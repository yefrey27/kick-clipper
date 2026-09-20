"""Puntaje de potencial viral de un clip (0-100).

La idea: un clip bueno no es el que tiene mas vistas, es el que tiene
muchas mas vistas de lo normal para ESE canal, en poco tiempo, y con
duracion apta para Shorts / TikTok / Reels.
"""
import json
import math
import statistics
from datetime import datetime, timezone

PESOS = {
    "velocidad": 34,   # vistas por hora
    "anomalia": 28,    # cuanto supera a la mediana del canal
    "enganche": 14,    # likes / vistas
    "duracion": 14,    # que tan editable es para formato corto
    "frescura": 10,    # que tan reciente es
}


def _parse(ts) -> datetime | None:
    if not ts:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    s = str(ts).replace("Z", "+00:00").replace(" ", "T", 1)
    for fmt in (None, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            d = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s[:26], fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def horas_desde(ts) -> float:
    d = _parse(ts)
    if not d:
        return 72.0
    delta = (datetime.now(timezone.utc) - d).total_seconds() / 3600
    return max(delta, 0.25)


def curva_duracion(seg: int) -> float:
    """1.0 alrededor de 25-45s, cae fuerte pasados 90s o bajo 8s."""
    if seg <= 0:
        return 0.35
    if seg < 8:
        return 0.30 + seg * 0.05
    if seg <= 60:
        return 1.0 - abs(seg - 35) / 90
    if seg <= 90:
        return 0.72 - (seg - 60) / 150
    return max(0.12, 0.52 - (seg - 90) / 420)


def velocidad(clip: dict) -> float:
    """Vistas por hora, con la ventana real si ya lo habiamos visto antes."""
    vistas = clip.get("views", 0)
    previas = clip.get("prev_views") or 0
    hs_prev = clip.get("prev_seen")
    if previas and hs_prev:
        ventana = horas_desde(hs_prev)
        if ventana >= 0.5 and vistas > previas:
            return (vistas - previas) / ventana
    return vistas / horas_desde(clip.get("created_at"))


def calcular(clip: dict, base_canal: dict | None = None) -> tuple[float, dict]:
    base = base_canal or {}
    mediana_vel = max(base.get("mediana_velocidad", 1.0), 0.5)

    vel = velocidad(clip)
    # 0 a 1: 1 vista/h = bajo, 400+ vistas/h = techo
    s_vel = min(1.0, math.log10(1 + vel) / math.log10(401))

    ratio = vel / mediana_vel
    s_anom = min(1.0, math.log2(1 + ratio) / math.log2(9))   # 8x la mediana = techo

    vistas = max(clip.get("views", 0), 1)
    s_eng = min(1.0, (clip.get("likes", 0) / vistas) / 0.06)  # 6% de likes = techo

    s_dur = curva_duracion(clip.get("duration", 0))
    s_fresh = math.exp(-horas_desde(clip.get("created_at")) / 200)

    partes = {
        "velocidad": round(s_vel * PESOS["velocidad"], 1),
        "anomalia": round(s_anom * PESOS["anomalia"], 1),
        "enganche": round(s_eng * PESOS["enganche"], 1),
        "duracion": round(s_dur * PESOS["duracion"], 1),
        "frescura": round(s_fresh * PESOS["frescura"], 1),
    }
    total = sum(partes.values())
    # Un clip de 4 minutos puede ser oro, pero hay que editarlo: baja en la fila.
    seg = clip.get("duration", 0)
    if seg > 120:
        total *= 0.88 if seg <= 240 else 0.78
    total = round(total, 1)
    partes["vistas_hora"] = round(vel, 1)
    partes["x_mediana"] = round(ratio, 2)
    return total, partes


def base_del_canal(clips: list[dict]) -> dict:
    """Referencia del canal para detectar clips fuera de curva."""
    vels = [velocidad(c) for c in clips if c.get("views")]
    if not vels:
        return {"mediana_velocidad": 1.0, "muestras": 0}
    return {
        "mediana_velocidad": max(statistics.median(vels), 0.5),
        "muestras": len(vels),
    }


def puntuar_lote(clips: list[dict]) -> list[dict]:
    base = base_del_canal(clips)
    for c in clips:
        total, partes = calcular(c, base)
        c["score"] = total
        c["score_parts"] = json.dumps(partes, ensure_ascii=False)
    return sorted(clips, key=lambda c: c["score"], reverse=True)
