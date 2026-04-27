#!/usr/bin/env python3
import importlib.util
from pathlib import Path


def main():
    gui_path = Path(__file__).resolve().parent / "Scripts" / "00_gui_orquestador.py"
    spec = importlib.util.spec_from_file_location("naucalpan_gui_orquestador", gui_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar la GUI desde {gui_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


if __name__ == "__main__":
    main()