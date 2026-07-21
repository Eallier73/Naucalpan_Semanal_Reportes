# SNA historico de Naucalpan

El corpus de entrada es `SNA/Datos/naucalpan_datos_tabulares_consolidados.csv`.
Incluye Twitter, Facebook, YouTube y Medios. En las notas periodisticas, el
campo `fuente` se conserva como cuenta bajo la identidad
`Medios::<nombre del medio>` (por ejemplo, `Medios::Milenio`).

El consolidador integra las descargas del repo y, cuando existe, el historico
social de `/home/emilio/Documentos/RAdAR/Datos_RAdAR/Juntos`. Los formatos sin
cuenta se conservan para temas, pero no participan en la red de cuentas. Para
generar solo con las fuentes del repo se puede usar `--sin-radar`; otra copia
del historico se indica con `--radar-dir RUTA`.

## Preparacion

```bash
.venv/bin/pip install -r requirements-sna.txt
.venv/bin/python -m spacy download es_core_news_md
```

## Ejecucion

Desde la GUI del orquestador se usa el botón `EJECUTAR SNA` para lanzar toda la
secuencia, incluidas las redes guiadas. El mismo flujo se puede ejecutar con:

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

Los resultados se escriben en `SNA/Resultados/historico/`. El diagnostico
calcula umbrales por capa a partir del percentil 75 del corpus; la red completa
los utiliza automaticamente, salvo que se indiquen valores por CLI.

La configuración compara entre 25 y 35 temas y selecciona el modelo con mejor
coherencia c_v. Después califica cada tema; los agrupamientos de calidad baja se
conservan para auditoría, pero las redes guiadas los ocultan inicialmente para
reducir ruido. Los subclusters conservan todas sus palabras;
`--max-words-per-subcluster` permite limitar ese detalle de forma explícita.

`subclusters/subclusters_lectura.csv` funciona como catalogo legible de
subtemas: incluye nombre automatico, resumen, terminos principales, tamano,
densidad y peso de cada comunidad.
