#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import anthropic
import pandas as pd

try:
    from dotenv import load_dotenv

    env_file = Path(__file__).resolve().parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(str(env_file))
except ImportError:
    pass

from output_naming import build_report_tag, ensure_tagged_name


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TWITTER_DIR = REPO_ROOT / "Twitter"
DEFAULT_FACEBOOK_DIR = REPO_ROOT / "Facebook"
DEFAULT_YOUTUBE_DIR = REPO_ROOT / "Youtube"
DEFAULT_DATOS_DIR = REPO_ROOT / "Datos"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "Claude"
DEFAULT_MODEL = "claude-opus-4-6"
DEFAULT_MAX_CORPUS_CHARS = 500000
DEFAULT_SAMPLE_SEED = 42
DEFAULT_MAX_DOC_CHARS = 6000
API_ENV_NAME = "CLAUDE_API_KEY"
THEME_COUNT = 8
CASE_ORDER = ["gobierno_naucalpan", "isaac_montoya", "guardia_municipal"]
CASE_LABELS = {
    "gobierno_naucalpan": "Gobierno de Naucalpan",
    "isaac_montoya": "Isaac Montoya",
    "guardia_municipal": "Guardia Municipal de Naucalpan",
}
CASE_TOKENS = {
    "gobierno_naucalpan": [
        "gobnau",
        "ciudadnaucalpan",
        "gobiernonaucalpan",
        "gobiernodenaucalpan",
        "gobiernonaucalpanedomex",
    ],
    "isaac_montoya": [
        "isaacsolar",
        "isaacmontoya24",
        "isaacmontoya",
    ],
    "guardia_municipal": [
        "guardiamunicipalciudadnaucalpan",
        "guardiamunicipaldenaucalpan",
        "guardiamunicipal",
    ],
}
NETWORK_LABELS = {
    "twitter": "Twitter/X",
    "facebook": "Facebook",
    "youtube": "YouTube",
}
MONTH_NAMES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
}
COMMON_COLUMNS = [
    "fecha_semana",
    "nombre_semana",
    "caso",
    "caso_label",
    "red_social",
    "red_social_label",
    "tipo_publicacion",
    "cuenta_origen",
    "autor",
    "titulo",
    "texto_publicacion",
    "texto_para_analisis",
    "url_publicacion",
    "id_publicacion",
    "fecha_publicacion",
    "fecha_publicacion_date",
    "archivo_origen",
]


def log_message(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def valid_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Fecha invalida '{value}', usa YYYY-MM-DD") from exc
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Consolida publicaciones institucionales de Twitter, Facebook y YouTube "
            "y genera un analisis tematico comparado con Claude para Naucalpan."
        )
    )
    parser.add_argument("--since", required=True, type=valid_date, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--before", required=True, type=valid_date, help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--twitter-dir", default=str(DEFAULT_TWITTER_DIR))
    parser.add_argument("--facebook-dir", default=str(DEFAULT_FACEBOOK_DIR))
    parser.add_argument("--youtube-dir", default=str(DEFAULT_YOUTUBE_DIR))
    parser.add_argument("--datos-dir", default=str(DEFAULT_DATOS_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-corpus-chars", type=int, default=DEFAULT_MAX_CORPUS_CHARS)
    parser.add_argument("--sample-seed", type=int, default=DEFAULT_SAMPLE_SEED)
    parser.add_argument("--max-doc-chars", type=int, default=DEFAULT_MAX_DOC_CHARS)
    parser.add_argument("--prepare-only", action="store_true")
    return parser.parse_args()


def weekly_dir(base_dir: Path, since: str, source: str) -> Path:
    base_path = Path(base_dir)
    tag = build_report_tag(since, source)
    if base_path.name == tag:
        return base_path
    return base_path / tag


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def save_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    last_exc: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except Exception as exc:
            last_exc = exc
    raise RuntimeError(f"No se pudo leer {path}: {last_exc}")


def normalize_whitespace(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_token(value: object) -> str:
    text = normalize_whitespace(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text)


def classify_case(*candidates: object) -> str:
    normalized = "".join(normalize_token(candidate) for candidate in candidates if candidate)
    for case in CASE_ORDER:
        if any(token in normalized for token in CASE_TOKENS[case]):
            return case
    return ""


def extract_handle_from_url(url: object) -> str:
    raw = normalize_whitespace(url)
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except Exception:
        return ""
    path = (parsed.path or "").strip("/")
    if not path:
        return ""
    return path.split("/")[0]


def parse_datetime_fields(value: object) -> tuple[str, str]:
    text = normalize_whitespace(value)
    if not text:
        return "", ""

    variants = [text]
    if text.endswith("Z"):
        variants.append(text[:-1] + "+00:00")

    for variant in variants:
        try:
            dt = datetime.fromisoformat(variant)
            return dt.isoformat(sep=" "), dt.date().isoformat()
        except ValueError:
            continue

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.isoformat(sep=" "), dt.date().isoformat()
        except ValueError:
            continue

    return text, text[:10] if len(text) >= 10 else ""


def build_text_for_analysis(title: str, body: str) -> str:
    if title and body:
        return f"{title}. {body}"
    return title or body


def load_twitter_records(base_dir: Path, since: str) -> tuple[list[dict[str, str]], dict[str, object]]:
    week_dir = weekly_dir(base_dir, since, "Twitter")
    csv_path = week_dir / f"{week_dir.name}_post_institucionales.csv"
    meta: dict[str, object] = {
        "source": "twitter",
        "path": str(csv_path),
        "exists": csv_path.exists(),
        "records": 0,
        "skipped_empty_text": 0,
        "skipped_unknown_case": 0,
    }
    if not csv_path.exists():
        return [], meta

    df = read_csv_with_fallback(csv_path)
    records: list[dict[str, str]] = []

    for row in df.fillna("").to_dict("records"):
        text = normalize_whitespace(row.get("text"))
        if not text:
            meta["skipped_empty_text"] = int(meta["skipped_empty_text"]) + 1
            continue

        url = normalize_whitespace(row.get("url"))
        author = normalize_whitespace(row.get("author"))
        query_used = normalize_whitespace(row.get("query_used"))
        handle = extract_handle_from_url(url)
        case = classify_case(author, query_used, handle)
        if not case:
            meta["skipped_unknown_case"] = int(meta["skipped_unknown_case"]) + 1
            continue

        fecha_publicacion, fecha_publicacion_date = parse_datetime_fields(
            row.get("datetime_parsed_utc") or row.get("datetime")
        )
        cuenta_origen = author or handle
        records.append(
            {
                "fecha_semana": since,
                "nombre_semana": normalize_whitespace(row.get("nombre_semana")) or week_dir.name,
                "caso": case,
                "caso_label": CASE_LABELS[case],
                "red_social": "twitter",
                "red_social_label": NETWORK_LABELS["twitter"],
                "tipo_publicacion": "tweet",
                "cuenta_origen": cuenta_origen,
                "autor": author,
                "titulo": "",
                "texto_publicacion": text,
                "texto_para_analisis": text,
                "url_publicacion": url,
                "id_publicacion": url or text[:120],
                "fecha_publicacion": fecha_publicacion,
                "fecha_publicacion_date": fecha_publicacion_date,
                "archivo_origen": str(csv_path),
            }
        )

    meta["records"] = len(records)
    return records, meta


def load_facebook_records(base_dir: Path, since: str) -> tuple[list[dict[str, str]], dict[str, object]]:
    week_dir = weekly_dir(base_dir, since, "Facebook")
    csv_path = week_dir / f"{week_dir.name}_posts.csv"
    meta: dict[str, object] = {
        "source": "facebook",
        "path": str(csv_path),
        "exists": csv_path.exists(),
        "records": 0,
        "skipped_empty_text": 0,
        "skipped_unknown_case": 0,
    }
    if not csv_path.exists():
        return [], meta

    df = read_csv_with_fallback(csv_path)
    records: list[dict[str, str]] = []

    for row in df.fillna("").to_dict("records"):
        text = normalize_whitespace(row.get("post_texto"))
        if not text:
            meta["skipped_empty_text"] = int(meta["skipped_empty_text"]) + 1
            continue

        page_handle = normalize_whitespace(row.get("page_handle"))
        page_url = normalize_whitespace(row.get("page_url"))
        author = normalize_whitespace(row.get("autor"))
        case = classify_case(page_handle, page_url, author)
        if not case:
            meta["skipped_unknown_case"] = int(meta["skipped_unknown_case"]) + 1
            continue

        fecha_publicacion, fecha_publicacion_date = parse_datetime_fields(row.get("fecha_post"))
        url = normalize_whitespace(row.get("post_url"))
        cuenta_origen = page_handle or extract_handle_from_url(page_url) or author
        records.append(
            {
                "fecha_semana": since,
                "nombre_semana": week_dir.name,
                "caso": case,
                "caso_label": CASE_LABELS[case],
                "red_social": "facebook",
                "red_social_label": NETWORK_LABELS["facebook"],
                "tipo_publicacion": "post_facebook",
                "cuenta_origen": cuenta_origen,
                "autor": author,
                "titulo": "",
                "texto_publicacion": text,
                "texto_para_analisis": text,
                "url_publicacion": url,
                "id_publicacion": url or text[:120],
                "fecha_publicacion": fecha_publicacion,
                "fecha_publicacion_date": fecha_publicacion_date,
                "archivo_origen": str(csv_path),
            }
        )

    meta["records"] = len(records)
    return records, meta


def load_youtube_records(base_dir: Path, since: str) -> tuple[list[dict[str, str]], dict[str, object]]:
    week_dir = weekly_dir(base_dir, since, "Youtube")
    csv_path = week_dir / f"{week_dir.name}_scripts.csv"
    meta: dict[str, object] = {
        "source": "youtube",
        "path": str(csv_path),
        "exists": csv_path.exists(),
        "records": 0,
        "skipped_empty_text": 0,
        "skipped_unknown_case": 0,
        "skipped_non_ok_transcript": 0,
    }
    if not csv_path.exists():
        return [], meta

    df = read_csv_with_fallback(csv_path)
    records: list[dict[str, str]] = []

    for row in df.fillna("").to_dict("records"):
        transcript_status = normalize_whitespace(row.get("transcript_status")).lower()
        transcript_text = normalize_whitespace(row.get("transcript_text"))
        if transcript_status and transcript_status != "ok":
            meta["skipped_non_ok_transcript"] = int(meta["skipped_non_ok_transcript"]) + 1
            continue
        if not transcript_text:
            meta["skipped_empty_text"] = int(meta["skipped_empty_text"]) + 1
            continue

        channel_handle = normalize_whitespace(row.get("channel_handle"))
        channel_title = normalize_whitespace(row.get("channel_title"))
        case = classify_case(channel_handle, channel_title)
        if not case:
            meta["skipped_unknown_case"] = int(meta["skipped_unknown_case"]) + 1
            continue

        title = normalize_whitespace(row.get("video_title"))
        fecha_publicacion, fecha_publicacion_date = parse_datetime_fields(row.get("video_published_at"))
        video_id = normalize_whitespace(row.get("video_id"))
        url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
        records.append(
            {
                "fecha_semana": since,
                "nombre_semana": week_dir.name,
                "caso": case,
                "caso_label": CASE_LABELS[case],
                "red_social": "youtube",
                "red_social_label": NETWORK_LABELS["youtube"],
                "tipo_publicacion": "video_youtube",
                "cuenta_origen": channel_handle or channel_title,
                "autor": channel_title,
                "titulo": title,
                "texto_publicacion": transcript_text,
                "texto_para_analisis": build_text_for_analysis(title, transcript_text),
                "url_publicacion": url,
                "id_publicacion": video_id or title[:120],
                "fecha_publicacion": fecha_publicacion,
                "fecha_publicacion_date": fecha_publicacion_date,
                "archivo_origen": str(csv_path),
            }
        )

    meta["records"] = len(records)
    return records, meta


def consolidate_records(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, object]]:
    loaders = [
        load_twitter_records(Path(args.twitter_dir), args.since),
        load_facebook_records(Path(args.facebook_dir), args.since),
        load_youtube_records(Path(args.youtube_dir), args.since),
    ]

    source_meta: dict[str, object] = {}
    frames: list[pd.DataFrame] = []
    for records, meta in loaders:
        source_meta[str(meta["source"])] = meta
        if records:
            frames.append(pd.DataFrame(records, columns=COMMON_COLUMNS))

    if not frames:
        raise FileNotFoundError(
            "No se encontraron publicaciones institucionales. "
            "Se esperaban CSVs semanales de Twitter, Facebook o YouTube."
        )

    df = pd.concat(frames, ignore_index=True)
    dedupe_key = (
        df["red_social"].fillna("")
        + "||"
        + df["id_publicacion"].fillna("")
        + "||"
        + df["texto_para_analisis"].fillna("").str[:200]
    )
    df = df.assign(_dedupe_key=dedupe_key).drop_duplicates(subset=["_dedupe_key"]).drop(columns=["_dedupe_key"])
    df = df.sort_values(
        by=["caso", "fecha_publicacion_date", "red_social", "cuenta_origen"],
        ascending=[True, False, True, True],
        na_position="last",
    ).reset_index(drop=True)
    return df, source_meta


def ordered_cases_from_df(df: pd.DataFrame) -> list[str]:
    available = {case for case in df["caso"].fillna("").astype(str).tolist() if case}
    return [case for case in CASE_ORDER if case in available]


def build_stats(df: pd.DataFrame, ordered_cases: list[str]) -> dict[str, object]:
    total_publicaciones = int(len(df))
    por_caso = {
        case: int(count)
        for case, count in df.groupby("caso").size().sort_index().items()
    }
    por_red = {
        network: int(count)
        for network, count in df.groupby("red_social").size().sort_index().items()
    }
    por_caso_y_red = {}
    grouped = df.groupby(["caso", "red_social"]).size()
    for (case, network), count in grouped.items():
        por_caso_y_red[f"{case}::{network}"] = int(count)

    return {
        "total_publicaciones": total_publicaciones,
        "casos_ordenados": ordered_cases,
        "por_caso": por_caso,
        "por_red": por_red,
        "por_caso_y_red": por_caso_y_red,
    }


def build_summary_block(stats: dict[str, object], ordered_cases: list[str]) -> str:
    lines = ["Resumen cuantitativo del corpus:"]
    lines.append(f"- Total de publicaciones institucionales: {stats['total_publicaciones']}")

    por_caso = stats.get("por_caso", {})
    for case in ordered_cases:
        lines.append(f"- {CASE_LABELS.get(case, case)}: {int(por_caso.get(case, 0))}")

    por_red = stats.get("por_red", {})
    for network in ("twitter", "facebook", "youtube"):
        lines.append(f"- {NETWORK_LABELS[network]}: {int(por_red.get(network, 0))}")

    lines.append("- Distribucion por caso y red:")
    por_caso_y_red = stats.get("por_caso_y_red", {})
    for case in ordered_cases:
        counts = []
        for network in ("twitter", "facebook", "youtube"):
            counts.append(f"{NETWORK_LABELS[network]}={int(por_caso_y_red.get(f'{case}::{network}', 0))}")
        lines.append(f"  - {CASE_LABELS.get(case, case)}: {', '.join(counts)}")
    return "\n".join(lines)


def format_corpus_record(row: dict[str, str], max_doc_chars: int) -> str:
    text = normalize_whitespace(row.get("texto_para_analisis"))
    if max_doc_chars > 0 and len(text) > max_doc_chars:
        text = text[:max_doc_chars].rstrip() + " [TRUNCADO]"

    lines = [
        f"CASO: {row.get('caso_label', '')}",
        f"RED: {row.get('red_social_label', '')}",
        f"CUENTA: {row.get('cuenta_origen', '')}",
        f"FECHA: {row.get('fecha_publicacion_date') or row.get('fecha_publicacion') or ''}",
    ]
    if row.get("titulo"):
        lines.append(f"TITULO: {row.get('titulo')}")
    if row.get("url_publicacion"):
        lines.append(f"URL: {row.get('url_publicacion')}")
    lines.append(f"TEXTO: {text}")
    return "\n".join(lines)


def sample_corpus(
    df: pd.DataFrame,
    ordered_cases: list[str],
    max_chars: int,
    seed: int,
    max_doc_chars: int,
) -> tuple[str, dict[str, object]]:
    rows = df.to_dict("records")
    formatted = [(row, format_corpus_record(row, max_doc_chars)) for row in rows]
    separators = "\n\n---\n\n"
    original_chars = sum(len(text) for _, text in formatted) + max(0, len(formatted) - 1) * len(separators)

    if original_chars <= max_chars:
        corpus = separators.join(text for _, text in formatted)
        return corpus, {
            "sampled": False,
            "original_chars": original_chars,
            "final_chars": len(corpus),
            "original_docs": len(formatted),
            "final_docs": len(formatted),
        }

    rng = random.Random(seed)
    grouped: dict[str, list[tuple[dict[str, str], str]]] = defaultdict(list)
    for row, text in formatted:
        grouped[str(row.get("caso") or "sin_caso")].append((row, text))

    selected: list[tuple[dict[str, str], str]] = []
    leftovers: list[tuple[dict[str, str], str]] = []
    approx_case_quota = max_chars // max(len(ordered_cases), 1)

    for case in ordered_cases:
        items = grouped.get(case, [])[:]
        rng.shuffle(items)
        case_chars = 0
        for row, text in items:
            text_size = len(text) + len(separators)
            if case_chars == 0 or case_chars + text_size <= approx_case_quota:
                selected.append((row, text))
                case_chars += text_size
            else:
                leftovers.append((row, text))

    rng.shuffle(leftovers)
    current_chars = sum(len(text) for _, text in selected) + max(0, len(selected) - 1) * len(separators)
    for row, text in leftovers:
        extra = len(text) + (len(separators) if selected else 0)
        if current_chars + extra > max_chars and selected:
            continue
        selected.append((row, text))
        current_chars += extra

    if not selected and formatted:
        selected.append(formatted[0])

    corpus = separators.join(text for _, text in selected)
    return corpus, {
        "sampled": True,
        "original_chars": original_chars,
        "final_chars": len(corpus),
        "original_docs": len(formatted),
        "final_docs": len(selected),
        "selected_by_case": dict(Counter(str(row.get("caso") or "sin_caso") for row, _ in selected)),
    }


def build_case_json_schema_lines(ordered_cases: list[str]) -> tuple[str, str]:
    summary_lines = []
    theme_lines = []
    for case in ordered_cases:
        label = CASE_LABELS[case]
        summary_lines.append(
            "    {\n"
            f'      "caso": "{case}",\n'
            f'      "nombre": "{label}",\n'
            '      "descripcion_general": "Resumen ejecutivo breve del enfoque de comunicacion."\n'
            "    }"
        )
        theme_lines.append(f'        "{case}": "Como aparece el tema en {label}."')
    return ",\n".join(summary_lines), ",\n".join(theme_lines)


def build_prompt(since: str, stats: dict[str, object], ordered_cases: list[str]) -> str:
    dt = datetime.strptime(since, "%Y-%m-%d")
    month_label = MONTH_NAMES[dt.month]
    year_label = dt.year
    summary_block = build_summary_block(stats, ordered_cases)
    case_list = "\n".join(
        f"{idx}. {CASE_LABELS[case]}" for idx, case in enumerate(ordered_cases, 1)
    )
    summary_schema, theme_focus_schema = build_case_json_schema_lines(ordered_cases)

    return f"""
Analiza publicaciones institucionales de la semana correspondientes a estos casos:
{case_list}

El corpus mezcla publicaciones institucionales de Twitter/X, Facebook y YouTube. Tu tarea es identificar los temas de comunicacion que aparecen en esas publicaciones y diferenciar claramente el enfoque de cada caso.

{summary_block}

OBJETIVO ANALITICO:
- Construir un catalogo comun de EXACTAMENTE {THEME_COUNT} temas transversales que describan la agenda institucional observada.
- Explicar brevemente en que consiste cada tema.
- Diferenciar como aparece cada tema en cada caso.
- Asignar un porcentaje a cada tema para cada caso usando como base la proporcion relativa de publicaciones institucionales asociadas a ese tema.
- El resultado debe servir para dos productos: un reporte descriptivo de temas y una tabla CSV de porcentajes por tema para cada caso.

REGLAS:
- Usa el mismo catalogo de temas para todos los casos.
- Para cada caso, los porcentajes deben sumar 100.
- Si un tema no aparece practicamente en un caso, puedes usar 0.0.
- No uses engagement ni importancia mediatica como criterio de porcentaje; usa frecuencia relativa dentro del corpus de publicaciones institucionales.
- Si el mismo mensaje aparece replicado en varias redes, consideralo parte del mismo tema, pero manten su presencia como publicaciones distintas si estan efectivamente repetidas en redes diferentes.
- Escribe todo en espanol.
- No inventes temas que no esten sustentados por el corpus.

SALIDA OBLIGATORIA:
Devuelve SOLO un JSON valido, sin markdown, sin comentarios, sin texto adicional, con esta estructura exacta:
{{
  "titulo": "ANALISIS TEMATICO DE PUBLICACIONES INSTITUCIONALES DE NAUCALPAN - {month_label} DE {year_label}",
  "resumen_casos": [
{summary_schema}
  ],
  "temas": [
    {{
      "tema": "NOMBRE DEL TEMA EN MAYUSCULAS",
      "descripcion": "Descripcion breve del tema.",
      "enfoques": {{
{theme_focus_schema}
      }},
      "porcentajes": {{
{", ".join(f'"{case}": 0.0' for case in ordered_cases)}
      }}
    }}
  ]
}}

RESTRICCIONES DE FORMATO:
- EXACTAMENTE {THEME_COUNT} elementos en "temas".
- "tema" siempre en MAYUSCULAS.
- "descripcion" y cada valor de "enfoques" deben ser breves y concretos.
- Los porcentajes deben expresarse como numeros, no como texto, con uno o dos decimales si hace falta.
- No devuelvas bloques de codigo ni fences.
""".strip()


def generate_analysis(api_key: str, model: str, prompt: str, corpus_text: str) -> tuple[str, dict[str, int | str]]:
    client = anthropic.Anthropic(api_key=api_key)
    message_content = f"{prompt}\n\n=== CORPUS PARA ANALISIS ===\n\n{corpus_text}"

    log_message("🚀 Enviando corpus de publicaciones institucionales a Claude API...")
    response = client.messages.create(
        model=model,
        max_tokens=5000,
        messages=[{"role": "user", "content": message_content}],
    )

    analysis_text = "\n".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    ).strip()
    usage = {
        "model": model,
        "input_tokens": int(getattr(response.usage, "input_tokens", 0)),
        "output_tokens": int(getattr(response.usage, "output_tokens", 0)),
    }
    return analysis_text, usage


def extract_json_payload(raw_text: str) -> dict[str, object]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("Claude no devolvio un objeto JSON interpretable.")

    return json.loads(match.group(0))


def to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = normalize_whitespace(value).replace("%", "")
    if not text:
        return 0.0
    return float(text)


def normalize_percentages(themes: list[dict[str, object]], case: str) -> None:
    values = [to_float(theme.get("porcentajes", {}).get(case)) for theme in themes]
    total = sum(values)
    if total <= 0:
        for theme in themes:
            theme.setdefault("porcentajes", {})[case] = 0.0
        return

    normalized = [round((value / total) * 100.0, 1) for value in values]
    delta = round(100.0 - sum(normalized), 1)
    normalized[-1] = round(normalized[-1] + delta, 1)
    for theme, value in zip(themes, normalized):
        theme.setdefault("porcentajes", {})[case] = value


def normalize_analysis_payload(payload: dict[str, object], ordered_cases: list[str]) -> dict[str, object]:
    temas = payload.get("temas")
    if not isinstance(temas, list) or len(temas) != THEME_COUNT:
        raise ValueError(f"La respuesta de Claude debe incluir exactamente {THEME_COUNT} temas.")

    resumen_casos = payload.get("resumen_casos")
    if not isinstance(resumen_casos, list):
        resumen_casos = []

    summary_map: dict[str, dict[str, str]] = {}
    for item in resumen_casos:
        if not isinstance(item, dict):
            continue
        case = normalize_whitespace(item.get("caso"))
        if case not in ordered_cases:
            continue
        summary_map[case] = {
            "caso": case,
            "nombre": normalize_whitespace(item.get("nombre")) or CASE_LABELS.get(case, case),
            "descripcion_general": normalize_whitespace(item.get("descripcion_general")),
        }

    normalized_themes: list[dict[str, object]] = []
    for idx, item in enumerate(temas, 1):
        if not isinstance(item, dict):
            raise ValueError(f"El tema #{idx} no tiene formato de objeto JSON.")

        enfoques_raw = item.get("enfoques")
        porcentajes_raw = item.get("porcentajes")
        if not isinstance(enfoques_raw, dict):
            enfoques_raw = {}
        if not isinstance(porcentajes_raw, dict):
            porcentajes_raw = {}

        normalized_themes.append(
            {
                "orden": idx,
                "tema": normalize_whitespace(item.get("tema")).upper(),
                "descripcion": normalize_whitespace(item.get("descripcion")),
                "enfoques": {
                    case: normalize_whitespace(enfoques_raw.get(case))
                    for case in ordered_cases
                },
                "porcentajes": {
                    case: to_float(porcentajes_raw.get(case))
                    for case in ordered_cases
                },
            }
        )

    for case in ordered_cases:
        normalize_percentages(normalized_themes, case)

    ordered_summary = []
    for case in ordered_cases:
        ordered_summary.append(
            summary_map.get(
                case,
                {
                    "caso": case,
                    "nombre": CASE_LABELS[case],
                    "descripcion_general": "",
                },
            )
        )

    return {
        "titulo": normalize_whitespace(payload.get("titulo")) or "ANALISIS TEMATICO DE PUBLICACIONES INSTITUCIONALES DE NAUCALPAN",
        "casos_ordenados": ordered_cases,
        "resumen_casos": ordered_summary,
        "temas": normalized_themes,
    }


def build_markdown_report(analysis: dict[str, object]) -> str:
    lines = [f"# {analysis['titulo']}", "", "## Resumen por caso", ""]

    for case_summary in analysis["resumen_casos"]:
        lines.append(f"### {case_summary['nombre']}")
        lines.append(case_summary["descripcion_general"] or "Sin descripcion general provista.")
        lines.append("")

    lines.append("## Temas transversales")
    lines.append("")
    for item in analysis["temas"]:
        lines.append(f"**{item['orden']}. {item['tema']}**")
        lines.append(item["descripcion"] or "Sin descripcion.")
        for case in analysis["casos_ordenados"]:
            lines.append(
                f"- {CASE_LABELS[case]}: {item['enfoques'].get(case, '')} "
                f"({float(item['porcentajes'].get(case, 0.0)):.1f}%)"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_theme_table(analysis: dict[str, object]) -> pd.DataFrame:
    rows = []
    for item in analysis["temas"]:
        row = {
            "orden": int(item["orden"]),
            "tema": item["tema"],
            "descripcion_tema": item["descripcion"],
        }
        for case in analysis["casos_ordenados"]:
            row[f"enfoque_{case}"] = item["enfoques"].get(case, "")
            row[f"porcentaje_{case}"] = float(item["porcentajes"].get(case, 0.0))
        rows.append(row)
    return pd.DataFrame(rows)


def build_percentages_table(analysis: dict[str, object]) -> pd.DataFrame:
    rows = []
    for item in analysis["temas"]:
        for case in analysis["casos_ordenados"]:
            rows.append(
                {
                    "orden": int(item["orden"]),
                    "tema": item["tema"],
                    "descripcion_tema": item["descripcion"],
                    "caso": case,
                    "caso_label": CASE_LABELS[case],
                    "enfoque_caso": item["enfoques"].get(case, ""),
                    "porcentaje": float(item["porcentajes"].get(case, 0.0)),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()

    log_message("🏛️ CONSOLIDADO Y ANALISIS DE PUBLICACIONES INSTITUCIONALES")

    datos_week_dir = weekly_dir(Path(args.datos_dir), args.since, "Datos")
    claude_week_dir = weekly_dir(Path(args.output_dir), args.since, "Claude")
    datos_tag = build_report_tag(args.since, "Datos")
    claude_tag = build_report_tag(args.since, "Claude")

    df, source_meta = consolidate_records(args)
    ordered_cases = ordered_cases_from_df(df)
    stats = build_stats(df, ordered_cases)

    consolidated_csv_path = datos_week_dir / f"{ensure_tagged_name('publicaciones_institucionales_redes', datos_tag)}.csv"
    datos_week_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(consolidated_csv_path, index=False, encoding="utf-8-sig")
    log_message(f"📄 CSV consolidado generado: {consolidated_csv_path}")

    prompt_text = build_prompt(args.since, stats, ordered_cases)
    corpus_text, sampling_stats = sample_corpus(
        df,
        ordered_cases,
        args.max_corpus_chars,
        args.sample_seed,
        args.max_doc_chars,
    )

    claude_week_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = claude_week_dir / f"{ensure_tagged_name('prompt_publicaciones_institucionales', claude_tag)}.txt"
    corpus_path = claude_week_dir / f"{ensure_tagged_name('corpus_publicaciones_institucionales', claude_tag)}.txt"
    metadata_path = claude_week_dir / f"{ensure_tagged_name('metadata_publicaciones_institucionales', claude_tag)}.json"
    write_text(prompt_path, prompt_text + "\n")
    write_text(corpus_path, corpus_text.strip() + "\n")
    save_json(
        metadata_path,
        {
            "since": args.since,
            "before": args.before,
            "ordered_cases": ordered_cases,
            "consolidated_csv": str(consolidated_csv_path),
            "source_meta": source_meta,
            "stats": stats,
            "sampling": sampling_stats,
            "prepare_only": bool(args.prepare_only),
        },
    )
    log_message(f"🧠 Prompt guardado en: {prompt_path}")
    log_message(f"📚 Corpus guardado en: {corpus_path}")

    if args.prepare_only:
        log_message("🧪 Modo prepare-only: no se llamo a Claude")
        return

    api_key = os.getenv(API_ENV_NAME, "").strip()
    if not api_key:
        raise SystemExit(
            f"No se encontro {API_ENV_NAME}. Define la variable en .env.local o en el entorno antes de ejecutar este script."
        )

    raw_response, usage = generate_analysis(api_key, args.model, prompt_text, corpus_text)
    raw_response_path = claude_week_dir / f"{ensure_tagged_name('respuesta_cruda_publicaciones_institucionales', claude_tag)}.txt"
    write_text(raw_response_path, raw_response.strip() + "\n")

    parsed = extract_json_payload(raw_response)
    normalized = normalize_analysis_payload(parsed, ordered_cases)

    report_md_path = claude_week_dir / f"{ensure_tagged_name('analisis_publicaciones_institucionales', claude_tag)}.md"
    report_json_path = claude_week_dir / f"{ensure_tagged_name('analisis_publicaciones_institucionales', claude_tag)}.json"
    table_csv_path = claude_week_dir / f"{ensure_tagged_name('tabla_temas_publicaciones_institucionales', claude_tag)}.csv"
    percentages_csv_path = claude_week_dir / f"{ensure_tagged_name('porcentajes_temas_publicaciones_institucionales', claude_tag)}.csv"

    markdown_report = build_markdown_report(normalized)
    theme_table = build_theme_table(normalized)
    percentages_table = build_percentages_table(normalized)

    write_text(report_md_path, markdown_report)
    save_json(report_json_path, normalized)
    theme_table.to_csv(table_csv_path, index=False, encoding="utf-8-sig")
    percentages_table.to_csv(percentages_csv_path, index=False, encoding="utf-8-sig")

    save_json(
        metadata_path,
        {
            "since": args.since,
            "before": args.before,
            "ordered_cases": ordered_cases,
            "consolidated_csv": str(consolidated_csv_path),
            "source_meta": source_meta,
            "stats": stats,
            "sampling": sampling_stats,
            "prepare_only": False,
            "usage": usage,
            "raw_response_path": str(raw_response_path),
            "analysis_json_path": str(report_json_path),
            "analysis_markdown_path": str(report_md_path),
            "table_csv_path": str(table_csv_path),
            "percentages_csv_path": str(percentages_csv_path),
        },
    )

    log_message(f"✅ Analisis Markdown guardado en: {report_md_path}")
    log_message(f"✅ Analisis JSON guardado en: {report_json_path}")
    log_message(f"✅ Tabla CSV guardada en: {table_csv_path}")
    log_message(f"✅ CSV de porcentajes guardado en: {percentages_csv_path}")


if __name__ == "__main__":
    main()
