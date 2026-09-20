"""Cambia el estado de clips desde el tablero (descartar / reintentar)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.comun import cargar, guardar   # noqa: E402

if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else ""
    ids = [i for i in (sys.argv[2] if len(sys.argv) > 2 else "").split(",") if i.strip()]
    nuevo = {"descartar": "descartado", "reintentar": "nuevo"}.get(accion)
    if not nuevo or not ids:
        raise SystemExit("uso: marcar.py descartar|reintentar id1,id2")
    estado = cargar()
    for i in ids:
        if i in estado["clips"]:
            estado["clips"][i]["estado"] = nuevo
            estado["clips"][i]["error"] = None
    guardar(estado)
    print(f"{len(ids)} clips marcados como {nuevo}")
