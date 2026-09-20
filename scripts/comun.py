import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "docs" / "data" / "clips.json"
CANALES = RAIZ / "canales.txt"

UMBRAL = float(os.getenv("AUTO_DOWNLOAD_SCORE", 72))
MAX_POR_TANDA = int(os.getenv("MAX_DOWNLOADS_PER_RUN", 4))
CLIPS_POR_CANAL = int(os.getenv("CLIPS_PER_SCAN", 40))
VERTICAL = os.getenv("MAKE_VERTICAL", "true").lower() in ("1", "true", "yes", "si")
TAG = os.getenv("RELEASE_TAG", "clips")
REPO = os.getenv("GITHUB_REPOSITORY", "")


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def leer_canales() -> list[str]:
    if not CANALES.exists():
        return []
    fuera = []
    for linea in CANALES.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#")[0].strip()
        if not linea:
            continue
        slug = linea.rstrip("/").split("/")[-1].lstrip("@").lower()
        if slug:
            fuera.append(slug)
    return fuera


def cargar() -> dict:
    if ESTADO.exists():
        try:
            return json.loads(ESTADO.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"actualizado": None, "canales": [], "clips": {}}


def guardar(estado: dict):
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    estado["actualizado"] = ahora()
    estado["umbral"] = UMBRAL
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")


def nombre_archivo(clip: dict, sufijo: str = "") -> str:
    limpio = re.sub(r"[^\w\s-]", "", clip.get("title", ""), flags=re.UNICODE).strip()
    limpio = re.sub(r"[\s_-]+", "-", limpio)[:60].strip("-").lower() or "clip"
    return f"{clip['channel_slug']}-{clip['id']}-{limpio}{sufijo}.mp4"


def url_release(archivo: str) -> str:
    return f"https://github.com/{REPO}/releases/download/{TAG}/{archivo}"
