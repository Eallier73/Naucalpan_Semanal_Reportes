import os
import matplotlib.pyplot as plt
from collections import Counter

# Rutas base relativas al script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
diccionarios_path = os.path.join(SCRIPT_DIR, "diccionarios")

ruta_input = os.path.join(REPO_ROOT, "Guardia", "guardia_menciones_01_15_abril")
resultados_dir = os.path.join(REPO_ROOT, "Polaridad")

# Archivos a analizar
archivos_analizar = ["guardia_menciones_01_15_abril"]

# Rutas de diccionarios
ruta_positivas = os.path.join(diccionarios_path, "diccionario_palabras_positivas.txt")
ruta_negativas = os.path.join(diccionarios_path, "diccionario_palabras_negativas.txt")
ruta_seguridad = os.path.join(diccionarios_path, "diccionario_seguridad.txt")
ruta_inseguridad = os.path.join(diccionarios_path, "diccionario_inseguridad.txt")

# Crear carpeta de resultados si no existe
if not os.path.exists(resultados_dir):
    os.makedirs(resultados_dir)
    print(f"Carpeta de resultados creada: {resultados_dir}")

# Definir stoplist
stoplist = set(['municipal', 'colonia', 'carretera', 'seguridad', 'calle', 'frontera', 'en', 'puerto', 'ir', 'como', 'nada', 'mil'])
print(f"Stoplist definida con {len(stoplist)} palabras: {', '.join(stoplist)}")

# Función para leer archivo
def leer_archivo(ruta):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        try:
            with open(ruta, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception as e:
            print(f"Error al leer {ruta}: {e}")
            return ""

# Cargar diccionarios
print(f"Leyendo palabras positivas de {ruta_positivas}")
texto_positivas = leer_archivo(ruta_positivas)
palabras_positivas = set([p.strip().lower() for p in texto_positivas.splitlines() if p.strip() and p.strip().lower() not in stoplist])
print(f"Palabras positivas cargadas: {len(palabras_positivas)}")

print(f"Leyendo palabras negativas de {ruta_negativas}")
texto_negativas = leer_archivo(ruta_negativas)
palabras_negativas = set([p.strip().lower() for p in texto_negativas.splitlines() if p.strip() and p.strip().lower() not in stoplist])
print(f"Palabras negativas cargadas: {len(palabras_negativas)}")

print(f"Leyendo palabras de seguridad de {ruta_seguridad}")
texto_seguridad = leer_archivo(ruta_seguridad)
palabras_seguridad = set([p.strip().lower() for p in texto_seguridad.splitlines() if p.strip() and p.strip().lower() not in stoplist])
print(f"Palabras de seguridad cargadas: {len(palabras_seguridad)}")

print(f"Leyendo palabras de inseguridad de {ruta_inseguridad}")
texto_inseguridad = leer_archivo(ruta_inseguridad)
palabras_inseguridad = set([p.strip().lower() for p in texto_inseguridad.splitlines() if p.strip() and p.strip().lower() not in stoplist])
print(f"Palabras de inseguridad cargadas: {len(palabras_inseguridad)}")

# Inicializar diccionario de resultados
resultados_por_archivo = {}

# Procesar cada archivo
for archivo in archivos_analizar:
    print(f"\n=== ANALIZANDO: {archivo} ===")
    ruta_archivo = os.path.join(os.path.dirname(ruta_input), archivo)  # se deriva de ruta_input definida arriba

    texto_principal = leer_archivo(ruta_archivo)
    print(f"Texto cargado: {len(texto_principal)} caracteres")

    palabras_texto = [p.strip().lower() for p in texto_principal.replace('.', ' ').replace(',', ' ').replace(';', ' ').replace(':', ' ').replace('!', ' ').replace('¡', ' ').replace('?', ' ').replace('¿', ' ').replace('-', ' ').replace('_', ' ').split() if p.strip()]
    print(f"Total de palabras en el texto: {len(palabras_texto)}")

    contador_positivas = 0
    contador_negativas = 0
    contador_seguridad = 0
    contador_inseguridad = 0

    palabras_positivas_encontradas = []
    palabras_negativas_encontradas = []
    palabras_seguridad_encontradas = []
    palabras_inseguridad_encontradas = []

    for palabra in palabras_texto:
        if palabra in stoplist:
            continue
        if palabra in palabras_positivas:
            contador_positivas += 1
            palabras_positivas_encontradas.append(palabra)
        if palabra in palabras_negativas:
            contador_negativas += 1
            palabras_negativas_encontradas.append(palabra)
        if palabra in palabras_seguridad:
            contador_seguridad += 1
            palabras_seguridad_encontradas.append(palabra)
        if palabra in palabras_inseguridad:
            contador_inseguridad += 1
            palabras_inseguridad_encontradas.append(palabra)

    contador_palabras_positivas = Counter(palabras_positivas_encontradas)
    contador_palabras_negativas = Counter(palabras_negativas_encontradas)
    contador_palabras_seguridad = Counter(palabras_seguridad_encontradas)
    contador_palabras_inseguridad = Counter(palabras_inseguridad_encontradas)

    top_positivas = contador_palabras_positivas.most_common(20)
    top_negativas = contador_palabras_negativas.most_common(20)
    top_seguridad = contador_palabras_seguridad.most_common(20)
    top_inseguridad = contador_palabras_inseguridad.most_common(20)

    total_palabras_encontradas = contador_positivas + contador_negativas
    if total_palabras_encontradas > 0:
        porcentaje_positivas = (contador_positivas / total_palabras_encontradas) * 100
        porcentaje_negativas = (contador_negativas / total_palabras_encontradas) * 100
    else:
        porcentaje_positivas = 0
        porcentaje_negativas = 0

    total_palabras_seguridad_inseguridad = contador_seguridad + contador_inseguridad
    if total_palabras_seguridad_inseguridad > 0:
        porcentaje_seguridad = (contador_seguridad / total_palabras_seguridad_inseguridad) * 100
        porcentaje_inseguridad = (contador_inseguridad / total_palabras_seguridad_inseguridad) * 100
    else:
        porcentaje_seguridad = 0
        porcentaje_inseguridad = 0

    resultados_por_archivo[archivo] = {
        "contador_positivas": contador_positivas,
        "contador_negativas": contador_negativas,
        "total_palabras_encontradas": total_palabras_encontradas,
        "porcentaje_positivas": porcentaje_positivas,
        "porcentaje_negativas": porcentaje_negativas,
        "contador_seguridad": contador_seguridad,
        "contador_inseguridad": contador_inseguridad,
        "total_palabras_seguridad_inseguridad": total_palabras_seguridad_inseguridad,
        "porcentaje_seguridad": porcentaje_seguridad,
        "porcentaje_inseguridad": porcentaje_inseguridad,
        "top_positivas": top_positivas,
        "top_negativas": top_negativas,
        "top_seguridad": top_seguridad,
        "top_inseguridad": top_inseguridad
    }

    print("\n=== RESULTADOS (POLARIDAD POSITIVA/NEGATIVA) ===")
    print(f"Palabras positivas encontradas: {contador_positivas}")
    print(f"Palabras negativas encontradas: {contador_negativas}")
    print(f"Total de palabras encontradas: {total_palabras_encontradas}")
    print(f"Porcentaje de palabras positivas: {porcentaje_positivas:.1f}%")
    print(f"Porcentaje de palabras negativas: {porcentaje_negativas:.1f}%")

    print("\n=== RESULTADOS (SEGURIDAD/INSEGURIDAD) ===")
    print(f"Palabras de seguridad encontradas: {contador_seguridad}")
    print(f"Palabras de inseguridad encontradas: {contador_inseguridad}")
    print(f"Total de palabras seguridad/inseguridad encontradas: {total_palabras_seguridad_inseguridad}")
    print(f"Porcentaje de palabras de seguridad: {porcentaje_seguridad:.1f}%")
    print(f"Porcentaje de palabras de inseguridad: {porcentaje_inseguridad:.1f}%")

    # Guardar resultados en TXT
    nombre_archivo_sin_extension = os.path.splitext(archivo)[0]
    ruta_resultados_txt = os.path.join(resultados_dir, f"resultados_{nombre_archivo_sin_extension}.txt")

    with open(ruta_resultados_txt, 'w', encoding='utf-8') as f:
        f.write("=== PALABRAS EXCLUIDAS DEL ANÁLISIS (STOPLIST) ===\n")
        for i, palabra in enumerate(sorted(stoplist), 1):
            f.write(f"{i}. {palabra}\n")
        f.write("\n")

        f.write("=== RESULTADOS DEL ANÁLISIS DE POLARIDAD (POSITIVO/NEGATIVO) ===\n")
        f.write(f"Palabras positivas encontradas: {contador_positivas}\n")
        f.write(f"Palabras negativas encontradas: {contador_negativas}\n")
        f.write(f"Total de palabras encontradas: {total_palabras_encontradas}\n")
        f.write(f"Porcentaje de palabras positivas: {porcentaje_positivas:.1f}%\n")
        f.write(f"Porcentaje de palabras negativas: {porcentaje_negativas:.1f}%\n\n")

        f.write("TOP 20 PALABRAS POSITIVAS ENCONTRADAS:\n")
        for i, (palabra, frecuencia) in enumerate(top_positivas, 1):
            f.write(f"{i}. {palabra}: {frecuencia} veces\n")
        f.write("\n")

        f.write("TOP 20 PALABRAS NEGATIVAS ENCONTRADAS:\n")
        for i, (palabra, frecuencia) in enumerate(top_negativas, 1):
            f.write(f"{i}. {palabra}: {frecuencia} veces\n")
        f.write("\n")

        f.write("=== RESULTADOS DEL ANÁLISIS (SEGURIDAD/INSEGURIDAD) ===\n")
        f.write(f"Palabras de seguridad encontradas: {contador_seguridad}\n")
        f.write(f"Palabras de inseguridad encontradas: {contador_inseguridad}\n")
        f.write(f"Total de palabras seguridad/inseguridad encontradas: {total_palabras_seguridad_inseguridad}\n")
        f.write(f"Porcentaje de palabras de seguridad: {porcentaje_seguridad:.1f}%\n")
        f.write(f"Porcentaje de palabras de inseguridad: {porcentaje_inseguridad:.1f}%\n\n")

        f.write("TOP 20 PALABRAS DE SEGURIDAD ENCONTRADAS:\n")
        for i, (palabra, frecuencia) in enumerate(top_seguridad, 1):
            f.write(f"{i}. {palabra}: {frecuencia} veces\n")
        f.write("\n")

        f.write("TOP 20 PALABRAS DE INSEGURIDAD ENCONTRADAS:\n")
        for i, (palabra, frecuencia) in enumerate(top_inseguridad, 1):
            f.write(f"{i}. {palabra}: {frecuencia} veces\n")

    print(f"\nResultados guardados en: {ruta_resultados_txt}")

    # Gráfico de pastel polaridad
    plt.figure(figsize=(10, 6))
    labels_polaridad = ['Positivas', 'Negativas']
    sizes_polaridad = [porcentaje_positivas, porcentaje_negativas]
    colors_polaridad = ['#66b3ff', '#ff9999']
    explode_polaridad = (0.1, 0)

    plt.pie(sizes_polaridad, explode=explode_polaridad, labels=labels_polaridad, colors=colors_polaridad,
            autopct='%1.1f%%', shadow=True, startangle=90)
    plt.axis('equal')
    plt.title(f'Distribución de Polaridad Positiva/Negativa - {nombre_archivo_sin_extension}')

    ruta_grafico_polaridad = os.path.join(resultados_dir, f"grafico_polaridad_{nombre_archivo_sin_extension}.png")
    plt.savefig(ruta_grafico_polaridad, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Gráfico de polaridad guardado en: {ruta_grafico_polaridad}")

    # Gráfico de pastel seguridad
    plt.figure(figsize=(10, 6))
    labels_seguridad = ['Seguridad', 'Inseguridad']
    sizes_seguridad = [porcentaje_seguridad, porcentaje_inseguridad]
    colors_seguridad = ['#77dd77', '#ff6961']
    explode_seguridad = (0.1, 0)

    plt.pie(sizes_seguridad, explode=explode_seguridad, labels=labels_seguridad, colors=colors_seguridad,
            autopct='%1.1f%%', shadow=True, startangle=90)
    plt.axis('equal')
    plt.title(f'Distribución de Seguridad/Inseguridad - {nombre_archivo_sin_extension}')

    ruta_grafico_seguridad = os.path.join(resultados_dir, f"grafico_seguridad_{nombre_archivo_sin_extension}.png")
    plt.savefig(ruta_grafico_seguridad, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Gráfico de seguridad guardado en: {ruta_grafico_seguridad}")

    # Gráficos de barras
    def crear_grafico_barras(datos, titulo, ruta_salida, color):
        if not datos:
            print(f"No hay datos para crear el gráfico: {titulo}")
            return
        palabras = [palabra for palabra, _ in datos]
        frecuencias = [freq for _, freq in datos]
        palabras.reverse()
        frecuencias.reverse()
        plt.figure(figsize=(12, 8))
        plt.barh(palabras, frecuencias, color=color)
        plt.xlabel('Frecuencia')
        plt.ylabel('Palabras')
        plt.title(titulo)
        plt.tight_layout()
        plt.savefig(ruta_salida, dpi=300, bbox_inches='tight')
        plt.close()

    if top_positivas:
        crear_grafico_barras(
            top_positivas,
            f'Palabras Positivas Más Frecuentes - {nombre_archivo_sin_extension}',
            os.path.join(resultados_dir, f"palabras_positivas_frecuentes_{nombre_archivo_sin_extension}.png"),
            '#66b3ff'
        )

    if top_negativas:
        crear_grafico_barras(
            top_negativas,
            f'Palabras Negativas Más Frecuentes - {nombre_archivo_sin_extension}',
            os.path.join(resultados_dir, f"palabras_negativas_frecuentes_{nombre_archivo_sin_extension}.png"),
            '#ff9999'
        )

    if top_seguridad:
        crear_grafico_barras(
            top_seguridad,
            f'Palabras de Seguridad Más Frecuentes - {nombre_archivo_sin_extension}',
            os.path.join(resultados_dir, f"palabras_seguridad_frecuentes_{nombre_archivo_sin_extension}.png"),
            '#77dd77'
        )

    if top_inseguridad:
        crear_grafico_barras(
            top_inseguridad,
            f'Palabras de Inseguridad Más Frecuentes - {nombre_archivo_sin_extension}',
            os.path.join(resultados_dir, f"palabras_inseguridad_frecuentes_{nombre_archivo_sin_extension}.png"),
            '#ff6961'
        )

# Informe consolidado
ruta_informe_consolidado = os.path.join(resultados_dir, "informe_consolidado.txt")
with open(ruta_informe_consolidado, 'w', encoding='utf-8') as f:
    f.write("=== INFORME CONSOLIDADO DE ANÁLISIS DE SENTIMIENTO ===\n\n")

    f.write("TABLA DE POLARIDAD POSITIVA/NEGATIVA\n")
    f.write("-" * 80 + "\n")
    f.write(f"{'Archivo':<40} | {'Positivas %':>12} | {'Negativas %':>12} | {'Total palabras':>12}\n")
    f.write("-" * 80 + "\n")

    for archivo, datos in resultados_por_archivo.items():
        f.write(f"{archivo:<40} | {datos['porcentaje_positivas']:>11.1f}% | {datos['porcentaje_negativas']:>11.1f}% | {datos['total_palabras_encontradas']:>12}\n")

    f.write("\n\n")

    f.write("TABLA DE SEGURIDAD/INSEGURIDAD\n")
    f.write("-" * 80 + "\n")
    f.write(f"{'Archivo':<40} | {'Seguridad %':>12} | {'Inseguridad %':>14} | {'Total palabras':>12}\n")
    f.write("-" * 80 + "\n")

    for archivo, datos in resultados_por_archivo.items():
        f.write(f"{archivo:<40} | {datos['porcentaje_seguridad']:>11.1f}% | {datos['porcentaje_inseguridad']:>13.1f}% | {datos['total_palabras_seguridad_inseguridad']:>12}\n")

print(f"\nInforme consolidado guardado en: {ruta_informe_consolidado}")

print("\n=== ANÁLISIS COMPLETADO ===")
print(f"Todos los resultados se han guardado en: {resultados_dir}")
