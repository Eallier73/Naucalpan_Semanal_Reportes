#!/usr/bin/env python3
"""Consolida el historico tabular local para el SNA de Naucalpan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "SNA" / "Datos" / "naucalpan_datos_tabulares_consolidados.csv"
DEFAULT_LAST_TWO_WEEKS_OUTPUT = (
    REPO_ROOT / "SNA" / "Datos" / "naucalpan_datos_tabulares_ultimas_2_semanas.csv"
)
SOURCE_ROOTS: list[tuple[Path, str]] = [(REPO_ROOT, "")]

URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
MENTION_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{1,50})")
HASHTAG_RE = re.compile(r"(?<!\w)#([\wÀ-ÿ]{1,80})", re.UNICODE)
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF"
    "\U0001FA70-\U0001FAFF\U00002600-\U000026FF"
    "\U00002700-\U000027BF\U0001F1E0-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)
WEEK_RE = re.compile(r"(20\d{2}_W\d{2})")
DATE_PREFIX_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
MEDIA_NAME_ALIASES = {
    "el_sol_de_mexico": "El Sol de México",
    "milenio": "Milenio",
}

OUTPUT_COLUMNS = [
    "id", "plataforma", "tipo_registro", "usuario", "semana", "semanas_origen",
    "fecha", "texto_original", "texto_limpio", "urls_extraidas",
    "menciones_extraidas", "hashtags_extraidos", "emojis_extraidos",
    "idioma_detectado", "likes", "comentarios", "shares", "vistas", "es_reply",
    "url_origen", "url_contexto", "query_busqueda", "titulo_contexto",
    "autor_contexto", "archivo_origen", "archivos_origen", "ruta_origen",
    "n_apariciones_descarga", "clave_deduplicacion", "datos_originales_json",
]


def text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def integer(value: Any) -> int:
    try:
        if value is None or pd.isna(value):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def boolean(value: Any) -> bool:
    return text(value).lower() in {"1", "true", "si", "sí", "yes", "y", "t"}


def first(row: pd.Series, *names: str) -> str:
    for name in names:
        if name in row:
            value = text(row.get(name))
            if value:
                return value
    return ""


def normalize_date(value: Any) -> str:
    raw = text(value)
    if not raw:
        return ""
    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    if pd.isna(parsed):
        return raw
    return parsed.isoformat().replace("+00:00", "Z")


def source_relative(path: Path) -> Path:
    for root, label in SOURCE_ROOTS:
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        return Path(label) / relative if label else relative
    return Path("externo") / path.name


def week_from_path(path: Path) -> str:
    relative = source_relative(path)
    week_match = WEEK_RE.search(str(relative))
    if week_match:
        return week_match.group(1)
    date_match = DATE_PREFIX_RE.search(str(relative))
    if not date_match:
        return ""
    parsed = pd.to_datetime(date_match.group(1), errors="coerce")
    if pd.isna(parsed):
        return ""
    iso = parsed.isocalendar()
    return f"{iso.year}_W{iso.week:02d}"


def week_from_date_or_path(value: Any, path: Path) -> str:
    """Usa la fecha real del registro y recurre a la ruta solo como respaldo."""
    parsed = pd.to_datetime(text(value), errors="coerce", utc=True)
    if not pd.isna(parsed):
        iso = parsed.isocalendar()
        return f"{iso.year}_W{iso.week:02d}"
    return week_from_path(path)


def stable_hash(*values: Any) -> str:
    raw = "|".join(text(value) for value in values)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def slug(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", text(value).lower())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_") or "sin_query"


def clean_and_extract(value: Any) -> dict[str, str]:
    raw = text(value)
    clean_chars = []
    for char in raw.replace("\ufffd", " "):
        if unicodedata.category(char).startswith("C") and char not in "\t\n\r":
            clean_chars.append(" ")
        else:
            clean_chars.append(char)
    clean = "".join(clean_chars)

    def unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(v for v in values if v))

    urls = unique([u.rstrip(".,;:!?)") for u in URL_RE.findall(clean)])
    mentions = unique(MENTION_RE.findall(clean))
    hashtags = unique(HASHTAG_RE.findall(clean))
    emojis = unique(EMOJI_RE.findall(clean))
    return {
        "texto_limpio": clean,
        "urls_extraidas": " ".join(urls),
        "menciones_extraidas": " ".join(mentions),
        "hashtags_extraidos": " ".join(hashtags),
        "emojis_extraidos": " ".join(emojis),
    }


def raw_json(row: pd.Series) -> str:
    data = {}
    for key, value in row.items():
        if value is None or pd.isna(value):
            data[str(key)] = None
        elif hasattr(value, "item"):
            data[str(key)] = value.item()
        else:
            data[str(key)] = value
    return json.dumps(data, ensure_ascii=False, default=str, separators=(",", ":"))


def base_record(
    row: pd.Series,
    path: Path,
    plataforma: str,
    tipo_registro: str,
    usuario: str,
    fecha: str,
    contenido: str,
    stable_key: str,
    **extra: Any,
) -> dict[str, Any]:
    relative = source_relative(path)
    week = week_from_date_or_path(fecha, path)
    clean = clean_and_extract(contenido)
    fallback_key = "|".join([plataforma, tipo_registro, usuario, fecha, contenido])
    dedup_key = f"{plataforma}:{tipo_registro}:{stable_key or hashlib.sha1(fallback_key.encode('utf-8')).hexdigest()}"
    record = {
        "plataforma": plataforma,
        "tipo_registro": tipo_registro,
        "usuario": usuario,
        "semana": week,
        "fecha": normalize_date(fecha),
        "texto_original": contenido,
        **clean,
        "idioma_detectado": "indeterminado",
        "likes": 0,
        "comentarios": 0,
        "shares": 0,
        "vistas": 0,
        "es_reply": False,
        "url_origen": "",
        "url_contexto": "",
        "query_busqueda": "",
        "titulo_contexto": "",
        "autor_contexto": "",
        "archivo_origen": path.name,
        "ruta_origen": str(relative),
        "clave_deduplicacion": dedup_key,
        "datos_originales_json": raw_json(row),
    }
    record.update(extra)
    return record


def adapt_twitter(row: pd.Series, path: Path, institutional: bool) -> dict[str, Any]:
    return base_record(
        row, path, "Twitter", "publicacion_institucional" if institutional else "comentario",
        first(row, "author"), first(row, "datetime_parsed_utc", "datetime"), first(row, "text"),
        first(row, "url"), likes=integer(row.get("likes")), comentarios=integer(row.get("replies")),
        shares=integer(row.get("retweets")), vistas=integer(row.get("views")),
        es_reply=boolean(row.get("is_reply")), url_origen=first(row, "url"),
        url_contexto=first(row, "in_reply_to_url"), query_busqueda=first(row, "query_used"),
    )


def adapt_facebook_comment(row: pd.Series, path: Path) -> dict[str, Any]:
    return base_record(
        row, path, "Facebook", "comentario", first(row, "autor"),
        first(row, "fecha_comentario"), first(row, "comentario_texto"),
        first(row, "url_comentario"), likes=integer(row.get("likes_comentario")),
        es_reply=boolean(row.get("es_respuesta")), url_origen=first(row, "url_comentario"),
        url_contexto=first(row, "post_url"),
    )


def adapt_facebook_post(row: pd.Series, path: Path) -> dict[str, Any]:
    return base_record(
        row, path, "Facebook", "publicacion_institucional",
        first(row, "autor", "page_handle"), first(row, "fecha_post", "fecha_post_date"),
        first(row, "post_texto"), first(row, "post_url"),
        likes=integer(row.get("reacciones_post")), comentarios=integer(row.get("num_comentarios_post")),
        url_origen=first(row, "post_url"), url_contexto=first(row, "page_url"),
        autor_contexto=first(row, "page_handle"),
    )


def adapt_youtube_comment(row: pd.Series, path: Path) -> dict[str, Any]:
    video_id = first(row, "video_id")
    comment_id = first(row, "comment_id")
    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
    comment_url = f"{video_url}&lc={comment_id}" if video_url and comment_id else comment_id
    return base_record(
        row, path, "YouTube", "comentario", first(row, "author"),
        first(row, "published_at"), first(row, "comment_text"), comment_id,
        likes=integer(row.get("like_count")), url_origen=comment_url, url_contexto=video_url,
        query_busqueda=first(row, "query"), titulo_contexto=first(row, "video_title"),
        autor_contexto=first(row, "channel_title"),
    )


def adapt_youtube_script(row: pd.Series, path: Path) -> dict[str, Any]:
    video_id = first(row, "video_id")
    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
    return base_record(
        row, path, "YouTube", "transcripcion", first(row, "channel_handle", "channel_title"),
        first(row, "video_published_at"), first(row, "transcript_text"), video_id,
        url_origen=video_url, titulo_contexto=first(row, "video_title"),
        autor_contexto=first(row, "channel_title"),
    )


def media_name(row: pd.Series) -> str:
    raw_name = first(row, "fuente")
    if raw_name:
        return MEDIA_NAME_ALIASES.get(slug(raw_name), raw_name)

    raw_url = first(row, "url", "url_google")
    hostname = urlparse(raw_url).hostname or ""
    return hostname.removeprefix("www.") or "Medio sin identificar"


def adapt_medio(row: pd.Series, path: Path) -> dict[str, Any]:
    url = first(row, "url", "url_google")
    titulo = first(row, "titulo")
    contenido = first(row, "texto") or titulo
    nombre_medio = media_name(row)
    return base_record(
        row, path, "Medios", "articulo", nombre_medio,
        first(row, "iso_date", "fecha"), contenido,
        url or stable_hash(nombre_medio, row.get("iso_date"), titulo, contenido),
        url_origen=url, url_contexto=url, titulo_contexto=titulo,
        autor_contexto=first(row, "autor"),
        query_busqueda=first(row, "origen"),
    )


def adapt_apify_social(
    row: pd.Series, path: Path, plataforma: str
) -> dict[str, Any]:
    return base_record(
        row,
        path,
        plataforma,
        first(row, "tipo_registro") or "mencion",
        first(row, "usuario"),
        first(row, "fecha"),
        first(row, "texto"),
        first(row, "id", "url"),
        likes=integer(row.get("likes")),
        comentarios=integer(row.get("comentarios")),
        shares=integer(row.get("shares")),
        vistas=integer(row.get("vistas")),
        es_reply=first(row, "tipo_registro") == "comentario",
        url_origen=first(row, "url"),
        url_contexto=first(row, "url_contexto", "input_url"),
        query_busqueda=first(row, "query_busqueda"),
        datos_originales_json=first(row, "datos_originales_json") or raw_json(row),
    )


SOURCES: list[tuple[str, str, Callable[[pd.Series, Path], dict[str, Any]]]] = [
    ("Twitter comentarios", "Twitter/*/*_comentarios.csv", lambda r, p: adapt_twitter(r, p, False)),
    ("Twitter institucionales", "Twitter/*/*_post_institucionales.csv", lambda r, p: adapt_twitter(r, p, True)),
    ("Facebook comentarios", "Facebook/*/*_comentarios.csv", adapt_facebook_comment),
    ("Facebook posts", "Facebook/*/*_posts.csv", adapt_facebook_post),
    ("YouTube comentarios", "Youtube/*/*_comentarios.csv", adapt_youtube_comment),
    ("YouTube transcripciones", "Youtube/*/*_scripts.csv", adapt_youtube_script),
    ("Medios", "Medios/*/*_Medios.csv", adapt_medio),
    (
        "Instagram",
        "Instagram/*/*_publicaciones.csv",
        lambda r, p: adapt_apify_social(r, p, "Instagram"),
    ),
    (
        "TikTok",
        "TikTok/*/*_publicaciones.csv",
        lambda r, p: adapt_apify_social(r, p, "TikTok"),
    ),
]


def read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig", low_memory=False, on_bad_lines="skip")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", low_memory=False, on_bad_lines="skip")


def latest_source_weeks(limit: int) -> list[str]:
    """Obtiene las semanas ISO más recientes presentes en las rutas fuente."""
    weeks = {
        week
        for _, pattern, _ in SOURCES
        for path in REPO_ROOT.glob(pattern)
        if (week := week_from_path(path))
    }
    return sorted(weeks)[-limit:]


def consolidate(
    last_weeks: int | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[str]]:
    selected_weeks = latest_source_weeks(last_weeks) if last_weeks else []
    if last_weeks and not selected_weeks:
        raise RuntimeError("No se encontraron semanas ISO en las rutas fuente.")
    if last_weeks and len(selected_weeks) < last_weeks:
        raise RuntimeError(
            f"Se solicitaron {last_weeks} semanas, pero solo hay "
            f"{len(selected_weeks)} disponible(s)."
        )
    if selected_weeks:
        print(
            f"[ALCANCE] Últimas {len(selected_weeks)} semanas disponibles: "
            + ", ".join(selected_weeks),
            flush=True,
        )

    records: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for family, pattern, adapter in SOURCES:
        paths = sorted(set(REPO_ROOT.glob(pattern)))
        if selected_weeks:
            paths = [path for path in paths if week_from_path(path) in selected_weeks]
        if paths:
            print(f"[FUENTE] {family}: {len(paths)} archivo(s)", flush=True)
        for index, path in enumerate(paths, 1):
            frame = read_csv(path)
            inventory.append({"familia": family, "archivo": str(path.relative_to(REPO_ROOT)), "filas": len(frame)})
            print(
                f"  [{index}/{len(paths)}] {path.relative_to(REPO_ROOT)} · {len(frame)} filas",
                flush=True,
            )
            for _, row in frame.iterrows():
                record = adapter(row, path)
                if selected_weeks and text(record.get("semana")) not in selected_weeks:
                    continue
                if text(record.get("texto_original")):
                    records.append(record)

    if not records:
        return pd.DataFrame(columns=OUTPUT_COLUMNS), inventory, selected_weeks

    print(
        f"[CONSOLIDAR] {len(records)} registros útiles; deduplicando descargas repetidas...",
        flush=True,
    )
    raw = pd.DataFrame(records)
    consolidated: list[dict[str, Any]] = []
    for _, group in raw.groupby("clave_deduplicacion", sort=False, dropna=False):
        selected = group.iloc[-1].to_dict()
        weeks = sorted({text(v) for v in group["semana"] if text(v)})
        files = list(dict.fromkeys(text(v) for v in group["archivo_origen"] if text(v)))
        selected["semanas_origen"] = "|".join(weeks)
        selected["archivos_origen"] = "|".join(files)
        selected["n_apariciones_descarga"] = len(group)
        selected["id"] = hashlib.sha1(str(selected["clave_deduplicacion"]).encode("utf-8")).hexdigest()[:20]
        consolidated.append(selected)

    print(f"[CONSOLIDAR] {len(consolidated)} registros únicos; ordenando salida...", flush=True)
    output = pd.DataFrame(consolidated)
    for column in OUTPUT_COLUMNS:
        if column not in output:
            output[column] = ""
    output = output[OUTPUT_COLUMNS]
    output = output.sort_values(["fecha", "plataforma", "tipo_registro", "id"], na_position="last").reset_index(drop=True)
    return output, inventory, selected_weeks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--last-weeks",
        type=int,
        metavar="N",
        help="Consolida solo las N semanas ISO más recientes disponibles.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Ruta de salida; si se omite, se elige según el alcance.",
    )
    args = parser.parse_args()
    if args.last_weeks is not None and args.last_weeks < 1:
        parser.error("--last-weeks debe ser mayor que cero")

    output_path = args.output
    if output_path is None:
        if args.last_weeks == 2:
            output_path = DEFAULT_LAST_TWO_WEEKS_OUTPUT
        elif args.last_weeks:
            output_path = (
                REPO_ROOT
                / "SNA"
                / "Datos"
                / f"naucalpan_datos_tabulares_ultimas_{args.last_weeks}_semanas.csv"
            )
        else:
            output_path = DEFAULT_OUTPUT

    print(f"Raíz local: {REPO_ROOT}", flush=True)
    print("Fuentes externas: desactivadas", flush=True)
    print("Periodico/: excluido del corpus SNA", flush=True)
    output, inventory, selected_weeks = consolidate(args.last_weeks)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False, encoding="utf-8")

    print(f"Archivo: {output_path}")
    print(
        "Alcance: "
        + (" | ".join(selected_weeks) if selected_weeks else "histórico completo")
    )
    print(f"Archivos fuente: {len(inventory)}")
    print(f"Filas fuente: {sum(item['filas'] for item in inventory)}")
    print(f"Filas consolidadas: {len(output)}")
    print("Por plataforma:")
    for platform, count in output["plataforma"].value_counts().items():
        print(f"  {platform}: {count}")
    print("Por tipo:")
    for kind, count in output["tipo_registro"].value_counts().items():
        print(f"  {kind}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
