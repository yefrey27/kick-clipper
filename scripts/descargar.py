"""Descarga los clips pendientes y los sube como assets de un Release.

Elige solos los que pasan el umbral, o los ids que le pases:
    python scripts/descargar.py 1234567,7654321
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.comun import (MAX_POR_TANDA, TAG, UMBRAL, VERTICAL,  # noqa: E402
                           cargar, guardar, nombre_archivo, url_release)

TMP = Path("/tmp/clips")


def elegir(estado: dict, forzados: list[str]) -> list[dict]:
    clips = estado["clips"]
    if forzados:
        return [clips[i] for i in forzados if i in clips]
    pendientes = [c for c in clips.values()
                  if c.get("estado") == "nuevo" and c.get("score", 0) >= UMBRAL]
    pendientes.sort(key=lambda c: c["score"], reverse=True)
    return pendientes[:MAX_POR_TANDA]


def bajar(clip: dict) -> Path:
    import yt_dlp
    TMP.mkdir(parents=True, exist_ok=True)
    destino = TMP / nombre_archivo(clip)
    opciones = {
        "outtmpl": str(destino.with_suffix(".%(ext)s")),
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "concurrent_fragment_downloads": 8,
        "retries": 5,
        "fragment_retries": 10,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "http_headers": {"Referer": "https://kick.com/"},
    }
    for objetivo in (clip.get("url"), clip.get("source_url")):
        if not objetivo:
            continue
        try:
            with yt_dlp.YoutubeDL(opciones) as ydl:
                ydl.download([objetivo])
            break
        except Exception as exc:
            print(f"  intento fallido con {objetivo[:60]}…: {exc}")
    else:
        raise RuntimeError("ninguna URL del clip funciono")

    candidatos = [p for p in TMP.glob(destino.stem + ".*")
                  if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")]
    if not candidatos:
        raise RuntimeError("yt-dlp no dejo archivo")
    mejor = max(candidatos, key=lambda p: p.stat().st_size)
    if mejor.suffix != ".mp4":
        salida = mejor.with_suffix(".mp4")
        subprocess.run(["ffmpeg", "-y", "-i", str(mejor), "-c", "copy", str(salida)],
                       check=True, capture_output=True)
        mejor = salida
    return mejor


def a_vertical(origen: Path) -> Path:
    salida = origen.with_name(origen.stem + "-9x16.mp4")
    filtro = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
              "crop=1080:1920,boxblur=28:3[bg];"
              "[0:v]scale=1080:-2:flags=lanczos[fg];"
              "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(origen), "-filter_complex", filtro,
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "19", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
         str(salida)],
        check=True, capture_output=True)
    return salida


def subir(archivo: Path):
    subprocess.run(["gh", "release", "upload", TAG, str(archivo), "--clobber"],
                   check=True)


def main() -> int:
    forzados = [i for i in (sys.argv[1] if len(sys.argv) > 1 else "").split(",") if i.strip()]
    estado = cargar()
    tanda = elegir(estado, forzados)
    if not tanda:
        print("No hay nada que descargar en esta pasada.")
        return 0

    for clip in tanda:
        ident = clip["id"]
        print(f"→ {clip['score']:.0f} pts · {clip['title'][:60]}")
        try:
            archivo = bajar(clip)
            subir(archivo)
            estado["clips"][ident]["archivo"] = url_release(archivo.name)

            if VERTICAL:
                try:
                    v = a_vertical(archivo)
                    subir(v)
                    estado["clips"][ident]["vertical"] = url_release(v.name)
                except Exception as exc:
                    print(f"  sin version 9:16: {exc}")

            estado["clips"][ident]["estado"] = "listo"
            estado["clips"][ident]["error"] = None
            print(f"  subido: {archivo.name} ({archivo.stat().st_size // 1024} KB)")
        except Exception as exc:
            estado["clips"][ident]["estado"] = "error"
            estado["clips"][ident]["error"] = str(exc)[:300]
            print(f"::warning::fallo {ident}: {exc}")
        finally:
            shutil.rmtree(TMP, ignore_errors=True)
        guardar(estado)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
