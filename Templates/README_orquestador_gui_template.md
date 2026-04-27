# Plantilla Reusable del Orquestador GUI

Esta carpeta deja una base para replicar la arquitectura de GUI + orquestador en otros repos semanales.

## Archivos

- `00_gui_orquestador_template.py`: plantilla base de la GUI.

## Suposiciones del repo destino

El orquestador principal debe existir en `Scripts/` y exponer estas piezas públicas:

- `PIPELINES`
- `PIPELINES_BY_CODE`
- `DEFAULT_GLOBAL_ISO_WEEK`
- `iso_week_to_range()`
- `build_pipeline()`
- `render_command()`
- `weekly_output_dir_for_command()`
- `_extract_flag_value()`
- `build_report_tag()`

## Qué se ajusta al portar

1. `PROJECT_NAME`
2. `ORCHESTRATOR_FILENAME`
3. `REQUIRED_BY_CONSOLIDATOR`
4. Reglas extra de dependencia en `validate_dependencies()`
5. Título de ventana, carpetas y textos de uso si cambian por proyecto

## Recomendación

Si el orquestador del repo destino también comienza con `00_`, conserva la carga dinámica por `importlib.util` para evitar problemas con imports normales de Python.