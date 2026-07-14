#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from output_naming import build_report_tag


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUBIR_IA_DIR = REPO_ROOT / "Subir_IA"
REQUIRED_PIPELINE_CODES = {"6", "7", "8", "9", "10", "11", "12"}


def build_week_tag(since: str) -> str:
    return build_report_tag(since, "Datos").rsplit("_", 1)[0]


def expected_sources_for_week(since: str, repo_root: Path = REPO_ROOT) -> list[Path]:
    week_tag = build_week_tag(since)
    temas_tag = f"{week_tag}_Temas_Guiados"
    seguridad_tag = f"{week_tag}_Seguridad"
    polaridad_tag = f"{week_tag}_Polaridad"
    influencia_tag = f"{week_tag}_Influencia_Temas"
    claude_tag = f"{week_tag}_Claude"
    datos_tag = f"{week_tag}_Datos"

    return [
        repo_root / "Temas_Guiados" / temas_tag / f"informe_temas_guiados_{temas_tag}.txt",
        repo_root / "Seguridad" / seguridad_tag / f"resultados_seguridad_{seguridad_tag}.txt",
        repo_root / "Polaridad" / polaridad_tag / f"resultados_polaridad_{polaridad_tag}.txt",
        repo_root / "Influencia_Temas" / influencia_tag / "ejecutivo" / "00_resumen_ejecutivo.md",
        repo_root / "Claude" / claude_tag / f"corpus_publicaciones_institucionales_{claude_tag}.txt",
        repo_root / "Datos" / datos_tag / f"corpus_claude_{datos_tag}.txt",
        repo_root / "Datos" / datos_tag / "material_comentarios.txt",
        repo_root / "Datos" / datos_tag / "material_institucional.txt",
        repo_root / "Datos" / datos_tag / f"publicaciones_institucionales_redes_{datos_tag}.csv",
    ]


def export_week_to_subir_ia(
    since: str,
    destination_root: Path = DEFAULT_SUBIR_IA_DIR,
    repo_root: Path = REPO_ROOT,
) -> Path:
    week_tag = build_week_tag(since)
    destination_dir = Path(destination_root) / week_tag
    sources = expected_sources_for_week(since, repo_root=repo_root)
    missing = [str(path) for path in sources if not path.exists()]
    if missing:
        missing_list = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            f"No se pudo preparar Subir_IA para {week_tag}. Faltan archivos requeridos:\n{missing_list}"
        )

    destination_dir.mkdir(parents=True, exist_ok=True)
    for source in sources:
        shutil.copy2(source, destination_dir / source.name)
    return destination_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copia los entregables semanales requeridos a Subir_IA/<semana>."
    )
    parser.add_argument("--since", required=True, help="Fecha de inicio semanal (YYYY-MM-DD)")
    parser.add_argument(
        "--destination-root",
        default=str(DEFAULT_SUBIR_IA_DIR),
        help=f"Carpeta raíz de destino (default: {DEFAULT_SUBIR_IA_DIR})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    destination_dir = export_week_to_subir_ia(
        since=args.since,
        destination_root=Path(args.destination_root),
    )
    print(f"✅ Archivos copiados a: {destination_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
