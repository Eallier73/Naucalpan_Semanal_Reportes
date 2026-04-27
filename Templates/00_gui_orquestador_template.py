#!/usr/bin/env python3
"""
Plantilla reusable para una GUI de orquestador basada en Tkinter.

Uso:
1. Copia este archivo a Scripts/00_gui_orquestador.py en el repo destino.
2. Ajusta PROJECT_NAME, ORCHESTRATOR_FILENAME y REQUIRED_BY_CONSOLIDATOR.
3. Verifica que el orquestador exponga:
   - PIPELINES
   - PIPELINES_BY_CODE
   - DEFAULT_GLOBAL_ISO_WEEK
   - iso_week_to_range
   - build_pipeline
   - render_command
   - weekly_output_dir_for_command
   - _extract_flag_value
   - build_report_tag
4. Si hay dependencias adicionales entre pipelines, agrégalas en validate_dependencies().
"""

from contextlib import contextmanager
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, scrolledtext, simpledialog, ttk


PROJECT_NAME = "Mi Proyecto"
ORCHESTRATOR_FILENAME = "00_orquestador_general.py"
REQUIRED_BY_CONSOLIDATOR = {
    "7": "Claude",
    "8": "Influencia",
    "9": "Temas Guiados",
}


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
    module_path = SCRIPTS_DIR / ORCHESTRATOR_FILENAME
    scripts_dir = str(SCRIPTS_DIR)
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)

    module_name = f"{PROJECT_NAME.lower().replace(' ', '_')}_orquestador"
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


class PromptCancelled(Exception):
    pass


class OrquestadorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Orquestador Pipelines {PROJECT_NAME}")
        self.root.geometry("860x760")

        self.running_process = None
        self.stop_requested = False
        self.venv_python = self.detect_venv()

        self.setup_ui()

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
        ttk.Checkbutton(venv_frame, text="Usar Entorno Virtual (.venv/venv)", variable=self.use_venv_var).grid(row=0, column=0, sticky=tk.W)

        self.venv_status_var = tk.StringVar(value=f"Ruta: {self.venv_python}")
        ttk.Label(venv_frame, textvariable=self.venv_status_var, foreground="gray", font=("Helvetica", 8)).grid(row=1, column=0, sticky=tk.W, padx=20)

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

        options_frame = ttk.Frame(main_frame, padding="5")
        options_frame.pack(fill=tk.X)

        self.mode_var = tk.StringVar(value="all_networks")
        ttk.Radiobutton(options_frame, text="Modo Genérico (Defaults)", variable=self.mode_var, value="all_networks").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(options_frame, text="Modo Específico por Red", variable=self.mode_var, value="per_network").pack(side=tk.LEFT, padx=10)

        self.continue_error_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Continuar en error", variable=self.continue_error_var).pack(side=tk.LEFT, padx=10)

        control_frame = ttk.Frame(main_frame, padding="10")
        control_frame.pack(fill=tk.X)

        self.play_button = ttk.Button(control_frame, text="▶ PLAY / EJECUTAR", command=self.start_execution)
        self.play_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.stop_button = ttk.Button(control_frame, text="⏹ DETENER", command=self.stop_execution, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        log_frame = ttk.LabelFrame(main_frame, text="Consola de Salida", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, height=15, state=tk.DISABLED, bg="black", fg="lightgreen", font=("Courier", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def update_dates_from_week(self):
        week = self.iso_week_var.get().strip()
        try:
            since, before = iso_week_to_range(week)
            self.since_var.set(since)
            self.before_var.set(before)
        except Exception as exc:
            messagebox.showerror("Error", f"Semana ISO inválida: {exc}")

    def log(self, message: str):
        def _append():
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, message + "\n")
            self.log_area.see(tk.END)
            self.log_area.config(state=tk.DISABLED)

        self.root.after(0, _append)

    def clear_log(self):
        def _clear():
            self.log_area.config(state=tk.NORMAL)
            self.log_area.delete(1.0, tk.END)
            self.log_area.config(state=tk.DISABLED)

        self.root.after(0, _clear)

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
            insert_at = next((index for index, item in enumerate(selected) if item.code == "5"), 0)
            selected.insert(insert_at, PIPELINES_BY_CODE["4"])

        selected = ensure_pipeline_before(selected, "4", "5")

        for dep_code, dep_label in REQUIRED_BY_CONSOLIDATOR.items():
            selected_codes = {item.code for item in selected}
            if dep_code in selected_codes and "6" not in selected_codes:
                self.log(f"⚠️ Agregando Consolidador (6) como dependencia de {dep_label} ({dep_code})")
                insert_at = next((index for index, item in enumerate(selected) if item.code == dep_code), len(selected))
                selected.insert(insert_at, PIPELINES_BY_CODE["6"])
            selected = ensure_pipeline_before(selected, "6", dep_code)

        seen = set()
        unique_selected = []
        for item in selected:
            if item.code not in seen:
                unique_selected.append(item)
                seen.add(item.code)
        return unique_selected

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

    def prepare_pipelines(self, selected, since: str, before: str):
        use_defaults = self.mode_var.get() == "all_networks"
        prepared = []
        self.log("🧩 Preparando comandos de ejecución...")

        with self.patch_orchestrator_prompts():
            for spec in selected:
                self.log(f"Preparando: {spec.label}")
                cmd, env = build_pipeline(spec, since, before, use_defaults=use_defaults, facebook_posts_csv="")
                prepared.append((spec, cmd, env))

        return prepared

    def start_execution(self):
        selected = self.get_selected_pipelines()
        if not selected:
            messagebox.showwarning("Atención", "Selecciona al menos un pipeline para ejecutar.")
            return

        since = self.since_var.get().strip()
        before = self.before_var.get().strip()
        since, before = parse_date_range(since, before)

        self.clear_log()
        self.log(f"🚀 Iniciando ejecución: {since} al {before}")
        selected = self.validate_dependencies(selected)
        self.log(f"Pipelines a ejecutar: {', '.join(spec.label for spec in selected)}")

        try:
            prepared = self.prepare_pipelines(selected, since, before)
        except PromptCancelled:
            self.log("⏹ Preparación cancelada por el usuario.")
            return

        self.play_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.root.update_idletasks()
        self.stop_requested = False

        thread = threading.Thread(target=self.run_pipelines, args=(prepared, since), daemon=True)
        thread.start()

    def stop_execution(self):
        if self.running_process:
            self.stop_requested = True
            self.running_process.terminate()
            self.log("\n🛑 Solicitud de detención enviada...")

    def run_pipelines(self, prepared, since: str):
        facebook_posts_csv = ""
        cleaned_week_dirs = set()

        for index, (spec, cmd, env_vars) in enumerate(prepared):
            if self.stop_requested:
                break

            self.log(f"\n--- Ejecutando: {spec.label} ---")

            try:
                if self.use_venv_var.get() and self.venv_python and cmd and cmd[0] == sys.executable:
                    cmd[0] = self.venv_python

                self.log(f"Comando: {render_command(cmd)}")

                week_dir = weekly_output_dir_for_command(spec, since, cmd)
                if week_dir is not None:
                    week_dir_key = str(week_dir.resolve())
                    if week_dir_key not in cleaned_week_dirs and week_dir.exists():
                        self.log(f"🧹 Eliminando resultado previo: {week_dir}")
                        shutil.rmtree(week_dir)
                    cleaned_week_dirs.add(week_dir_key)

                current_env = os.environ.copy()
                current_env.update(env_vars)

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

                assert self.running_process.stdout is not None
                for line in self.running_process.stdout:
                    self.log(line.rstrip())

                self.running_process.wait()
                return_code = self.running_process.returncode
                if return_code == 0:
                    self.log(f"✅ {spec.label} finalizado con éxito.")
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
                else:
                    self.log(f"❌ Error en {spec.label} (Código {return_code})")
                    if not self.continue_error_var.get():
                        self.log("Abortando ejecución.")
                        break
            except Exception as exc:
                self.log(f"💥 Error inesperado ejecutando {spec.label}: {exc}")
                if not self.continue_error_var.get():
                    break

        self.log("\n🏁 Proceso terminado.")
        self.root.after(0, self.finish_ui)

    def finish_ui(self):
        self.play_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.running_process = None
        if not self.stop_requested:
            messagebox.showinfo("Finalizado", "La ejecución de los pipelines ha concluido.")


def main():
    root = tk.Tk()
    OrquestadorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()