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
import csv
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Importar build_report_tag desde el mismo directorio
sys.path.insert(0, str(REPO_ROOT / "Scripts"))
from output_naming import build_report_tag


PERIOD_DIR_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})_al_(\d{4}-\d{2}-\d{2})$")
TEXT_SUFFIXES = {".txt", ".md"}
CSV_SUFFIXES = {".csv"}
JSON_SUFFIXES = {".json"}
MERGEABLE_SUFFIXES = TEXT_SUFFIXES | CSV_SUFFIXES | JSON_SUFFIXES
SKIP_DIR_NAMES = {"__pycache__", ".git", ".idea"}


@dataclass(frozen=True)
class PeriodFolder:
    since: str
    before: str
    path: Path

    @property
    def name(self) -> str:
        return self.path.name


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


def _parse_period_folder(path: Path) -> PeriodFolder | None:
    match = PERIOD_DIR_PATTERN.match(path.name)
    if not match:
        return None
    since, before = match.groups()
    return PeriodFolder(since=since, before=before, path=path)


def _discover_period_folders(base_dir: Path) -> list[PeriodFolder]:
    periods: list[PeriodFolder] = []
    for child in sorted(base_dir.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        period = _parse_period_folder(child)
        if period is not None:
            periods.append(period)
    return sorted(periods, key=lambda period: (period.since, period.before, period.name))


def _build_material_range_tag(periods: list[PeriodFolder]) -> str:
    if not periods:
        raise ValueError("No hay periodos para construir el rango de materiales")
    first_since = min(period.since for period in periods).replace("-", "_")
    last_before = max(period.before for period in periods).replace("-", "_")
    return f"{first_since}_{last_before}"


def _canonical_material_filename(filename: str, period: PeriodFolder) -> str:
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix

    if stem.endswith("_Datos"):
        stem = stem[:-6]
    if stem.endswith("_Claude"):
        stem = stem[:-7]

    patterns = [
        re.escape(period.name),
        r"\d{4}_W\d{2}_(?:Datos|Claude)",
        r"\d{4}_W\d{2}",
        r"W\d{1,2}",
        r"\d{4}-\d{2}-\d{2}_al_\d{4}-\d{2}-\d{2}",
    ]
    for pattern in patterns:
        stem = re.sub(fr"_{pattern}$", "", stem, flags=re.IGNORECASE)

    stem = stem.rstrip("_") or path.stem
    return f"{stem}{suffix}"


def _is_binary_material(path: Path) -> bool:
    return path.suffix.lower() not in MERGEABLE_SUFFIXES


def _normalize_relative_material_path(relative_path: Path, period: PeriodFolder, source_name: str) -> Path:
    parts = list(relative_path.parts)
    if not parts:
        return relative_path

    first_part = parts[0]
    removable_prefixes = {
        period.name,
        f"{period.name}_{source_name}",
    }

    if first_part in removable_prefixes or first_part.endswith(f"_{source_name}"):
        parts = parts[1:]

    if not parts:
        return Path(relative_path.name)

    return Path(*parts)


def _iter_material_files(source_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def _merge_text_files(entries: list[tuple[PeriodFolder, Path]], dest: Path, include_headers: bool = True) -> int:
    blocks: list[str] = []
    total_chars = 0
    for period, source_path in entries:
        try:
            content = source_path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            content = ""
        if not content:
            continue
        if include_headers:
            header = f"===== {period.name} | {source_path.name} ====="
            blocks.append(f"{header}\n{content}")
        else:
            blocks.append(content)
        total_chars += len(content)

    escribir(blocks, dest)
    return total_chars


def _merge_csv_files(entries: list[tuple[PeriodFolder, Path]], dest: Path) -> int:
    fieldnames = ["source_period", "source_file"]
    rows: list[dict[str, str]] = []

    for period, source_path in entries:
        try:
            with source_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
                reader = csv.DictReader(handle)
                current_fieldnames = reader.fieldnames or []
                for name in current_fieldnames:
                    if name not in fieldnames:
                        fieldnames.append(name)
                for row in reader:
                    merged = {
                        "source_period": period.name,
                        "source_file": source_path.name,
                    }
                    for key, value in (row or {}).items():
                        merged[key] = "" if value is None else str(value)
                    rows.append(merged)
        except OSError:
            continue

    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return len(rows)


def _merge_json_files(entries: list[tuple[PeriodFolder, Path]], dest: Path) -> int:
    payloads: list[dict[str, object]] = []

    for period, source_path in entries:
        try:
            raw = source_path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            raw = ""
        if not raw:
            continue

        try:
            parsed: object = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw

        payloads.append(
            {
                "source_period": period.name,
                "source_file": source_path.name,
                "content": parsed,
            }
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as handle:
        json.dump(payloads, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return len(payloads)


def _copy_binary_materials(binary_entries: list[tuple[PeriodFolder, Path, Path]], dest_dir: Path) -> int:
    copied = 0
    for period, source_path, relative_path in binary_entries:
        target = dest_dir / "_originales" / period.name / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        copied += 1
    return copied


def _bundle_period_materials(
    periods: list[PeriodFolder],
    source_name: str,
    output_dir: Path,
) -> tuple[list[str], list[str]]:
    summary: list[str] = []
    warnings: list[str] = []
    grouped: dict[Path, list[tuple[PeriodFolder, Path]]] = {}
    binaries: list[tuple[PeriodFolder, Path, Path]] = []

    for period in periods:
        source_dir = period.path / source_name
        if not source_dir.exists():
            warnings.append(f"  ⚠️  No existe carpeta {source_name} en: {period.path}")
            continue

        for source_path in _iter_material_files(source_dir):
            relative_path = source_path.relative_to(source_dir)
            normalized_relative = _normalize_relative_material_path(relative_path, period, source_name)
            if _is_binary_material(source_path):
                binaries.append((period, source_path, normalized_relative))
                continue

            canonical_name = _canonical_material_filename(normalized_relative.name, period)
            canonical_relpath = normalized_relative.with_name(canonical_name)
            grouped.setdefault(canonical_relpath, []).append((period, source_path))

    output_dir.mkdir(parents=True, exist_ok=True)

    for relative_path, entries in sorted(grouped.items(), key=lambda item: str(item[0])):
        dest = output_dir / relative_path
        suffix = dest.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            include_headers = dest.name not in {"material_institucional.txt", "material_comentarios.txt"}
            total = _merge_text_files(entries, dest, include_headers=include_headers)
            summary.append(f"  📄 {source_name}/{relative_path}: {len(entries)} archivo(s), {total:,} caracteres")
        elif suffix in CSV_SUFFIXES:
            total = _merge_csv_files(entries, dest)
            summary.append(f"  📊 {source_name}/{relative_path}: {len(entries)} archivo(s), {total:,} fila(s)")
        elif suffix in JSON_SUFFIXES:
            total = _merge_json_files(entries, dest)
            summary.append(f"  🧾 {source_name}/{relative_path}: {len(entries)} archivo(s), {total:,} entrada(s)")

    copied = _copy_binary_materials(binaries, output_dir)
    if copied:
        summary.append(f"  📦 {source_name}/_originales: {copied} archivo(s) binario(s) copiado(s)")

    return summary, warnings


def consolidar_materiales_conjuntos(base_dir: Path, output_base: Path) -> tuple[Path, list[str], list[str]]:
    periods = _discover_period_folders(base_dir)
    if not periods:
        raise FileNotFoundError(
            f"No se encontraron carpetas de periodo dentro de {base_dir}. "
            "Se esperaban nombres como YYYY-MM-DD_al_YYYY-MM-DD"
        )

    range_tag = _build_material_range_tag(periods)
    bundle_dir = output_base / range_tag
    summary: list[str] = []
    warnings: list[str] = []

    for source_name in ("Datos", "Claude"):
        source_output_dir = bundle_dir / source_name
        if source_output_dir.exists():
            shutil.rmtree(source_output_dir)
        source_summary, source_warnings = _bundle_period_materials(periods, source_name, source_output_dir)
        summary.extend(source_summary)
        warnings.extend(source_warnings)

    manifest = {
        "range_tag": range_tag,
        "period_count": len(periods),
        "periods": [
            {
                "since": period.since,
                "before": period.before,
                "folder": str(period.path),
            }
            for period in periods
        ],
    }
    manifest_path = bundle_dir / "manifest_materiales_conjunto.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    summary.append(f"  🗂️ manifest_materiales_conjunto.json: {len(periods)} periodo(s)")

    return bundle_dir, summary, warnings


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
    if args.periodico and args.since == "conjunto":
        output_base = Path(args.output_dir) if args.output_dir else base_dir
    else:
        output_base = Path(args.output_dir) if args.output_dir else base_dir / "Datos"

    if args.periodico and args.since == "conjunto":
        print("\n" + "=" * 70)
        print("📚 CONSOLIDADOR DE MATERIALES CONJUNTOS")
        print("=" * 70)
        print(f"Base periodos : {base_dir}")
        print(f"Salida base   : {output_base}")

        bundle_dir, summary, warnings = consolidar_materiales_conjuntos(base_dir, output_base)
        for line in summary:
            print(line)
        for warning in warnings:
            print(warning)

        print("\n" + "=" * 70)
        print("✅ CONSOLIDACIÓN CONJUNTA COMPLETADA")
        print("=" * 70)
        print(f"  Carpeta rango: {bundle_dir}")
        print(f"  Datos        : {bundle_dir / 'Datos'}")
        print(f"  Claude       : {bundle_dir / 'Claude'}")
        return

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
