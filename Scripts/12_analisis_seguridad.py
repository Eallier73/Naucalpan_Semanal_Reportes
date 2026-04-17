import os
import matplotlib.pyplot as plt
from collections import Counter

# Rutas base relativas al script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
diccionarios_path = os.path.join(SCRIPT_DIR, "diccionarios")

ruta_input = os.path.join(REPO_ROOT, "Datos", "2026_W15_Datos", "material_comentarios.txt")
resultados_dir = os.path.join(REPO_ROOT, "Seguridad")

# Rutas de diccionarios
ruta_seguridad = os.path.join(diccionarios_path, "diccionario_seguridad.txt")
ruta_inseguridad = os.path.join(diccionarios_path, "diccionario_inseguridad.txt")

# Crear carpeta de resultados si no existe
os.makedirs(resultados_dir, exist_ok=True)

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

# Cargar stoplist desde archivo
ruta_stoplist = os.path.join(SCRIPT_DIR, "diccionarios", "stopwords", "stop_list_espanol.txt")
texto_stoplist = leer_archivo(ruta_stoplist)
stoplist = set([p.strip().lower() for p in texto_stoplist.splitlines() if p.strip()])
print(f"Stoplist cargada desde {ruta_stoplist}: {len(stoplist)} palabras")

# Cargar diccionarios
print(f"Leyendo palabras de seguridad de {ruta_seguridad}")
texto_seguridad = leer_archivo(ruta_seguridad)
palabras_seguridad = set([p.strip().lower() for p in texto_seguridad.splitlines() if p.strip() and p.strip().lower() not in stoplist])
print(f"Palabras de seguridad cargadas: {len(palabras_seguridad)}")

print(f"Leyendo palabras de inseguridad de {ruta_inseguridad}")
texto_inseguridad = leer_archivo(ruta_inseguridad)
palabras_inseguridad = set([p.strip().lower() for p in texto_inseguridad.splitlines() if p.strip() and p.strip().lower() not in stoplist])
print(f"Palabras de inseguridad cargadas: {len(palabras_inseguridad)}")

# Cargar corpus
nombre_archivo = os.path.splitext(os.path.basename(ruta_input))[0]
print(f"\n=== ANALIZANDO: {nombre_archivo} ===")
texto_principal = leer_archivo(ruta_input)
print(f"Texto cargado: {len(texto_principal)} caracteres")

palabras_texto = [p.strip().lower() for p in texto_principal.replace('.', ' ').replace(',', ' ').replace(';', ' ').replace(':', ' ').replace('!', ' ').replace('¡', ' ').replace('?', ' ').replace('¿', ' ').replace('-', ' ').replace('_', ' ').split() if p.strip()]
print(f"Total de palabras en el texto: {len(palabras_texto)}")

# Analizar
contador_seguridad = 0
contador_inseguridad = 0
palabras_seguridad_encontradas = []
palabras_inseguridad_encontradas = []

for palabra in palabras_texto:
    if palabra in stoplist:
        continue
    if palabra in palabras_seguridad:
        contador_seguridad += 1
        palabras_seguridad_encontradas.append(palabra)
    if palabra in palabras_inseguridad:
        contador_inseguridad += 1
        palabras_inseguridad_encontradas.append(palabra)

top_seguridad = Counter(palabras_seguridad_encontradas).most_common(20)
top_inseguridad = Counter(palabras_inseguridad_encontradas).most_common(20)

total = contador_seguridad + contador_inseguridad
if total > 0:
    porcentaje_seguridad = (contador_seguridad / total) * 100
    porcentaje_inseguridad = (contador_inseguridad / total) * 100
else:
    porcentaje_seguridad = 0
    porcentaje_inseguridad = 0

print("\n=== RESULTADOS (SEGURIDAD/INSEGURIDAD) ===")
print(f"Palabras de seguridad encontradas: {contador_seguridad}")
print(f"Palabras de inseguridad encontradas: {contador_inseguridad}")
print(f"Total: {total}")
print(f"Porcentaje de seguridad: {porcentaje_seguridad:.1f}%")
print(f"Porcentaje de inseguridad: {porcentaje_inseguridad:.1f}%")

# Guardar resultados TXT
ruta_resultados_txt = os.path.join(resultados_dir, f"resultados_{nombre_archivo}.txt")
with open(ruta_resultados_txt, 'w', encoding='utf-8') as f:
    f.write("=== PALABRAS EXCLUIDAS DEL ANÁLISIS (STOPLIST) ===\n")
    for i, palabra in enumerate(sorted(stoplist), 1):
        f.write(f"{i}. {palabra}\n")
    f.write("\n")

    f.write("=== RESULTADOS DEL ANÁLISIS DE SEGURIDAD/INSEGURIDAD ===\n")
    f.write(f"Palabras de seguridad encontradas: {contador_seguridad}\n")
    f.write(f"Palabras de inseguridad encontradas: {contador_inseguridad}\n")
    f.write(f"Total de palabras encontradas: {total}\n")
    f.write(f"Porcentaje de seguridad: {porcentaje_seguridad:.1f}%\n")
    f.write(f"Porcentaje de inseguridad: {porcentaje_inseguridad:.1f}%\n\n")

    f.write("TOP 20 PALABRAS DE SEGURIDAD ENCONTRADAS:\n")
    for i, (palabra, frecuencia) in enumerate(top_seguridad, 1):
        f.write(f"{i}. {palabra}: {frecuencia} veces\n")
    f.write("\n")

    f.write("TOP 20 PALABRAS DE INSEGURIDAD ENCONTRADAS:\n")
    for i, (palabra, frecuencia) in enumerate(top_inseguridad, 1):
        f.write(f"{i}. {palabra}: {frecuencia} veces\n")

print(f"\nResultados guardados en: {ruta_resultados_txt}")

# Gráfico de pastel seguridad/inseguridad
plt.figure(figsize=(10, 6))
plt.pie(
    [porcentaje_seguridad, porcentaje_inseguridad],
    explode=(0.1, 0),
    labels=['Seguridad', 'Inseguridad'],
    colors=['#77dd77', '#ff6961'],
    autopct='%1.1f%%',
    shadow=True,
    startangle=90
)
plt.axis('equal')
plt.title(f'Distribución de Seguridad/Inseguridad - {nombre_archivo}')
ruta_grafico = os.path.join(resultados_dir, f"grafico_seguridad_{nombre_archivo}.png")
plt.savefig(ruta_grafico, dpi=300, bbox_inches='tight')
plt.close()
print(f"Gráfico guardado en: {ruta_grafico}")

# Gráfico de barras - seguridad
def crear_grafico_barras(datos, titulo, ruta_salida, color):
    if not datos:
        return
    palabras = [p for p, _ in datos][::-1]
    frecuencias = [f for _, f in datos][::-1]
    plt.figure(figsize=(12, 8))
    plt.barh(palabras, frecuencias, color=color)
    plt.xlabel('Frecuencia')
    plt.ylabel('Palabras')
    plt.title(titulo)
    plt.tight_layout()
    plt.savefig(ruta_salida, dpi=300, bbox_inches='tight')
    plt.close()

if top_seguridad:
    crear_grafico_barras(
        top_seguridad,
        f'Palabras de Seguridad Más Frecuentes - {nombre_archivo}',
        os.path.join(resultados_dir, f"palabras_seguridad_frecuentes_{nombre_archivo}.png"),
        '#77dd77'
    )

if top_inseguridad:
    crear_grafico_barras(
        top_inseguridad,
        f'Palabras de Inseguridad Más Frecuentes - {nombre_archivo}',
        os.path.join(resultados_dir, f"palabras_inseguridad_frecuentes_{nombre_archivo}.png"),
        '#ff6961'
    )

print(f"\n=== ANÁLISIS COMPLETADO ===")
print(f"Resultados en: {resultados_dir}")
