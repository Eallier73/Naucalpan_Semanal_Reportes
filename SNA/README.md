# SNA historico de Naucalpan

El corpus de entrada es `SNA/Datos/naucalpan_datos_tabulares_consolidados.csv`.
Incluye Twitter, Facebook, YouTube y Medios. En las notas periodisticas, el
campo `fuente` se conserva como cuenta bajo la identidad
`Medios::<nombre del medio>` (por ejemplo, `Medios::Milenio`).

El consolidador usa exclusivamente las descargas semanales locales del
repositorio. La carpeta `Periodico/` queda fuera del corpus SNA. Los formatos
sin cuenta se conservan para temas, pero no participan en la red de cuentas.

## Preparacion

```bash
.venv/bin/pip install -r requirements-sna.txt
.venv/bin/python -m spacy download es_core_news_md
```

## Ejecucion

La GUI ofrece tres ejecuciones completas, incluidas las tres redes guiadas:

- `EJECUTAR SNA MATERIAL HISTÓRICO` usa todo el corpus y escribe en
  `SNA/Resultados/historico/`.
- `EJECUTAR SNA DOS SEMANAS` detecta las dos semanas ISO más recientes y
  escribe sin sobrescribir el histórico en
  `SNA/Resultados/ultimas_2_semanas/`.
- `EJECUTAR SNA ÚLTIMA SEMANA` usa únicamente la semana ISO más reciente y
  escribe sin sobrescribir los otros alcances en
  `SNA/Resultados/ultima_semana/`.

El flujo histórico también se puede ejecutar con:

```bash
.venv/bin/python Scripts/20_generar_analisis_sna.py
```

La secuencia manual equivalente es:

```bash
.venv/bin/python Scripts/11_consolidar_historico_sna.py
.venv/bin/python Scripts/12_lda_sna.py --k-min 25 --k-max 35 --selection-mode coherence
.venv/bin/python Scripts/sna_topic_quality.py
.venv/bin/python Scripts/12b_subclusters_louvain.py --resolution 1.4 --min-sub-size 3
.venv/bin/python Scripts/12c_diagnostico_umbrales.py
.venv/bin/python Scripts/12c_red_completa.py
.venv/bin/python Scripts/18_cuentas_clusters.py
.venv/bin/python Scripts/12d_red_cuentas.py
.venv/bin/python Scripts/19_red_posiciones_discursivas.py
.venv/bin/python Scripts/12c_red_completa_guiada.py
.venv/bin/python Scripts/12d_red_cuentas_guiada.py
.venv/bin/python Scripts/19_red_posiciones_guiada.py
```

## Salidas separadas

Cada alcance conserva su propio CSV, directorio de resultados y bitácora. Los
HTML finales de dos semanas son:

- `red_naucalpan_ultimas_2_semanas_guiada.html`
- `red_naucalpan_cuentas_ultimas_2_semanas_guiada.html`
- `red_naucalpan_posiciones_ultimas_2_semanas_guiada.html`

Los HTML finales de la última semana son:

- `red_naucalpan_ultima_semana_guiada.html`
- `red_naucalpan_cuentas_ultima_semana_guiada.html`
- `red_naucalpan_posiciones_ultima_semana_guiada.html`

El CSV reciente se puede regenerar por separado con:

```bash
.venv/bin/python Scripts/11_consolidar_historico_sna.py --last-weeks 2
```

Para consolidar únicamente la semana más reciente:

```bash
.venv/bin/python Scripts/11_consolidar_historico_sna.py --last-weeks 1
```

El diagnostico
calcula umbrales por capa a partir del percentil 75 del corpus; la red completa
los utiliza automaticamente, salvo que se indiquen valores por CLI.

La GUI conserva bitácoras independientes en `ultima_ejecucion.log` para el
histórico, `ultima_ejecucion_ultimas_2_semanas.log` para dos semanas y
`ultima_ejecucion_ultima_semana.log` para la última semana.
Solo muestra el aviso de éxito cuando existen los tres HTML finales del alcance
seleccionado; si una etapa falla, la bitácora correspondiente conserva el motivo.

La configuración compara entre 25 y 35 temas y selecciona el modelo con mejor
coherencia c_v. Después califica cada tema; los agrupamientos de calidad baja se
conservan para auditoría, pero las redes guiadas los ocultan inicialmente para
reducir ruido. Los subclusters conservan todas sus palabras;
`--max-words-per-subcluster` permite limitar ese detalle de forma explícita.

`subclusters/subclusters_lectura.csv` funciona como catalogo legible de
subtemas: incluye nombre automatico, resumen, terminos principales, tamano,
densidad y peso de cada comunidad.
