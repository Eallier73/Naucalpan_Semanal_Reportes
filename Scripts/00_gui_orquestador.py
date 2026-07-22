#!/usr/bin/env python3
from contextlib import contextmanager
import importlib.util
import math
import os
import re
from queue import Empty, SimpleQueue
import shutil
import struct
import subprocess
import sys
import threading
import tempfile
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from time import monotonic
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
import wave

from subir_ia_export import REQUIRED_PIPELINE_CODES, export_week_to_subir_ia


def manual_load_dotenv(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip("'").strip('"')
        return True
    except Exception:
        return False


REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.local"
SCRIPTS_DIR = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv

    if ENV_FILE.exists():
        load_dotenv(str(ENV_FILE))
except ImportError:
    manual_load_dotenv(ENV_FILE)


def load_orchestrator_module():
    module_path = SCRIPTS_DIR / "00_orquestador_general.py"
    scripts_dir = str(SCRIPTS_DIR)
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)
    module_name = "naucalpan_orquestador"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar el módulo del orquestador: {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ORQUESTADOR = load_orchestrator_module()

PIPELINES = ORQUESTADOR.PIPELINES
PIPELINES_BY_CODE = ORQUESTADOR.PIPELINES_BY_CODE
DEFAULT_GLOBAL_ISO_WEEK = ORQUESTADOR.DEFAULT_GLOBAL_ISO_WEEK
iso_week_to_range = ORQUESTADOR.iso_week_to_range
build_pipeline = ORQUESTADOR.build_pipeline
render_command = ORQUESTADOR.render_command
weekly_output_dir_for_command = ORQUESTADOR.weekly_output_dir_for_command
_extract_flag_value = ORQUESTADOR._extract_flag_value
build_report_tag = ORQUESTADOR.build_report_tag


DEFAULT_GLOBAL_SINCE, DEFAULT_GLOBAL_BEFORE = iso_week_to_range(DEFAULT_GLOBAL_ISO_WEEK)
PERIOD_FOLDER_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})_al_(\d{4}-\d{2}-\d{2})$")

SNA_DATA_DIR = REPO_ROOT / "SNA" / "Datos"
SNA_HISTORICAL_CSV = SNA_DATA_DIR / "naucalpan_datos_tabulares_consolidados.csv"
SNA_LAST_TWO_WEEKS_CSV = SNA_DATA_DIR / "naucalpan_datos_tabulares_ultimas_2_semanas.csv"
SNA_LAST_WEEK_CSV = SNA_DATA_DIR / "naucalpan_datos_tabulares_ultima_semana.csv"
SNA_RESULTS_ROOT = REPO_ROOT / "SNA" / "Resultados"


def build_sna_run(scope: str) -> dict[str, object]:
    if scope == "historico":
        label = "material histórico"
        input_csv = SNA_HISTORICAL_CSV
        results_dir = SNA_RESULTS_ROOT / "historico"
        consolidate_args = ["--output", str(input_csv)]
        scope_short = "histórico"
        network_scope = "Naucalpan histórico"
        accounts_scope = "histórica"
        corpus_label = "histórico consolidado de Naucalpan"
        complete_name = "red_naucalpan_historico.html"
        accounts_name = "red_naucalpan_cuentas.html"
        positions_name = "red_naucalpan_posiciones.html"
        guided_complete_name = "red_naucalpan_historico_guiada.html"
        guided_accounts_name = "red_naucalpan_cuentas_guiada.html"
        guided_positions_name = "red_naucalpan_posiciones_guiada.html"
        log_name = "ultima_ejecucion.log"
    elif scope == "ultimas_2_semanas":
        label = "últimas 2 semanas"
        input_csv = SNA_LAST_TWO_WEEKS_CSV
        results_dir = SNA_RESULTS_ROOT / "ultimas_2_semanas"
        consolidate_args = ["--last-weeks", "2", "--output", str(input_csv)]
        scope_short = "de las últimas 2 semanas"
        network_scope = "Naucalpan · últimas 2 semanas"
        accounts_scope = "de las últimas 2 semanas"
        corpus_label = "últimas 2 semanas disponibles de Naucalpan"
        complete_name = "red_naucalpan_ultimas_2_semanas.html"
        accounts_name = "red_naucalpan_cuentas_ultimas_2_semanas.html"
        positions_name = "red_naucalpan_posiciones_ultimas_2_semanas.html"
        guided_complete_name = "red_naucalpan_ultimas_2_semanas_guiada.html"
        guided_accounts_name = "red_naucalpan_cuentas_ultimas_2_semanas_guiada.html"
        guided_positions_name = "red_naucalpan_posiciones_ultimas_2_semanas_guiada.html"
        log_name = "ultima_ejecucion_ultimas_2_semanas.log"
    elif scope == "ultima_semana":
        label = "última semana"
        input_csv = SNA_LAST_WEEK_CSV
        results_dir = SNA_RESULTS_ROOT / "ultima_semana"
        consolidate_args = ["--last-weeks", "1", "--output", str(input_csv)]
        scope_short = "de la última semana disponible"
        network_scope = "Naucalpan · última semana"
        accounts_scope = "de la última semana disponible"
        corpus_label = "última semana disponible de Naucalpan"
        complete_name = "red_naucalpan_ultima_semana.html"
        accounts_name = "red_naucalpan_cuentas_ultima_semana.html"
        positions_name = "red_naucalpan_posiciones_ultima_semana.html"
        guided_complete_name = "red_naucalpan_ultima_semana_guiada.html"
        guided_accounts_name = "red_naucalpan_cuentas_ultima_semana_guiada.html"
        guided_positions_name = "red_naucalpan_posiciones_ultima_semana_guiada.html"
        log_name = "ultima_ejecucion_ultima_semana.log"
    else:
        raise ValueError(f"Alcance SNA desconocido: {scope}")

    clusters_dir = results_dir / "clusters"
    accounts_dir = results_dir / "cuentas_clusters"
    steps = [
        ("Consolidar material local", "11_consolidar_historico_sna.py", consolidate_args),
        (
            "LDA SNA",
            "12_lda_sna.py",
            [
                "--input-csv", str(input_csv),
                "--output-dir", str(clusters_dir),
                "--k-min", "25", "--k-max", "35",
                "--selection-mode", "coherence",
            ],
        ),
        ("Evaluar calidad temática", "sna_topic_quality.py", ["--clusters-dir", str(clusters_dir)]),
        (
            "Subclusters Louvain",
            "12b_subclusters_louvain.py",
            ["--clusters-dir", str(clusters_dir), "--resolution", "1.4", "--min-sub-size", "3"],
        ),
        ("Diagnóstico de umbrales", "12c_diagnostico_umbrales.py", ["--clusters-dir", str(clusters_dir)]),
        (
            "Red completa",
            "12c_red_completa.py",
            ["--clusters-dir", str(clusters_dir), "--output-filename", complete_name, "--scope-label", scope_short],
        ),
        (
            "Cuentas por clusters",
            "18_cuentas_clusters.py",
            ["--clusters-dir", str(clusters_dir), "--output-dir", str(accounts_dir)],
        ),
        (
            "Red de cuentas",
            "12d_red_cuentas.py",
            [
                "--base-dir", str(results_dir), "--output-filename", accounts_name,
                "--scope-label", accounts_scope, "--corpus-label", corpus_label,
            ],
        ),
        (
            "Red de posiciones discursivas",
            "19_red_posiciones_discursivas.py",
            [
                "--base-dir", str(results_dir), "--input-csv", str(input_csv),
                "--output-filename", positions_name, "--scope-label", network_scope,
                "--corpus-label", corpus_label,
            ],
        ),
        (
            "Red completa guiada",
            "12c_red_completa_guiada.py",
            ["--clusters-dir", str(clusters_dir), "--output-filename", guided_complete_name, "--scope-label", scope_short],
        ),
        (
            "Red de cuentas guiada",
            "12d_red_cuentas_guiada.py",
            [
                "--base-dir", str(results_dir), "--output-filename", guided_accounts_name,
                "--scope-label", accounts_scope, "--corpus-label", corpus_label,
            ],
        ),
        (
            "Red de posiciones guiada",
            "19_red_posiciones_guiada.py",
            [
                "--base-dir", str(results_dir), "--input-csv", str(input_csv),
                "--output-filename", guided_positions_name, "--scope-label", network_scope,
                "--corpus-label", corpus_label, "--words-per-position", "35",
            ],
        ),
    ]
    guided_dir = clusters_dir / "red_guiada"
    final_outputs = [
        guided_dir / guided_complete_name,
        guided_dir / guided_accounts_name,
        guided_dir / guided_positions_name,
    ]
    return {
        "scope": scope,
        "label": label,
        "input_csv": input_csv,
        "results_dir": results_dir,
        "run_log": results_dir / log_name,
        "steps": steps,
        "final_outputs": final_outputs,
    }


def parse_date_range(since: str, before: str) -> tuple[str, str]:
    try:
        since_date = datetime.strptime((since or "").strip(), "%Y-%m-%d").date()
        before_date = datetime.strptime((before or "").strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Formato inválido. Usa YYYY-MM-DD.") from exc

    if since_date > before_date:
        raise ValueError("La fecha since no puede ser mayor que before.")

    return since_date.isoformat(), before_date.isoformat()


def find_selected_index(selected, code: str):
    for index, item in enumerate(selected):
        if item.code == code:
            return index
    return None


def ensure_pipeline_before(selected, before_code: str, after_code: str):
    before_idx = find_selected_index(selected, before_code)
    after_idx = find_selected_index(selected, after_code)
    if before_idx is None or after_idx is None or before_idx < after_idx:
        return selected

    item = selected.pop(before_idx)
    after_idx = find_selected_index(selected, after_code)
    insert_at = after_idx if after_idx is not None else len(selected)
    selected.insert(insert_at, item)
    return selected


def ensure_pipeline_after(selected, target_code: str, dependency_codes: list[str]):
    target_idx = find_selected_index(selected, target_code)
    dependency_indexes = [
        index for index, item in enumerate(selected) if item.code in dependency_codes
    ]
    if target_idx is None or not dependency_indexes or target_idx > max(dependency_indexes):
        return selected

    target = selected.pop(target_idx)
    insert_at = max(
        index for index, item in enumerate(selected) if item.code in dependency_codes
    ) + 1
    selected.insert(insert_at, target)
    return selected


def append_missing_pipelines(selected, pipeline_codes: list[str]) -> list:
    existing_codes = {item.code for item in selected}
    order = {pipe.code: index for index, pipe in enumerate(PIPELINES)}
    for code in pipeline_codes:
        if code not in existing_codes:
            selected.append(PIPELINES_BY_CODE[code])
            existing_codes.add(code)
    selected.sort(key=lambda item: order[item.code])
    return selected


PERIODO_DIR_FLAGS = {
    "--output-dir",
    "--base-dir",
    "--input-dir",
    "--twitter-dir",
    "--facebook-dir",
    "--youtube-dir",
    "--datos-dir",
}


def remap_periodic_path(raw_value: str, period_dir: Path) -> str:
    raw_path = Path(raw_value)
    try:
        relative = raw_path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return raw_value
    return str(period_dir / relative)


def discover_period_dirs(parent_dir: Path) -> list[tuple[str, str, Path]]:
    periods: list[tuple[str, str, Path]] = []
    for child in sorted(parent_dir.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        match = PERIOD_FOLDER_PATTERN.match(child.name)
        if not match:
            continue
        since, before = match.groups()
        periods.append((since, before, child))
    return sorted(periods, key=lambda item: (item[0], item[1], item[2].name))


def build_conjunto_range_tag(periods: list[tuple[str, str, Path]]) -> str:
    if not periods:
        raise ValueError("No hay periodos disponibles para construir el rango conjunto.")
    first_since = min(item[0] for item in periods).replace("-", "_")
    last_before = max(item[1] for item in periods).replace("-", "_")
    return f"{first_since}_{last_before}"


def rewrite_flag_value(cmd: list[str], flag: str, new_value: str) -> list[str]:
    rewritten = list(cmd)
    for index, token in enumerate(rewritten):
        if token == flag and index + 1 < len(rewritten):
            rewritten[index + 1] = new_value
            break
    return rewritten


class PromptCancelled(Exception):
    pass


class OrquestadorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Orquestador Pipelines Naucalpan")
        self.root.geometry("860x760")

        self.running_process = None
        self.stop_requested = False
        self.venv_python = self.detect_venv()
        self.log_queue = SimpleQueue()
        self.alarm_generation = 0
        self.audio_player = shutil.which("paplay") or shutil.which("aplay")
        self.stage_alarm_path = None
        self.final_alarm_path = None
        self.current_alarm_process = None

        if self.audio_player:
            self.stage_alarm_path = self.ensure_alarm_file("stage")
            self.final_alarm_path = self.ensure_alarm_file("final")

        self.setup_ui()
        self.root.after(100, self.process_log_queue)

    def detect_venv(self):
        for folder in [".venv", "venv"]:
            python_bin = REPO_ROOT / folder / "bin" / "python3"
            if not python_bin.exists():
                python_bin = REPO_ROOT / folder / "bin" / "python"
            if not python_bin.exists():
                python_bin = REPO_ROOT / folder / "Scripts" / "python.exe"
            if python_bin.exists():
                return str(python_bin)
        return sys.executable

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        venv_frame = ttk.LabelFrame(main_frame, text="Entorno de Ejecución", padding="10")
        venv_frame.pack(fill=tk.X, pady=5)

        self.use_venv_var = tk.BooleanVar(value=(self.venv_python != sys.executable))
        ttk.Checkbutton(
            venv_frame,
            text="Usar Entorno Virtual (.venv/venv)",
            variable=self.use_venv_var,
        ).grid(row=0, column=0, sticky=tk.W)

        self.venv_status_var = tk.StringVar(value=f"Ruta: {self.venv_python}")
        ttk.Label(
            venv_frame,
            textvariable=self.venv_status_var,
            foreground="gray",
            font=("Helvetica", 8),
        ).grid(row=1, column=0, sticky=tk.W, padx=20)

        # Nueva sección para Tipo de Pipeline y Carpeta Especial
        mode_select_frame = ttk.LabelFrame(main_frame, text="Modo de Pipeline", padding="10")
        mode_select_frame.pack(fill=tk.X, pady=5)

        self.pipeline_type_var = tk.StringVar(value="semanal")
        ttk.Radiobutton(mode_select_frame, text="Semanal (Estándar)", variable=self.pipeline_type_var, value="semanal").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Radiobutton(mode_select_frame, text="Periódico (Por carpetas)", variable=self.pipeline_type_var, value="periodico").grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Radiobutton(mode_select_frame, text="Conjunto (Todo unido)", variable=self.pipeline_type_var, value="conjunto").grid(row=0, column=2, sticky=tk.W, padx=5)

        ttk.Label(mode_select_frame, text="Carpeta Especial:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.special_folder_var = tk.StringVar()
        ttk.Entry(mode_select_frame, textvariable=self.special_folder_var, width=50).grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5)
        ttk.Button(mode_select_frame, text="Buscar...", command=self.browse_special_folder).grid(row=1, column=3, padx=5)

        date_frame = ttk.LabelFrame(main_frame, text="Configuración Temporal", padding="10")
        date_frame.pack(fill=tk.X, pady=5)

        ttk.Label(date_frame, text="Semana ISO (YYYY-Www):").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.iso_week_var = tk.StringVar(value=DEFAULT_GLOBAL_ISO_WEEK)
        ttk.Entry(date_frame, textvariable=self.iso_week_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(date_frame, text="Usar Semana", command=self.update_dates_from_week).grid(row=0, column=2, padx=5)

        ttk.Label(date_frame, text="Desde (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.since_var = tk.StringVar(value=DEFAULT_GLOBAL_SINCE)
        ttk.Entry(date_frame, textvariable=self.since_var, width=15).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(date_frame, text="Hasta (YYYY-MM-DD):").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.before_var = tk.StringVar(value=DEFAULT_GLOBAL_BEFORE)
        ttk.Entry(date_frame, textvariable=self.before_var, width=15).grid(row=1, column=3, sticky=tk.W, padx=5)

        options_frame = ttk.Frame(main_frame, padding="5")
        options_frame.pack(fill=tk.X)

        self.mode_var = tk.StringVar(value="all_networks")
        ttk.Radiobutton(
            options_frame,
            text="Modo Genérico (Defaults)",
            variable=self.mode_var,
            value="all_networks",
        ).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(
            options_frame,
            text="Modo Específico por Red",
            variable=self.mode_var,
            value="per_network",
        ).pack(side=tk.LEFT, padx=10)

        self.continue_error_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame,
            text="Continuar en error",
            variable=self.continue_error_var,
        ).pack(side=tk.LEFT, padx=10)

        sna_frame = ttk.LabelFrame(main_frame, text="Análisis SNA", padding="8")
        sna_frame.pack(fill=tk.X, pady=5)

        ttk.Label(
            sna_frame,
            text=(
                "Elige el alcance del análisis completo. Cada opción conserva sus "
                "propios datos, resultados y bitácora (Periodico excluido)."
            ),
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5)

        self.sna_history_button = ttk.Button(
            sna_frame,
            text="EJECUTAR SNA MATERIAL HISTÓRICO",
            command=lambda: self.start_sna_execution("historico"),
        )
        self.sna_history_button.grid(row=1, column=0, sticky=tk.EW, padx=5, pady=(7, 3))

        self.sna_recent_button = ttk.Button(
            sna_frame,
            text="EJECUTAR SNA DOS SEMANAS",
            command=lambda: self.start_sna_execution("ultimas_2_semanas"),
        )
        self.sna_recent_button.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=(7, 3))

        self.sna_last_week_button = ttk.Button(
            sna_frame,
            text="EJECUTAR SNA ÚLTIMA SEMANA",
            command=lambda: self.start_sna_execution("ultima_semana"),
        )
        self.sna_last_week_button.grid(
            row=2, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=3
        )
        sna_frame.columnconfigure(0, weight=1)
        sna_frame.columnconfigure(1, weight=1)

        ttk.Label(
            sna_frame,
            text=(
                "Histórico: SNA/Resultados/historico/ · Dos semanas: "
                "SNA/Resultados/ultimas_2_semanas/ · Última semana: "
                "SNA/Resultados/ultima_semana/"
            ),
            foreground="gray",
            font=("Helvetica", 8),
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5)

        control_frame = ttk.Frame(main_frame, padding="10")
        control_frame.pack(fill=tk.X)

        self.play_button = ttk.Button(control_frame, text="▶ PLAY / EJECUTAR", command=self.start_execution)
        self.play_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.stop_button = ttk.Button(control_frame, text="⏹ DETENER", command=self.stop_execution, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        pipeline_frame = ttk.LabelFrame(main_frame, text="Selección de Pipelines", padding="10")
        pipeline_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.pipeline_vars = {}
        canvas = tk.Canvas(pipeline_frame)
        scrollbar = ttk.Scrollbar(pipeline_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for pipe in PIPELINES:
            variable = tk.BooleanVar(value=False)
            self.pipeline_vars[pipe.code] = variable
            ttk.Checkbutton(scrollable_frame, text=f"{pipe.code}) {pipe.label}", variable=variable).pack(anchor=tk.W, pady=2)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        log_frame = ttk.LabelFrame(main_frame, text="Consola de Salida", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_area = scrolledtext.ScrolledText(
            log_frame,
            height=15,
            state=tk.DISABLED,
            bg="black",
            fg="lightgreen",
            font=("Courier", 10),
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def browse_special_folder(self):
        directory = filedialog.askdirectory(initialdir=str(REPO_ROOT))
        if directory:
            self.special_folder_var.set(directory)

    def update_dates_from_week(self):
        week = self.iso_week_var.get().strip()
        try:
            since, before = iso_week_to_range(week)
            self.since_var.set(since)
            self.before_var.set(before)
        except Exception as exc:
            messagebox.showerror("Error", f"Semana ISO inválida: {exc}")

    def log(self, message: str):
        self.log_queue.put(message)

    def process_log_queue(self):
        messages = []
        while True:
            try:
                messages.append(self.log_queue.get_nowait())
            except Empty:
                break

        if not messages:
            self.root.after(100, self.process_log_queue)
            return

        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, "\n".join(messages) + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)
        self.root.after(100, self.process_log_queue)

    def clear_log(self):
        def _clear():
            while True:
                try:
                    self.log_queue.get_nowait()
                except Empty:
                    break
            self.log_area.config(state=tk.NORMAL)
            self.log_area.delete(1.0, tk.END)
            self.log_area.config(state=tk.DISABLED)

        self.root.after(0, _clear)

    def ensure_alarm_file(self, kind: str) -> str | None:
        alarm_path = Path(tempfile.gettempdir()) / f"naucalpan_alarm_{kind}.wav"
        if not alarm_path.exists():
            self.write_alarm_wav(alarm_path, kind)
        return str(alarm_path)

    def write_alarm_wav(self, path: Path, kind: str):
        sample_rate = 22050
        duration_seconds = 5.0
        total_frames = int(sample_rate * duration_seconds)

        if kind == "stage":
            segments = [
                (0.00, 0.35, 880.0),
                (0.80, 1.15, 880.0),
                (1.60, 1.95, 880.0),
                (2.40, 2.75, 880.0),
                (3.20, 3.55, 880.0),
                (4.00, 4.35, 880.0),
            ]
        else:
            segments = [
                (0.00, 0.45, 660.0),
                (0.55, 1.00, 880.0),
                (1.15, 1.85, 990.0),
                (2.10, 2.55, 880.0),
                (2.70, 3.40, 1100.0),
                (3.65, 4.75, 1320.0),
            ]

        def envelope(position: float, start: float, end: float) -> float:
            attack = 0.03
            release = 0.08
            if position < start or position > end:
                return 0.0
            if position < start + attack:
                return (position - start) / attack
            if position > end - release:
                return max(0.0, (end - position) / release)
            return 1.0

        frames = bytearray()
        for frame_index in range(total_frames):
            t = frame_index / sample_rate
            sample = 0.0
            for start, end, freq in segments:
                env = envelope(t, start, end)
                if env:
                    sample += math.sin(2.0 * math.pi * freq * t) * env
            sample = max(-1.0, min(1.0, sample * 0.22))
            pcm = int(sample * 32767)
            frames.extend(struct.pack("<h", pcm))

        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(bytes(frames))

    def trigger_stage_alarm(self):
        self.play_alarm(self.stage_alarm_path)

    def trigger_final_alarm(self):
        self.play_alarm(self.final_alarm_path)

    def play_alarm(self, alarm_path: str | None):
        if not self.audio_player or not alarm_path:
            return
        self.alarm_generation += 1
        try:
            if self.current_alarm_process and self.current_alarm_process.poll() is None:
                self.current_alarm_process.terminate()
        except Exception:
            pass

        command = [self.audio_player, alarm_path]
        if Path(self.audio_player).name == "aplay":
            command = [self.audio_player, "-q", alarm_path]

        try:
            self.current_alarm_process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            self.current_alarm_process = None

    def get_selected_pipelines(self):
        selected = []
        order = {pipe.code: index for index, pipe in enumerate(PIPELINES)}
        for code, variable in self.pipeline_vars.items():
            if variable.get():
                selected.append(PIPELINES_BY_CODE[code])
        selected.sort(key=lambda item: order[item.code])
        return selected

    def validate_dependencies(self, selected):
        selected_codes = {item.code for item in selected}

        if "5" in selected_codes and "4" not in selected_codes:
            self.log("⚠️ Agregando Facebook Posts (4) como dependencia de Comentarios (5)")
            facebook_posts_spec = PIPELINES_BY_CODE["4"]
            insert_at = next((index for index, item in enumerate(selected) if item.code == "5"), 0)
            selected.insert(insert_at, facebook_posts_spec)

        selected = ensure_pipeline_before(selected, "4", "5")

        required_by_consolidador = {
            "7": "Claude",
            "8": "Influencia",
            "9": "Temas Guiados",
            "11": "Polaridad",
            "12": "Seguridad/Inseguridad",
        }
        for dep_code, dep_label in required_by_consolidador.items():
            selected_codes = {item.code for item in selected}
            if dep_code in selected_codes and "6" not in selected_codes:
                self.log(f"⚠️ Agregando Consolidador (6) como dependencia de {dep_label} ({dep_code})")
                insert_at = next((index for index, item in enumerate(selected) if item.code == dep_code), len(selected))
                selected.insert(insert_at, PIPELINES_BY_CODE["6"])

            selected = ensure_pipeline_before(selected, "6", dep_code)

        selected = ensure_pipeline_after(
            selected, "6", ["1", "2", "3", "4", "5", "14", "15"]
        )

        seen = set()
        unique_selected = []
        for item in selected:
            if item.code not in seen:
                unique_selected.append(item)
                seen.add(item.code)

        if "13" in seen:
            unique_selected = [item for item in unique_selected if item.code != "13"] + [PIPELINES_BY_CODE["13"]]

        return unique_selected

    def start_execution(self):
        if self.running_process is not None:
            messagebox.showwarning("En ejecución", "Ya hay un proceso en ejecución.")
            return

        selected = self.get_selected_pipelines()
        if not selected:
            messagebox.showwarning("Atención", "Selecciona al menos un pipeline para ejecutar.")
            return

        pipeline_type = self.pipeline_type_var.get()
        special_folder = self.special_folder_var.get().strip()

        if pipeline_type != "semanal" and any(item.code == "13" for item in selected):
            messagebox.showwarning(
                "Material para IA",
                "El pipeline 13 solo está disponible en el modo Semanal (Estándar).",
            )
            return

        if pipeline_type in ["periodico", "conjunto"] and not special_folder:
            messagebox.showwarning("Atención", "Debes seleccionar una Carpeta Especial para este tipo de pipeline.")
            return

        since = self.since_var.get().strip()
        before = self.before_var.get().strip()

        try:
            since, before = parse_date_range(since, before)
        except ValueError as exc:
            messagebox.showerror("Error de Fechas", str(exc))
            return

        self.clear_log()
        self.log(f"🚀 Iniciando ejecución: {since} al {before}")

        selected = self.validate_dependencies(selected)
        if pipeline_type == "conjunto":
            selected = append_missing_pipelines(selected, ["6", "7", "8", "9", "10", "11", "12"])
        self.log(f"Pipelines a ejecutar: {', '.join(spec.label for spec in selected)}")

        try:
            if pipeline_type == "semanal":
                prepared = self.prepare_pipelines(selected, since, before)
            elif pipeline_type == "periodico":
                prepared = self.prepare_pipelines(
                    selected,
                    "__PERIODO_SINCE__",
                    "__PERIODO_BEFORE__",
                    is_periodico=True,
                )
            elif pipeline_type == "conjunto":
                prepared = self.prepare_pipelines(selected, "conjunto", before, is_periodico=True)
            else:
                raise ValueError(f"Tipo de pipeline no soportado: {pipeline_type}")
        except PromptCancelled:
            self.log("⏹ Preparación cancelada por el usuario.")
            return
        except Exception as exc:
            messagebox.showerror("Error preparando ejecución", str(exc))
            self.log(f"💥 Error preparando ejecución: {exc}")
            return

        self.play_button.config(state=tk.DISABLED)
        self.sna_history_button.config(state=tk.DISABLED)
        self.sna_recent_button.config(state=tk.DISABLED)
        self.sna_last_week_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.root.update_idletasks()
        self.stop_requested = False

        thread = threading.Thread(
            target=self.run_pipelines_orchestrator,
            args=(prepared, since, before, pipeline_type, special_folder),
            daemon=True
        )
        thread.start()

    def build_python_exec(self) -> str:
        if self.use_venv_var.get() and self.venv_python:
            return self.venv_python
        return sys.executable

    def start_sna_execution(self, scope: str):
        if self.running_process is not None:
            messagebox.showwarning("En ejecución", "Ya hay un proceso en ejecución.")
            return

        run = build_sna_run(scope)
        steps = run["steps"]

        self.clear_log()
        self.log(f"🧠 Iniciando ejecución SNA: {run['label']}...")
        self.log("Etapas: " + ", ".join(label for label, _, _ in steps))

        self.play_button.config(state=tk.DISABLED)
        self.sna_history_button.config(state=tk.DISABLED)
        self.sna_recent_button.config(state=tk.DISABLED)
        self.sna_last_week_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.root.update_idletasks()
        self.stop_requested = False

        thread = threading.Thread(target=self.run_sna_pipelines, args=(run,), daemon=True)
        thread.start()

    def stop_execution(self):
        if self.running_process:
            self.stop_requested = True
            self.running_process.terminate()
            self.log("\n🛑 Solicitud de detención enviada...")

    def ask_string(self, title: str, prompt: str, initialvalue: str | None = None, show: str | None = None):
        value = simpledialog.askstring(title, prompt, parent=self.root, initialvalue=initialvalue, show=show)
        if value is None:
            raise PromptCancelled()
        return value.strip()

    def gui_prompt_text(self, label: str, default: str = "", allow_blank: bool = False) -> str:
        suffix = f" [{default}]" if default else ""
        while True:
            value = self.ask_string("Parámetro de Pipeline", f"{label}{suffix}:", initialvalue=default or "")
            if value:
                return value
            if default:
                return default
            if allow_blank:
                return ""
            messagebox.showwarning("Valor requerido", "Este valor es obligatorio.", parent=self.root)

    def gui_prompt_secret(self, label: str, env_name: str, required: bool = False) -> str:
        current = os.getenv(env_name, "")
        suffix = " [ya definido en entorno]" if current else ""
        while True:
            value = self.ask_string("Credencial de Pipeline", f"{label} ({env_name}){suffix}:", show="*")
            if value:
                return value
            if current:
                return current
            if not required:
                return ""
            messagebox.showwarning("Credencial requerida", f"Debes capturar {env_name} o definirlo en el entorno.", parent=self.root)

    def gui_prompt_choice(self, label: str, options: list[str], default: str) -> str:
        rendered = "/".join(options)
        while True:
            value = self.gui_prompt_text(f"{label} ({rendered})", default=default)
            if value in options:
                return value
            messagebox.showwarning("Opción inválida", f"Usa una de: {', '.join(options)}", parent=self.root)

    def gui_prompt_bool(self, label: str, default: bool) -> bool:
        default_text = "s" if default else "n"
        while True:
            raw = self.gui_prompt_text(f"{label} [s/n]", default=default_text).lower()
            if raw in {"s", "si", "sí", "y", "yes"}:
                return True
            if raw in {"n", "no"}:
                return False
            messagebox.showwarning("Respuesta inválida", "Responde s o n.", parent=self.root)

    def gui_prompt_int(self, label: str, default: int | None = None, allow_blank: bool = False) -> int | None:
        default_text = "" if default is None else str(default)
        while True:
            raw = self.gui_prompt_text(label, default=default_text, allow_blank=allow_blank)
            if raw == "" and allow_blank and default is None:
                return None
            try:
                return int(raw)
            except ValueError:
                messagebox.showwarning("Valor inválido", "Debe ser un entero.", parent=self.root)

    def gui_prompt_float(self, label: str, default: float | None = None, allow_blank: bool = False) -> float | None:
        default_text = "" if default is None else str(default)
        while True:
            raw = self.gui_prompt_text(label, default=default_text, allow_blank=allow_blank)
            if raw == "" and allow_blank and default is None:
                return None
            try:
                return float(raw)
            except ValueError:
                messagebox.showwarning("Valor inválido", "Debe ser un número.", parent=self.root)

    def gui_prompt_list(self, label: str, default: list[str] | None = None, allow_blank: bool = False) -> list[str]:
        default_text = ",".join(default or [])
        raw = self.gui_prompt_text(label, default=default_text, allow_blank=allow_blank)
        if raw == "":
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    @contextmanager
    def patch_orchestrator_prompts(self):
        original = {
            "prompt_text": ORQUESTADOR.prompt_text,
            "prompt_secret": ORQUESTADOR.prompt_secret,
            "prompt_choice": ORQUESTADOR.prompt_choice,
            "prompt_bool": ORQUESTADOR.prompt_bool,
            "prompt_int": ORQUESTADOR.prompt_int,
            "prompt_float": ORQUESTADOR.prompt_float,
            "prompt_list": ORQUESTADOR.prompt_list,
        }

        ORQUESTADOR.prompt_text = self.gui_prompt_text
        ORQUESTADOR.prompt_secret = self.gui_prompt_secret
        ORQUESTADOR.prompt_choice = self.gui_prompt_choice
        ORQUESTADOR.prompt_bool = self.gui_prompt_bool
        ORQUESTADOR.prompt_int = self.gui_prompt_int
        ORQUESTADOR.prompt_float = self.gui_prompt_float
        ORQUESTADOR.prompt_list = self.gui_prompt_list

        try:
            yield
        finally:
            for name, value in original.items():
                setattr(ORQUESTADOR, name, value)

    def prepare_pipelines(self, selected, since: str, before: str, is_periodico: bool = False):
        use_defaults = self.mode_var.get() == "all_networks"
        facebook_posts_csv = ""
        prepared = []

        self.log("🧩 Preparando comandos de ejecución...")
        with self.patch_orchestrator_prompts():
            for spec in selected:
                self.log(f"Preparando: {spec.label}")
                cmd, env = build_pipeline(
                    spec,
                    since,
                    before,
                    use_defaults=use_defaults,
                    facebook_posts_csv=facebook_posts_csv,
                    is_periodico=is_periodico,
                )
                prepared.append((spec, cmd, env))

        return prepared

    def run_pipelines_orchestrator(self, prepared, since, before, pipeline_type, special_folder):
        try:
            if pipeline_type == "semanal":
                self.run_pipelines(prepared, since)
            elif pipeline_type == "periodico":
                self.run_periodico(prepared, since, before, special_folder)
            elif pipeline_type == "conjunto":
                self.run_conjunto(prepared, before, special_folder)
        finally:
            self.root.after(0, self.finish_ui)

    def run_sna_pipelines(self, run):
        python_exec = self.build_python_exec()
        steps = run["steps"]
        results_dir = Path(run["results_dir"])
        run_log = Path(run["run_log"])
        final_outputs = [Path(path) for path in run["final_outputs"]]
        had_error = False
        success = False
        results_dir.mkdir(parents=True, exist_ok=True)
        log_handle = open(run_log, "w", encoding="utf-8", buffering=1)

        def sna_log(message: str) -> None:
            self.log(message)
            log_handle.write(message + "\n")

        try:
            sna_log(f"Inicio: {datetime.now().isoformat(timespec='seconds')}")
            sna_log(f"Intérprete: {python_exec}")
            sna_log(f"Alcance: {run['label']}; Periodico/ excluido")
            for label, script_name, args in steps:
                if self.stop_requested:
                    had_error = True
                    break

                cmd = [python_exec, str(SCRIPTS_DIR / script_name), *args]
                sna_log(f"\n--- Ejecutando SNA: {label} ---")
                sna_log(f"Comando: {render_command(cmd)}")

                heartbeat_stop = None
                try:
                    self.running_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        cwd=str(REPO_ROOT),
                        env={**os.environ, "PYTHONUNBUFFERED": "1"},
                        bufsize=1,
                        universal_newlines=True,
                    )

                    last_output_at = {"value": monotonic()}
                    heartbeat_stop = self.start_heartbeat(label, last_output_at)

                    assert self.running_process.stdout is not None
                    for line in self.running_process.stdout:
                        last_output_at["value"] = monotonic()
                        sna_log(line.rstrip())

                    self.running_process.wait()
                    return_code = self.running_process.returncode

                    if return_code == 0:
                        sna_log(f"✅ {label} finalizado con éxito.")
                        self.root.after(0, self.trigger_stage_alarm)
                    else:
                        had_error = True
                        if self.stop_requested:
                            sna_log("⏹ Proceso SNA detenido por el usuario.")
                            break
                        sna_log(f"❌ Error en {label} (Código {return_code})")
                        if not self.continue_error_var.get():
                            sna_log("Abortando ejecución SNA.")
                            break

                except Exception as exc:
                    had_error = True
                    sna_log(f"💥 Error inesperado en {label}: {exc}")
                    if not self.continue_error_var.get():
                        break
                finally:
                    if heartbeat_stop is not None:
                        heartbeat_stop.set()

            if not had_error and not self.stop_requested:
                missing_outputs = [path for path in final_outputs if not path.exists()]
                if missing_outputs:
                    had_error = True
                    sna_log("❌ Las etapas terminaron, pero faltan resultados finales:")
                    for path in missing_outputs:
                        sna_log(f"   - {path}")
                else:
                    success = True
                    sna_log("📁 Resultados SNA generados:")
                    for path in final_outputs:
                        sna_log(f"   - {path}")

            if success:
                sna_log("\n🏁 SNA finalizado correctamente.")
            elif not self.stop_requested:
                sna_log("\n🏁 SNA incompleto: no se generaron los tres HTML finales.")
            sna_log(f"Bitácora: {run_log}")
        finally:
            log_handle.close()
            self.root.after(0, self.finish_sna_ui, success, run)

    def run_periodico(self, prepared_template, since, before, special_folder):
        parent_path = Path(special_folder)
        if not parent_path.exists():
            parent_path.mkdir(parents=True, exist_ok=True)

        period_dir = parent_path / f"{since}_al_{before}"
        self.log(f"ℹ️ Procesando un solo periodo: {period_dir.name}")
        self.log(f"\n{'='*60}")
        self.log(f"🔄 PROCESANDO PERIODO: {period_dir.name}")
        self.log(f"{'='*60}")

        adjusted_prepared = []
        for spec, cmd, env in prepared_template:
            new_cmd = []
            current_flag = None
            for part in cmd:
                if part == str(REPO_ROOT):
                    new_cmd.append(str(period_dir))
                elif current_flag in PERIODO_DIR_FLAGS:
                    new_cmd.append(remap_periodic_path(part, period_dir))
                elif part == "__PERIODO_SINCE__":
                    new_cmd.append(since)
                elif part == "__PERIODO_BEFORE__":
                    new_cmd.append(before)
                else:
                    new_cmd.append(part)
                current_flag = part if part.startswith("--") else None
            new_env = dict(env)
            new_env["REPORT_TAG_OVERRIDE"] = period_dir.name
            adjusted_prepared.append((spec, new_cmd, new_env))

        self.run_pipelines(adjusted_prepared, period_dir.name)

    def run_conjunto(self, prepared, before, special_folder):
        parent_path = Path(special_folder)
        parent_path.mkdir(parents=True, exist_ok=True)
        periods = discover_period_dirs(parent_path)
        if not periods:
            self.log(f"❌ No se encontraron carpetas de periodo en: {parent_path}")
            return

        combined_since = min(item[0] for item in periods)
        combined_before = max(item[1] for item in periods)
        range_tag = build_conjunto_range_tag(periods)
        conjunto_dir = parent_path / range_tag
        conjunto_dir.mkdir(parents=True, exist_ok=True)

        self.log(f"\n{'='*60}")
        self.log(f"🏗️ INICIANDO ANÁLISIS CONJUNTO")
        self.log(f"{'='*60}")
        self.log(f"Carpeta destino: {conjunto_dir}")
        self.log(f"Rango detectado: {combined_since} a {combined_before}")
        self.log(f"Tag de materiales: {range_tag}")

        adjusted_prepared = []
        for spec, cmd, env in prepared:
            new_cmd = list(cmd)
            new_env = dict(env)

            if spec.code == "6":
                new_cmd = rewrite_flag_value(new_cmd, "--since", "conjunto")
                new_cmd = rewrite_flag_value(new_cmd, "--before", combined_before)
                new_cmd = rewrite_flag_value(new_cmd, "--base-dir", str(parent_path))
                new_cmd = rewrite_flag_value(new_cmd, "--output-dir", str(parent_path))
            else:
                new_cmd = rewrite_flag_value(new_cmd, "--since", combined_since)
                new_cmd = rewrite_flag_value(new_cmd, "--before", combined_before)

                remapped_cmd = []
                current_flag = None
                for part in new_cmd:
                    if current_flag in PERIODO_DIR_FLAGS:
                        remapped_cmd.append(remap_periodic_path(part, conjunto_dir))
                    else:
                        remapped_cmd.append(part)
                    current_flag = part if part.startswith("--") else None
                new_cmd = remapped_cmd
                new_env["REPORT_TAG_OVERRIDE"] = range_tag

            adjusted_prepared.append((spec, new_cmd, new_env))

        self.run_pipelines(adjusted_prepared, combined_since)

    def start_heartbeat(self, spec_label: str, last_output_at: dict[str, float]):
        stop_event = threading.Event()

        def _heartbeat():
            while not stop_event.wait(5):
                if self.running_process is None:
                    continue
                idle_for = int(monotonic() - last_output_at["value"])
                if idle_for >= 5:
                    self.log(f"⏳ {spec_label} sigue corriendo... {idle_for}s sin salida nueva.")

        thread = threading.Thread(target=_heartbeat, daemon=True)
        thread.start()
        return stop_event

    def _resolve_datos_dir_for_limpieza(self, cmd: list[str], since: str) -> Path | None:
        output_dir_arg = _extract_flag_value(cmd, "--output-dir")
        if not output_dir_arg:
            return None
        if "--periodico" in cmd and _extract_flag_value(cmd, "--since") == "conjunto":
            base_dir_arg = _extract_flag_value(cmd, "--base-dir") or output_dir_arg
            base_path = Path(base_dir_arg)
            periods = discover_period_dirs(base_path)
            if periods:
                range_tag = build_conjunto_range_tag(periods)
                return base_path / range_tag / "Datos"
            return None
        datos_tag = build_report_tag(since, "Datos")
        return Path(output_dir_arg) / datos_tag

    def run_pipelines(self, prepared, since: str):
        use_defaults = self.mode_var.get() == "all_networks"
        pipeline_type = self.pipeline_type_var.get()
        facebook_posts_csv = ""
        cleaned_week_dirs = set()
        selected_codes = {spec.code for spec, _, _ in prepared}
        completed_codes = set()
        had_error = False

        for index, (spec, cmd, env_vars) in enumerate(prepared):
            if self.stop_requested:
                had_error = True
                break

            self.log(f"\n--- Ejecutando: {spec.label} ---")

            try:
                heartbeat_stop = None
                if self.use_venv_var.get() and self.venv_python and cmd and cmd[0] == sys.executable:
                    cmd[0] = self.venv_python

                self.log(f"Comando: {render_command(cmd)}")

                week_dir = weekly_output_dir_for_command(spec, since, cmd)
                if pipeline_type == "semanal" and week_dir is not None:
                    week_dir_key = str(week_dir.resolve())
                    if week_dir_key not in cleaned_week_dirs and week_dir.exists():
                        self.log(f"🧹 Eliminando resultado previo: {week_dir}")
                        import shutil

                        shutil.rmtree(week_dir)
                    cleaned_week_dirs.add(week_dir_key)

                current_env = os.environ.copy()
                current_env.update(env_vars)
                current_env["PYTHONUNBUFFERED"] = "1"

                keys_to_check = ["YOUTUBE_API_KEY", "APIFY_TOKEN", "CLAUDE_API_KEY"]
                keys_present = [key for key in keys_to_check if current_env.get(key)]
                keys_missing = [key for key in keys_to_check if not current_env.get(key)]

                if keys_present:
                    self.log(f"ℹ️ Variables de entorno detectadas: {', '.join(keys_present)}")
                if keys_missing:
                    self.log(f"⚠️ Variables no disponibles en este proceso: {', '.join(keys_missing)}")

                self.running_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=current_env,
                    cwd=str(REPO_ROOT),
                    bufsize=1,
                    universal_newlines=True,
                )

                if Path(cmd[0]).name.startswith("python"):
                    self.log("ℹ️ Salida en tiempo real activada para el proceso Python.")

                last_output_at = {"value": monotonic()}
                heartbeat_stop = self.start_heartbeat(spec.label, last_output_at)

                assert self.running_process.stdout is not None
                for line in self.running_process.stdout:
                    last_output_at["value"] = monotonic()
                    self.log(line.rstrip())

                self.running_process.wait()
                return_code = self.running_process.returncode

                if return_code == 0:
                    completed_codes.add(spec.code)
                    self.log(f"✅ {spec.label} finalizado con éxito.")
                    self.root.after(0, self.trigger_stage_alarm)

                    if spec.code == "6" and pipeline_type != "conjunto":
                        datos_dir = self._resolve_datos_dir_for_limpieza(cmd, since)
                        if datos_dir and datos_dir.exists():
                            limpieza_cmd = [
                                cmd[0],
                                str(SCRIPTS_DIR / "limpieza_texto.py"),
                                "--datos-dir",
                                str(datos_dir),
                            ]
                            self.log(f"🧼 Ejecutando limpieza de texto: {datos_dir}")
                            limpieza_result = subprocess.run(
                                limpieza_cmd,
                                env=current_env,
                                cwd=str(REPO_ROOT),
                                capture_output=True,
                                text=True,
                            )
                            if limpieza_result.returncode == 0:
                                self.log("✅ Limpieza de texto completada")
                            else:
                                self.log(f"⚠️ Limpieza de texto falló con código {limpieza_result.returncode}")

                    if spec.code == "4":
                        output_dir_arg = _extract_flag_value(cmd, "--output-dir") or str(REPO_ROOT / "Facebook")
                        report_tag = build_report_tag(since, "Facebook")
                        facebook_posts_csv = str(Path(output_dir_arg) / report_tag / f"{report_tag}_posts.csv")

                        if os.path.exists(facebook_posts_csv):
                            self.log(f"ℹ️ Detectado CSV de posts: {facebook_posts_csv}")
                            for future_index in range(index + 1, len(prepared)):
                                pending_spec, pending_cmd, pending_env = prepared[future_index]
                                if pending_spec.code == "5" and "--input-csv" not in pending_cmd:
                                    pending_cmd.extend(["--input-csv", facebook_posts_csv])
                                    prepared[future_index] = (pending_spec, pending_cmd, pending_env)
                        else:
                            self.log(f"⚠️ CSV esperado no encontrado: {facebook_posts_csv}")
                            facebook_posts_csv = ""
                else:
                    had_error = True
                    if self.stop_requested:
                        self.log("⏹ Proceso detenido por el usuario.")
                        break

                    self.log(f"❌ Error en {spec.label} (Código {return_code})")
                    if pipeline_type != "conjunto" and not self.continue_error_var.get():
                        self.log("Abortando ejecución.")
                        break

            except Exception as exc:
                had_error = True
                self.log(f"💥 Error inesperado ejecutando {spec.label}: {exc}")
                if pipeline_type != "conjunto" and not self.continue_error_var.get():
                    break
            finally:
                if heartbeat_stop is not None:
                    heartbeat_stop.set()

        if (
            pipeline_type == "semanal"
            and not self.stop_requested
            and not had_error
            and "13" not in selected_codes
            and REQUIRED_PIPELINE_CODES.issubset(selected_codes)
            and REQUIRED_PIPELINE_CODES.issubset(completed_codes)
        ):
            try:
                destination_dir = export_week_to_subir_ia(since)
                self.log(f"📦 Archivos listos para IA en: {destination_dir}")
            except FileNotFoundError as exc:
                self.log(f"⚠️ No se pudo preparar Subir_IA: {exc}")
            except Exception as exc:
                self.log(f"⚠️ Error preparando Subir_IA: {exc}")

        self.log("\n🏁 Proceso terminado.")

    def finish_ui(self):
        self.play_button.config(state=tk.NORMAL)
        self.sna_history_button.config(state=tk.NORMAL)
        self.sna_recent_button.config(state=tk.NORMAL)
        self.sna_last_week_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.running_process = None
        if not self.stop_requested:
            self.trigger_final_alarm()
            messagebox.showinfo("Finalizado", "La ejecución de los pipelines ha concluido.")

    def finish_sna_ui(self, success: bool, run):
        self.play_button.config(state=tk.NORMAL)
        self.sna_history_button.config(state=tk.NORMAL)
        self.sna_recent_button.config(state=tk.NORMAL)
        self.sna_last_week_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.running_process = None
        if self.stop_requested:
            return
        if success:
            self.trigger_final_alarm()
            messagebox.showinfo(
                "SNA finalizado",
                f"Se generó el análisis de {run['label']} en:\n{run['results_dir']}",
            )
        else:
            messagebox.showerror(
                "SNA incompleto",
                "La cadena se detuvo antes de generar los resultados finales. "
                f"Revisa la bitácora:\n{run['run_log']}",
            )


def main():
    root = tk.Tk()
    OrquestadorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
