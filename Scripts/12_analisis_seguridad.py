#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from output_naming import build_output_dir, build_report_tag, ensure_tagged_name


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = REPO_ROOT / "Datos"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "Seguridad"
DEFAULT_STOPWORDS_PATH = SCRIPTS_DIR / "diccionarios" / "stopwords" / "stop_list_espanol.txt"
DEFAULT_SEGURIDAD_PATH = SCRIPTS_DIR / "diccionarios" / "diccionario_seguridad.txt"
DEFAULT_INSEGURIDAD_PATH = SCRIPTS_DIR / "diccionarios" / "diccionario_inseguridad.txt"


def log(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}")


def valid_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Fecha invalida '{value}', usa YYYY-MM-DD") from exc
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analisis de seguridad/inseguridad sobre material_comentarios.txt")
    parser.add_argument("--since", required=True, type=valid_date,
                        help="Fecha inicio YYYY-MM-DD (define el tag de salida)")
    parser.add_argument("--before", required=True, type=valid_date,
                        help="Fecha fin YYYY-MM-DD (compatibilidad con orquestador)")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR),
                        help=f"Carpeta base de Datos (default: {DEFAULT_INPUT_DIR})")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                        help=f"Carpeta base de salida Seguridad (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--input-file", default="material_comentarios.txt",
                        help="Archivo de entrada dentro del directorio de Datos (default: material_comentarios.txt)")
    parser.add_argument("--stopwords-path", default=str(DEFAULT_STOPWORDS_PATH),
                        help=f"Ruta de stopwords (default: {DEFAULT_STOPWORDS_PATH})")
    parser.add_argument("--seguridad-path", default=str(DEFAULT_SEGURIDAD_PATH),
                        help=f"Ruta de diccionario seguridad (default: {DEFAULT_SEGURIDAD_PATH})")
    parser.add_argument("--inseguridad-path", default=str(DEFAULT_INSEGURIDAD_PATH),
                        help=f"Ruta de diccionario inseguridad (default: {DEFAULT_INSEGURIDAD_PATH})")
    return parser.parse_args()


def normalize_text(text: str) -> str:
    replacements = str.maketrans("áéíóúÁÉÍÓÚñÑüÜ", "aeiouAEIOUnNuU")
    cleaned = text.translate(replacements).lower()
    for token in (".", ",", ";", ":", "!", "¡", "?", "¿", "-", "_", "(", ")", "[", "]", "{", "}", '"', "'"):
        cleaned = cleaned.replace(token, " ")
    return " ".join(cleaned.split())


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding, errors="ignore")
        except OSError:
            continue
    raise FileNotFoundError(f"No se pudo leer archivo: {path}")


def read_wordlist(path: Path) -> set[str]:
    words: set[str] = set()
    if not path.exists():
        raise FileNotFoundError(f"No existe archivo de palabras: {path}")
    for line in read_text(path).splitlines():
        token = normalize_text(line).strip()
        if token:
            words.add(token)
    return words


def weekly_input_dir(base_dir: Path, since: str) -> Path:
    base_path = Path(base_dir)
    if (base_path / "material_comentarios.txt").exists() or (base_path / "material_institucional.txt").exists():
        return base_path
    tag = build_report_tag(since, "Datos")
    if base_path.name == tag:
        return base_path
    return base_path / tag


def tokenize(text: str) -> list[str]:
    return [token for token in normalize_text(text).split() if token]


def create_bar_chart(data: list[tuple[str, int]], title: str, output_path: Path, color: str) -> None:
    if not data:
        return
    words = [word for word, _ in data][::-1]
    freqs = [freq for _, freq in data][::-1]
    plt.figure(figsize=(12, 8))
    plt.barh(words, freqs, color=color)
    plt.xlabel("Frecuencia")
    plt.ylabel("Palabras")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def create_security_chart(seguridad_pct: float, inseguridad_pct: float, output_path: Path, report_tag: str) -> None:
    plt.figure(figsize=(10, 6))
    if (seguridad_pct + inseguridad_pct) > 0:
        values = [seguridad_pct, inseguridad_pct]
        explode = (0.1, 0)
        labels = ["Seguridad", "Inseguridad"]
        colors = ["#77dd77", "#ff6961"]
        plt.pie(
            values,
            explode=explode,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            shadow=True,
            startangle=90,
        )
        plt.axis("equal")
    else:
        plt.text(0.5, 0.5, "Sin palabras de seguridad detectadas", ha="center", va="center")
        plt.axis("off")
    plt.title(f"Distribucion de Seguridad/Inseguridad - {report_tag}")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def main() -> None:
    args = parse_args()
    input_week_dir = weekly_input_dir(Path(args.input_dir), args.since)
    output_week_dir = build_output_dir(Path(args.output_dir), args.since, "Seguridad")
    output_week_dir.mkdir(parents=True, exist_ok=True)

    input_path = input_week_dir / args.input_file
    if not input_path.exists():
        raise FileNotFoundError(f"No existe archivo de entrada: {input_path}")

    stopwords = read_wordlist(Path(args.stopwords_path))
    seguridad = read_wordlist(Path(args.seguridad_path)) - stopwords
    inseguridad = read_wordlist(Path(args.inseguridad_path)) - stopwords

    log(f"Entrada: {input_path}")
    log(f"Salida: {output_week_dir}")
    log(f"Stopwords: {len(stopwords)}")
    log(f"Palabras seguridad: {len(seguridad)}")
    log(f"Palabras inseguridad: {len(inseguridad)}")

    words = tokenize(read_text(input_path))
    filtered_words = [word for word in words if word not in stopwords]
    seguridad_encontradas = [word for word in filtered_words if word in seguridad]
    inseguridad_encontradas = [word for word in filtered_words if word in inseguridad]

    contador_seguridad = Counter(seguridad_encontradas)
    contador_inseguridad = Counter(inseguridad_encontradas)
    total_seguridad = sum(contador_seguridad.values())
    total_inseguridad = sum(contador_inseguridad.values())
    total = total_seguridad + total_inseguridad

    porcentaje_seguridad = (total_seguridad / total * 100) if total else 0.0
    porcentaje_inseguridad = (total_inseguridad / total * 100) if total else 0.0

    report_tag = build_report_tag(args.since, "Seguridad")
    txt_path = output_week_dir / f"{ensure_tagged_name('resultados_seguridad', report_tag)}.txt"
    pie_path = output_week_dir / f"{ensure_tagged_name('grafico_seguridad', report_tag)}.png"
    seg_bar_path = output_week_dir / f"{ensure_tagged_name('palabras_seguridad_frecuentes', report_tag)}.png"
    inseg_bar_path = output_week_dir / f"{ensure_tagged_name('palabras_inseguridad_frecuentes', report_tag)}.png"

    txt_lines = [
        "=== RESULTADOS DEL ANALISIS DE SEGURIDAD/INSEGURIDAD ===",
        f"Archivo fuente: {input_path.name}",
        f"Total de tokens analizados: {len(filtered_words)}",
        f"Palabras de seguridad encontradas: {total_seguridad}",
        f"Palabras de inseguridad encontradas: {total_inseguridad}",
        f"Total de palabras encontradas: {total}",
        f"Porcentaje de seguridad: {porcentaje_seguridad:.1f}%",
        f"Porcentaje de inseguridad: {porcentaje_inseguridad:.1f}%",
        "",
        "TOP 20 PALABRAS DE SEGURIDAD ENCONTRADAS:",
    ]
    txt_lines.extend(
        f"{idx}. {word}: {freq} veces"
        for idx, (word, freq) in enumerate(contador_seguridad.most_common(20), 1)
    )
    txt_lines.append("")
    txt_lines.append("TOP 20 PALABRAS DE INSEGURIDAD ENCONTRADAS:")
    txt_lines.extend(
        f"{idx}. {word}: {freq} veces"
        for idx, (word, freq) in enumerate(contador_inseguridad.most_common(20), 1)
    )
    txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")

    create_security_chart(porcentaje_seguridad, porcentaje_inseguridad, pie_path, report_tag)

    create_bar_chart(
        contador_seguridad.most_common(20),
        f"Palabras de Seguridad Mas Frecuentes - {report_tag}",
        seg_bar_path,
        "#77dd77",
    )
    create_bar_chart(
        contador_inseguridad.most_common(20),
        f"Palabras de Inseguridad Mas Frecuentes - {report_tag}",
        inseg_bar_path,
        "#ff6961",
    )

    log(f"Resultados TXT: {txt_path}")
    log(f"Grafico seguridad: {pie_path}")
    if contador_seguridad:
        log(f"Barras seguridad: {seg_bar_path}")
    if contador_inseguridad:
        log(f"Barras inseguridad: {inseg_bar_path}")
    log("Analisis de seguridad completado")


if __name__ == "__main__":
    main()
