# Naucalpan_Semanal_Reportes

Repo base para descargar datos semanales de redes y medios en Naucalpan, y dejar la salida lista para procesos posteriores de NLP, homologación y análisis.

## Alcance

Este repo parte de `Datos_Radar`, pero quedó limpiado para uso operativo:

- Sin datos históricos descargados.
- Sin la carpeta `Datos_Redes_Sets_Enteros_55_Semanas`.
- Con carpetas de salida separadas para cada red y solo su arquitectura versionada.
- Con scripts ajustados para escribir dentro de este mismo repo.
- Sin secretos embebidos en código.

## Estructura

```text
Naucalpan_Semanal_Reportes/
├── Claude/
├── Datos/
├── Facebook/
├── Instagram/
├── Medios/
├── Scripts/
├── TikTok/
├── Twitter/
├── Youtube/
└── state/
```

Donde:

- `Claude/`: Analisis tematicos generados por Claude (corpus combinado + analisis)
- `Datos/`: Archivos consolidados y procesados por semana
- `Influencia_Temas/`: Analisis correlacional de influencia de temas sobre polaridad
- `Temas_Guiados/`: Clasificacion de documentos por temas guiados por palabras clave
- `Facebook/`, `Instagram/`, `Medios/`, `TikTok/`, `Twitter/`, `Youtube/`: Descargas por red/fuente

## Scripts incluidos

- `Scripts/00_gui_orquestador.py`
- `Scripts/00_orquestador_general.py`
- `Scripts/1_extractors_youtube.py`
- `Scripts/2_extractors_twitter.py`
- `Scripts/3_extractors_medios.py`
- `Scripts/4_extractors_facebook_posts.py`
- `Scripts/5_extractors_facebook_comentarios.py`
- `Scripts/5a_extractors_instagram.py`
- `Scripts/5b_extractors_tiktok.py`
- `Scripts/6_consolidador_datos.py`
- `Scripts/7_modelado_temas_claude.py`
- `Scripts/8_influencia_temas.py`
- `Scripts/9_temas_guiados.py`
- `Scripts/10_publicaciones_institucionales_claude.py`

## Variables de entorno

Define las credenciales antes de correr los extractores:

```bash
export YOUTUBE_API_KEY=""
export APIFY_TOKEN=""
export CLAUDE_API_KEY=""
```

Opcionales para YouTube:

```bash
export YT_PROXY_HTTP=""
export YT_PROXY_HTTPS=""
```

## Instalación rápida

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Uso recomendado

```bash
python Scripts/00_orquestador_general.py
```

Si prefieres interfaz gráfica:

```bash
python Scripts/00_gui_orquestador.py
```

O con lanzador corto desde la raíz del repo:

```bash
python abrir_gui_orquestador.py
```

La GUI usa el mismo motor del orquestador general, respeta las dependencias operativas entre pipelines y ya permite dos flujos:

- Modo genérico con parámetros por defecto.
- Modo específico por red, reutilizando los prompts del orquestador mediante diálogos de Tkinter.

Se dejó además una plantilla reusable en `Templates/` para portar esta arquitectura a otros repos semanales.

El detalle script por script de argumentos y prompts quedó en `ORQUESTADOR_ARGUMENTOS.md`.

## Notas operativas

- `state/x_state.example.json` es solo una referencia. Debes crear `state/x_state.json` con un `storage_state` válido para correr el extractor de X/Twitter.
- Las salidas semanales se generan dentro de la carpeta de cada fuente y usan etiquetas por semana.
- Instagram (pipeline 14) y TikTok (pipeline 15) usan `APIFY_TOKEN`; sus consultas y hashtags están centralizados en `Scripts/queries_config.py`.
- Los perfiles oficiales de Instagram y TikTok permanecen vacíos hasta confirmarlos. Mientras tanto, ambos funcionan por búsquedas y hashtags dirigidos a Isaac Montoya y al Gobierno de Naucalpan.
- Ambos admiten `--dry-run`: muestran la entrada prevista sin llamar a Apify, sin requerir token y sin crear archivos.
- El botón `EJECUTAR SNA` corre el análisis histórico completo, incluidas las redes guiadas, la postura hacia Isaac Montoya/gobierno municipal y el filtro de calidad temática.
- La carpeta `Influencia_Temas/{semana}/` contiene analisis correlacional de temas sobre polaridad con reportes tecnicos (CSVs) y ejecutivos (KPIs, hallazgos, alertas).
- El pipeline 8 (Analisis de Influencia) requiere que se ejecute primero el pipeline 6 (Consolidador) para generar `material_institucional.txt` e `material_comentarios.txt`.
- La carpeta `Temas_Guiados/{semana}/` contiene clasificacion por tema, top de palabras y reporte textual del analisis guiado.
- El pipeline 9 (Temas Guiados) requiere que se ejecute primero el pipeline 6 (Consolidador), salvo que se indique un `--input-file` explicito.
- El análisis temático con Claude toma su insumo desde `Datos/{semana}/`, donde primero se crea un corpus combinado sin borrar los dos materiales originales.
- El pipeline 10 consolida publicaciones institucionales de Twitter, Facebook y YouTube en `Datos/{semana}/publicaciones_institucionales_redes_*.csv` y genera su analisis tematico comparado dentro de `Claude/{semana}/`.
- `.gitignore` está configurado para no versionar descargas, cachés ni credenciales futuras.
