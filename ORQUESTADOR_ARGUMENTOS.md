# Argumentos del Orquestador

Este documento resume, script por script, qué argumentos conviene pedir desde el orquestador general y qué tan interactivo era cada extractor antes de unificarlo.

## Convención de nombres

- `1_extractors_youtube.py`
- `2_extractors_twitter.py`
- `3_extractors_medios.py`
- `4_extractors_facebook_posts.py`
- `5_extractors_facebook_comentarios.py`
- `06_consolidador_datos.py`
- `07_modelado_temas_claude.py`
- `10_publicaciones_institucionales_claude.py`
- `11_analisis_polaridad.py`
- `12_analisis_seguridad.py`
- `00_orquestador_general.py`

## 01 YouTube

- Prompt propio previo: no.
- Argumentos clave:
  - `--since`
  - `--before`
  - `--queries`
  - `--mode`
  - `--max-videos-query`
  - `--output-dir`
- Credenciales:
  - `YOUTUBE_API_KEY`

## 02 Twitter/X

- Prompt propio previo: no.
- Argumentos clave:
  - `--since`
  - `--before`
  - `--query` repetible
  - `--output-dir`
  - `--state-path`
  - `--max-tweets`
  - `--max-replies-per-tweet`
  - `--max-reply-scrolls`
  - `--no-headless` opcional
- Requisito operativo:
  - `state/x_state.json`

## 03 Medios Naucalpan

- Prompt propio previo: no.
- Argumentos clave:
  - `--since`
  - `--before`
  - `--medio` repetible
  - `--termino` repetible
  - `--modo-queries`
  - `--output-dir`
  - `--nombre-archivo-base`
  - `--omitir-semanas-existentes`
  - `--pausa`
  - `--pausa-entre-queries`

## 04 Facebook desde CSV de URLs

- Prompt propio previo: sí.
- Argumentos clave:
  - `--mode`
  - `--pages`
  - `--input-csv`
  - `--max-comments`
  - `--max-urls`
  - `--sample-percent`
  - `--sample-seed`
  - `--since`
  - `--before`
  - `--batch-size`
  - `--output-dir`
- Credenciales:
  - `APIFY_TOKEN` cuando se descargan comentarios

## 05 Facebook posts

- Prompt propio previo: sí.
- Argumentos clave:
  - `--pages`
  - `--since`
  - `--before`
  - `--max-posts`
  - `--max-pages`
  - `--sample-percent`
  - `--sample-seed`
  - `--batch-size`
  - `--output-dir`
- Credenciales:
  - `APIFY_TOKEN`

## 06 Consolidador de datos

- Prompt propio previo: no.
- Argumentos clave:
  - `--since`
  - `--before`
  - `--base-dir`
  - `--output-dir`

## 07 Modelado temático con Claude

- Prompt propio previo: no.
- Argumentos clave:
  - `--since`
  - `--before`
  - `--input-dir`
  - `--output-dir`
  - `--model`
  - `--max-corpus-chars`
- Credenciales:
  - `CLAUDE_API_KEY`
- Dependencia operativa:
  - Requiere que exista `Datos/{semana}/material_institucional.txt`
  - Requiere que exista `Datos/{semana}/material_comentarios.txt`

  ## 08 Analisis de Influencia de Temas

  - Prompt propio previo: no.
  - Argumentos clave:
    - `--since`
    - `--before`
    - `--input-dir`
    - `--output-dir`
    - `--stopwords-path`
  - No requiere credenciales
  - Dependencia operativa:
    - Requiere que exista `Datos/{semana}/material_institucional.txt`
    - Requiere que exista `Datos/{semana}/material_comentarios.txt`
    - Se ejecuta tipicamente despues del pipeline 6 (Consolidador)
  - Salidas:
    - `Influencia_Temas/{semana}/tecnico/`: influencia_temas.csv, polaridad_documentos.csv
    - `Influencia_Temas/{semana}/ejecutivo/`: 00_resumen_ejecutivo.md, 01_kpis_polaridad_por_tema.csv, 01b_kpis_polaridad_por_subtema.csv, 02_top_hallazgos_polaridad.csv, 03_alertas_polaridad.csv
  - Métodos empleados:
    - Ridge Regression para coeficientes de influencia
    - Regresion Logistica para direccion de polaridad
    - Correlacion de Pearson para asociacion tema-polaridad
    - Clasificacion de impacto (Alta/Media/Baja) y confianza

  ## 09 Analisis de Temas Guiados

  - Prompt propio previo: no.
  - Argumentos clave:
    - `--since`
    - `--before`
    - `--input-dir`
    - `--output-dir`
    - `--exclude-words-path`
    - `--input-file` (opcional)
  - No requiere credenciales
  - Dependencia operativa:
    - Requiere que exista `Datos/{semana}/material_institucional.txt`
    - Requiere que exista `Datos/{semana}/material_comentarios.txt`
    - Alternativamente se puede usar `--input-file` para forzar un archivo de entrada especifico
  - Salidas:
    - `Temas_Guiados/{semana}/`: clasificacion_temas_guiados.csv, distribucion_temas_guiados.png, top75_palabras_temas_guiados.csv, informe_temas_guiados.txt
  - Antes del envío crea un corpus combinado `.txt` dentro de la carpeta semanal de `Datos`

## 10 Publicaciones Institucionales con Claude

- Prompt propio previo: no.
- Argumentos clave:
  - `--since`
  - `--before`
  - `--twitter-dir`
  - `--facebook-dir`
  - `--youtube-dir`
  - `--datos-dir`
  - `--output-dir`
  - `--model`
  - `--max-corpus-chars`
  - `--max-doc-chars`
  - `--sample-seed`
  - `--prepare-only` opcional
- Credenciales:
  - `CLAUDE_API_KEY` salvo en `--prepare-only`
- Dependencia operativa:
  - Requiere insumos institucionales de Twitter (`*_post_institucionales.csv`), Facebook (`*_posts.csv`) y/o YouTube (`*_scripts.csv`) para la semana consultada
- Salidas:
  - `Datos/{semana}/`: `publicaciones_institucionales_redes_*.csv`
  - `Claude/{semana}/`: prompt, corpus, metadata, respuesta cruda, analisis markdown/json y tablas CSV de temas/porcentajes

## 11 Analisis de Polaridad

- Prompt propio previo: no.
- Argumentos clave:
  - Actualmente no recibe CLI; usa configuracion interna del script.
- No requiere credenciales.
- Dependencia operativa:
  - Requiere diccionarios locales en `Scripts/diccionarios/`.
  - Usa corpus configurado dentro del script.
- Salidas:
  - Carpeta `Polaridad/` en raiz del repo.

## 12 Analisis de Seguridad/Inseguridad

- Prompt propio previo: no.
- Argumentos clave:
  - Actualmente no recibe CLI; usa configuracion interna del script.
- No requiere credenciales.
- Dependencia operativa:
  - Requiere diccionarios locales en `Scripts/diccionarios/`.
  - Requiere stoplist en `Scripts/diccionarios/stopwords/stop_list_espanol.txt`.
  - Requiere corpus de comentarios configurado dentro del script.
- Salidas:
  - Carpeta `Seguridad/` en raiz del repo.

## Criterio del orquestador

- El orquestador pregunta una vez el rango global `since/before`.
- Luego pide solo los parámetros específicos de cada pipeline seleccionado.
- Las credenciales sensibles se capturan sin exponerlas en la línea de comandos.
- La ejecución de los scripts se hace con CLI explícita y, cuando aplica, con `--no-prompt`.
