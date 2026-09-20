"""Revisa todos los canales de canales.txt y actualiza docs/data/clips.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import kick, scoring                                   # noqa: E402
from scripts.comun import (CLIPS_POR_CANAL, ahora, cargar,      # noqa: E402
                           guardar, leer_canales)


def main() -> int:
    estado = cargar()
    clips_guardados = estado.get("clips", {})
    canales_info, fallos = [], 0

    for slug in leer_canales():
        entrada = {"slug": slug, "revisado": ahora(), "error": None, "nuevos": 0}
        try:
            perfil = kick.get_channel(slug)
            entrada["nombre"] = perfil["display_name"]
            entrada["avatar"] = perfil["avatar"]
            entrada["seguidores"] = perfil["followers"]
            slug = perfil["slug"]
            entrada["slug"] = slug
        except Exception as exc:
            print(f"::warning::no pude leer el perfil de {slug}: {exc}")
            entrada["nombre"] = slug

        try:
            lote = kick.get_clips(slug, limit=CLIPS_POR_CANAL, sort="date", window="month")
        except Exception as exc:
            entrada["error"] = str(exc)[:200]
            canales_info.append(entrada)
            fallos += 1
            print(f"::warning::fallo al traer clips de {slug}: {exc}")
            continue

        for c in lote:
            viejo = clips_guardados.get(c["id"])
            if viejo:
                c["prev_views"] = viejo.get("views", 0)
                c["prev_seen"] = viejo.get("visto")

        scoring.puntuar_lote(lote)

        for c in lote:
            viejo = clips_guardados.get(c["id"], {})
            if not viejo:
                entrada["nuevos"] += 1
            clips_guardados[c["id"]] = {
                **{k: c[k] for k in ("id", "channel_slug", "title", "url", "source_url",
                                     "thumbnail", "duration", "views", "likes",
                                     "category", "created_at")},
                "score": c["score"],
                "partes": __import__("json").loads(c["score_parts"]),
                "visto": ahora(),
                "prev_views": c.get("prev_views", 0),
                "estado": viejo.get("estado", "nuevo"),
                "archivo": viejo.get("archivo"),
                "vertical": viejo.get("vertical"),
            }

        entrada["total"] = sum(1 for v in clips_guardados.values()
                               if v["channel_slug"] == slug)
        canales_info.append(entrada)
        print(f"{slug}: {len(lote)} clips revisados, {entrada['nuevos']} nuevos")

    # Nos quedamos con los 400 clips mas recientes para que el JSON no engorde.
    if len(clips_guardados) > 400:
        ordenados = sorted(clips_guardados.items(),
                           key=lambda kv: kv[1].get("visto") or "", reverse=True)
        conservar = {k: v for k, v in ordenados[:400]}
        conservar.update({k: v for k, v in clips_guardados.items()
                          if v.get("estado") == "listo"})
        clips_guardados = conservar

    estado["clips"] = clips_guardados
    estado["canales"] = canales_info
    guardar(estado)

    if canales_info and fallos == len(canales_info):
        print("::error::ningun canal respondio. Probablemente Cloudflare bloqueo al runner.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
