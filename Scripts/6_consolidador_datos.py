#!/usr/bin/env python3
"""
Consolida los .txt de cada extractor en dos archivos de análisis:

  material_institucional.txt  <- posts oficiales (Twitter, Facebook, YouTube scripts)
  material_comentarios.txt    <- reacciones ciudadanas (Twitter, Facebook, YouTube comentarios, Medios)

Uso:
  python 6_consolidador_datos.py --since 2026-03-30 --before 2026-04-05

  El script infiere la semana ISO desde --since y busca los archivos en las
  carpetas de cada red (relativas a la raíz del repo o a --base-dir).
  La salida va a Datos/{semana_tag}/.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Importar build_report_tag desde el mismo directorio
sys.path.insert(0, str(REPO_ROOT / "Scripts"))
from output_naming import build_report_tag


# ---------------------------------------------------------------------------
# Definición de fuentes
# ---------------------------------------------------------------------------

def _sources(since: str, base_dir: Path, is_periodico: bool = False) -> dict[str, list[Path]]:
    """
    Devuelve dos listas de paths (pueden no existir):
      "institucional": posts oficiales
      "comentarios":   reacciones ciudadanas
    """
    if is_periodico:
        if since == "conjunto":
            # Modo conjunto: buscamos en TODAS las subcarpetas de base_dir que parezcan periodos
            # y que contengan carpetas de redes.
            institucional = []
            comentarios = []
            
            # Buscar subcarpetas que NO sean 'analisis_conjunto' ni terminen en '_Datos'
            for p_dir in base_dir.iterdir():
                if p_dir.is_dir() and p_dir.name != "analisis_conjunto" and not p_dir.name.endswith("_Datos"):
                    tag = p_dir.name
                    weekly_prefix = _periodic_weekly_prefix(tag)
                    institucional.extend([
                        *_candidate_paths(p_dir / "Twitter", [tag, weekly_prefix], "Twitter", "post_institucionales.txt"),
                        *_candidate_paths(p_dir / "Facebook", [tag, weekly_prefix], "Facebook", "posts.txt"),
                        *_candidate_paths(p_dir / "Youtube", [tag, weekly_prefix], "Youtube", "scripts.txt"),
                    ])
                    comentarios.extend([
                        *_candidate_paths(p_dir / "Twitter", [tag, weekly_prefix], "Twitter", "_comentarios.txt"),
                        *_candidate_paths(p_dir / "Facebook", [tag, weekly_prefix], "Facebook", "_comentarios.txt"),
                        *_candidate_paths(p_dir / "Youtube", [tag, weekly_prefix], "Youtube", "_comentarios.txt"),
                        *_candidate_paths(p_dir / "Medios", [tag, weekly_prefix], "Medios", ".txt", prefix="noticias_naucalpan_"),
                    ])
            return {"institucional": institucional, "comentarios": comentarios}

    tag_variants = _tag_variants(since, is_periodico)

    institucional = [
        *_candidate_paths(base_dir / "Twitter", tag_variants, "Twitter", "_post_institucionales.txt"),
        *_candidate_paths(base_dir / "Facebook", tag_variants, "Facebook", "_posts.txt"),
        *_candidate_paths(base_dir / "Youtube", tag_variants, "Youtube", "_scripts.txt"),
    ]

    comentarios = [
        *_candidate_paths(base_dir / "Twitter", tag_variants, "Twitter", "_comentarios.txt"),
        *_candidate_paths(base_dir / "Facebook", tag_variants, "Facebook", "_comentarios.txt"),
        *_candidate_paths(base_dir / "Youtube", tag_variants, "Youtube", "_comentarios.txt"),
        *_candidate_paths(base_dir / "Medios", tag_variants, "Medios", ".txt", prefix="noticias_naucalpan_"),
    ]

    return {"institucional": institucional, "comentarios": comentarios}


def _periodic_weekly_prefix(period_tag: str) -> str | None:
    raw = (period_tag or "").strip()
    try:
        start_date = raw.split("_al_", 1)[0].strip()
        return build_report_tag(start_date, "placeholder").rsplit("_", 1)[0]
    except Exception:
        return None


def _tag_variants(since: str, is_periodico: bool) -> list[str]:
    if not is_periodico:
        weekly_prefix = build_report_tag(since, "placeholder").rsplit("_", 1)[0]
        return [weekly_prefix]

    weekly_prefix = _periodic_weekly_prefix(since)
    variants = []
    if weekly_prefix:
        variants.append(weekly_prefix)
    if since not in variants:
        variants.append(since)
    return variants


def _candidate_paths(
    base_dir: Path,
    tag_prefixes: list[str | None],
    source: str,
    filename_tail: str,
    prefix: str = "",
) -> list[Path]:
    candidates: list[Path] = []
    for tag_prefix in tag_prefixes:
        if not tag_prefix:
            continue
        tag = f"{tag_prefix}_{source}"
        candidates.append(base_dir / tag / f"{prefix}{tag}{filename_tail}")
    if not candidates:
        return []
    for candidate in candidates:
        if candidate.exists():
            return [candidate]
    return [candidates[0]]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def consolidar(paths: list[Path]) -> tuple[list[str], list[str]]:
    """Lee y limpia líneas de cada archivo. Devuelve (líneas, advertencias)."""
    lines: list[str] = []
    warnings: list[str] = []

    for path in paths:
        if not path.exists():
            warnings.append(f"  ⚠️  No encontrado: {path}")
            continue
        with open(path, encoding="utf-8") as f:
            raw = f.readlines()
        kept = [l.rstrip("\n") for l in raw if l.strip()]
        lines.extend(kept)
        print(f"  ✅ {path.name}: {len(kept)} líneas")

    return lines, warnings


def escribir(lines: list[str], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        if lines:
            f.write("\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def valid_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Fecha inválida '{value}', usa YYYY-MM-DD") from exc
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consolida .txt de todos los extractores en material_institucional.txt y material_comentarios.txt"
    )
    parser.add_argument("--since", required=True,
                        help="Fecha inicio YYYY-MM-DD o tag de periodo")
    parser.add_argument("--before", required=False,
                        help="Fecha fin YYYY-MM-DD (heredado del orquestador)")
    parser.add_argument("--base-dir", default=str(REPO_ROOT),
                        help=f"Raíz del repositorio (default: {REPO_ROOT})")
    parser.add_argument("--output-dir", default=None,
                        help="Carpeta base de salida (default: <base-dir>/Datos)")
    parser.add_argument("--periodico", action="store_true",
                        help="Usa lógica de carpetas por periodo en lugar de semanas ISO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path(args.base_dir)
    output_base = Path(args.output_dir) if args.output_dir else base_dir / "Datos"
    if args.periodico and args.since == "conjunto":
        datos_tag = "conjunto_Datos"
    elif args.periodico:
        periodic_prefix = _periodic_weekly_prefix(args.since)
        datos_tag = f"{periodic_prefix or args.since}_Datos"
    else:
        datos_tag = build_report_tag(args.since, "Datos")
    output_dir = output_base / datos_tag

    print("\n" + "=" * 70)
    if args.periodico:
        print("📦 CONSOLIDADOR DE DATOS POR PERIODO")
    else:
        print("📦 CONSOLIDADOR DE DATOS SEMANALES")
    print("=" * 70)
    print(f"Tag    : {datos_tag}")
    print(f"Salida : {output_dir}")

    sources = _sources(args.since, base_dir, is_periodico=args.periodico)

    # ── Material institucional ──
    print("\n── Material institucional ──")
    inst_lines, inst_warn = consolidar(sources["institucional"])
    for w in inst_warn:
        print(w)

    inst_path = output_dir / "material_institucional.txt"
    escribir(inst_lines, inst_path)
    print(f"\n  📄 {inst_path.name}: {len(inst_lines)} líneas totales")

    # ── Material comentarios ──
    print("\n── Material comentarios ──")
    com_lines, com_warn = consolidar(sources["comentarios"])
    for w in com_warn:
        print(w)

    com_path = output_dir / "material_comentarios.txt"
    escribir(com_lines, com_path)
    print(f"\n  📄 {com_path.name}: {len(com_lines)} líneas totales")

    print("\n" + "=" * 70)
    print("✅ CONSOLIDACIÓN COMPLETADA")
    print("=" * 70)
    print(f"  {inst_path}")
    print(f"  {com_path}")


if __name__ == "__main__":
    main()
