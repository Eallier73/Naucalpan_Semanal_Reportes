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
DEFAULT_OUTPUT_DIR = REPO_ROOT / "Polaridad"
DEFAULT_STOPWORDS_PATH = SCRIPTS_DIR / "diccionarios" / "stopwords" / "stop_list_espanol.txt"
DEFAULT_POSITIVAS_PATH = SCRIPTS_DIR / "diccionarios" / "diccionario_palabras_positivas.txt"
DEFAULT_NEGATIVAS_PATH = SCRIPTS_DIR / "diccionarios" / "diccionario_palabras_negativas.txt"


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
    parser = argparse.ArgumentParser(description="Analisis de polaridad sobre material_comentarios.txt")
    parser.add_argument("--since", required=True, type=valid_date,
                        help="Fecha inicio YYYY-MM-DD (define el tag de salida)")
    parser.add_argument("--before", required=True, type=valid_date,
                        help="Fecha fin YYYY-MM-DD (compatibilidad con orquestador)")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR),
                        help=f"Carpeta base de Datos (default: {DEFAULT_INPUT_DIR})")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                        help=f"Carpeta base de salida Polaridad (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--input-file", default="material_comentarios.txt",
                        help="Archivo de entrada dentro del directorio de Datos (default: material_comentarios.txt)")
    parser.add_argument("--stopwords-path", default=str(DEFAULT_STOPWORDS_PATH),
                        help=f"Ruta de stopwords (default: {DEFAULT_STOPWORDS_PATH})")
    parser.add_argument("--positivas-path", default=str(DEFAULT_POSITIVAS_PATH),
                        help=f"Ruta de diccionario positivo (default: {DEFAULT_POSITIVAS_PATH})")
    parser.add_argument("--negativas-path", default=str(DEFAULT_NEGATIVAS_PATH),
                        help=f"Ruta de diccionario negativo (default: {DEFAULT_NEGATIVAS_PATH})")
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


def create_polarity_chart(positivas_pct: float, negativas_pct: float, output_path: Path, report_tag: str) -> None:
    plt.figure(figsize=(10, 6))
    if (positivas_pct + negativas_pct) > 0:
        values = [positivas_pct, negativas_pct]
        explode = (0.1, 0)
        labels = ["Positivas", "Negativas"]
        colors = ["#66b3ff", "#ff9999"]
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
        plt.text(0.5, 0.5, "Sin palabras de polaridad detectadas", ha="center", va="center")
        plt.axis("off")
    plt.title(f"Distribucion de Polaridad - {report_tag}")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def main() -> None:
    args = parse_args()
    input_week_dir = weekly_input_dir(Path(args.input_dir), args.since)
    output_week_dir = build_output_dir(Path(args.output_dir), args.since, "Polaridad")
    output_week_dir.mkdir(parents=True, exist_ok=True)

    input_path = input_week_dir / args.input_file
    if not input_path.exists():
        raise FileNotFoundError(f"No existe archivo de entrada: {input_path}")

    stopwords = read_wordlist(Path(args.stopwords_path))
    positivas = read_wordlist(Path(args.positivas_path)) - stopwords
    negativas = read_wordlist(Path(args.negativas_path)) - stopwords

    log(f"Entrada: {input_path}")
    log(f"Salida: {output_week_dir}")
    log(f"Stopwords: {len(stopwords)}")
    log(f"Palabras positivas: {len(positivas)}")
    log(f"Palabras negativas: {len(negativas)}")

    words = tokenize(read_text(input_path))
    filtered_words = [word for word in words if word not in stopwords]
    positivas_encontradas = [word for word in filtered_words if word in positivas]
    negativas_encontradas = [word for word in filtered_words if word in negativas]

    contador_positivas = Counter(positivas_encontradas)
    contador_negativas = Counter(negativas_encontradas)
    total_positivas = sum(contador_positivas.values())
    total_negativas = sum(contador_negativas.values())
    total = total_positivas + total_negativas

    porcentaje_positivas = (total_positivas / total * 100) if total else 0.0
    porcentaje_negativas = (total_negativas / total * 100) if total else 0.0

    report_tag = build_report_tag(args.since, "Polaridad")
    txt_path = output_week_dir / f"{ensure_tagged_name('resultados_polaridad', report_tag)}.txt"
    pie_path = output_week_dir / f"{ensure_tagged_name('grafico_polaridad', report_tag)}.png"
    pos_bar_path = output_week_dir / f"{ensure_tagged_name('palabras_positivas_frecuentes', report_tag)}.png"
    neg_bar_path = output_week_dir / f"{ensure_tagged_name('palabras_negativas_frecuentes', report_tag)}.png"

    txt_lines = [
        "=== RESULTADOS DEL ANALISIS DE POLARIDAD ===",
        f"Archivo fuente: {input_path.name}",
        f"Total de tokens analizados: {len(filtered_words)}",
        f"Palabras positivas encontradas: {total_positivas}",
        f"Palabras negativas encontradas: {total_negativas}",
        f"Total de palabras encontradas: {total}",
        f"Porcentaje de palabras positivas: {porcentaje_positivas:.1f}%",
        f"Porcentaje de palabras negativas: {porcentaje_negativas:.1f}%",
        "",
        "TOP 20 PALABRAS POSITIVAS ENCONTRADAS:",
    ]
    txt_lines.extend(
        f"{idx}. {word}: {freq} veces"
        for idx, (word, freq) in enumerate(contador_positivas.most_common(20), 1)
    )
    txt_lines.append("")
    txt_lines.append("TOP 20 PALABRAS NEGATIVAS ENCONTRADAS:")
    txt_lines.extend(
        f"{idx}. {word}: {freq} veces"
        for idx, (word, freq) in enumerate(contador_negativas.most_common(20), 1)
    )
    txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")

    create_polarity_chart(porcentaje_positivas, porcentaje_negativas, pie_path, report_tag)

    create_bar_chart(
        contador_positivas.most_common(20),
        f"Palabras Positivas Mas Frecuentes - {report_tag}",
        pos_bar_path,
        "#66b3ff",
    )
    create_bar_chart(
        contador_negativas.most_common(20),
        f"Palabras Negativas Mas Frecuentes - {report_tag}",
        neg_bar_path,
        "#ff9999",
    )

    log(f"Resultados TXT: {txt_path}")
    log(f"Grafico polaridad: {pie_path}")
    if contador_positivas:
        log(f"Barras positivas: {pos_bar_path}")
    if contador_negativas:
        log(f"Barras negativas: {neg_bar_path}")
    log("Analisis de polaridad completado")


if __name__ == "__main__":
    main()
