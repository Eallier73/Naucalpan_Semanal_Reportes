from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path


def _normalize_date_label(run_date: str | date | datetime | None, fallback: str) -> str:
    if isinstance(run_date, datetime):
        iso = run_date.isocalendar()
        return f"{iso.year}_W{iso.week:02d}"
    if isinstance(run_date, date):
        iso = run_date.isocalendar()
        return f"{iso.year}_W{iso.week:02d}"
    if run_date:
        raw = str(run_date).strip()
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d")
            iso = dt.date().isocalendar()
            return f"{iso.year}_W{iso.week:02d}"
        except ValueError:
            pass
        m = re.match(r"^(\d{4})[-_]?W(\d{1,2})$", raw, flags=re.IGNORECASE)
        if m:
            year = int(m.group(1))
            week = int(m.group(2))
            if 1 <= week <= 53:
                return f"{year}_W{week:02d}"
        return raw
    return fallback


def _normalize_source_label(source: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", (source or "").strip())
    return normalized.strip("_") or "Reporte"


def build_report_tag(
    run_date: str | date | datetime | None,
    source: str,
    fallback: str = "sin_inicio",
) -> str:
    override = os.getenv("REPORT_TAG_OVERRIDE", "").strip()
    if override:
        return f"{override}_{_normalize_source_label(source)}"
    return f"{_normalize_date_label(run_date, fallback)}_{_normalize_source_label(source)}"


def build_output_dir(
    base_dir: str | Path,
    run_date: str | date | datetime | None,
    source: str,
    fallback: str = "sin_inicio",
) -> Path:
    return Path(base_dir) / build_report_tag(run_date, source, fallback=fallback)


def ensure_tagged_name(base_name: str, report_tag: str) -> str:
    if base_name.endswith(report_tag):
        return base_name
    return f"{base_name}_{report_tag}"
