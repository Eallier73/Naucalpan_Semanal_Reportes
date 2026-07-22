#!/usr/bin/env python3
"""Evalua coherencia por tema y agrega una capa editorial recuperable.

La coherencia c_v detecta mezclas semanticas, pero no siempre identifica
artefactos editoriales (por ejemplo, columnas o resúmenes informativos). Por
eso se combina con reglas por firma léxica. Los temas de calidad baja no se
eliminan: quedan marcados para ocultarlos por defecto en la interfaz.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CLUSTERS = REPO_ROOT / "SNA" / "Resultados" / "historico" / "clusters"


@dataclass(frozen=True)
class EditorialRule:
    signature: frozenset[str]
    minimum: int
    title: str
    summary: str
    quality: str
    reason: str


EDITORIAL_RULES = (
    EditorialRule(
        frozenset({"mundial", "futbol", "deporte", "estadio", "copa", "pasion", "triunfo", "celebrar"}), 3,
        "Mundial, fútbol y celebraciones públicas",
        "El núcleo reúne expectativas y reacciones alrededor del Mundial, los partidos y el ambiente en estadios o plazas públicas. Permite seguir la apropiación local del evento, desde la celebración y la convivencia hasta las críticas por acceso, costos y organización.",
        "media", "tema reconocible, aunque incorpora conversación general sobre espectáculos y convivencia",
    ),
    EditorialRule(
        frozenset({"maestro", "maestros", "cnte", "marcha", "clase", "exigir", "protesta", "pliego"}), 3,
        "Protestas magisteriales y demandas de la CNTE",
        "Concentra discusión sobre movilizaciones de la CNTE, pagos y condiciones laborales del magisterio, suspensión de clases y exigencias al gobierno. También recoge el conflicto público sobre los métodos de protesta y sus efectos en estudiantes, trabajadores y movilidad.",
        "alta", "firma léxica consistente de protesta y conflicto magisterial",
    ),
    EditorialRule(
        frozenset({"venustiano", "carranza", "parquimetro", "guardia", "transito", "persecucion", "cartelera", "getting"}), 3,
        "Agregación de notas metropolitanas y policiacas",
        "Mezcla encabezados sobre tránsito, Guardia Nacional, robos, homicidios y actividades metropolitanas en Venustiano Carranza. La unión proviene en buena medida de páginas de medios que concatenan notas o recomendaciones, por lo que no debe interpretarse como una sola preocupación social.",
        "baja", "artefacto de agregación editorial con noticias distintas concatenadas",
    ),
    EditorialRule(
        frozenset({"city", "love", "like", "first", "good", "time", "happy", "one", "great", "going", "thank", "amazing"}), 5,
        "Audiencias en inglés sobre viajes y experiencias en México",
        "Agrupa comentarios en inglés que celebran viajes, comida, recorridos urbanos y experiencias personales en México. Describe una audiencia digital internacional y afectiva; sirve para estudiar recepción turística, pero aporta poca evidencia directa sobre problemas municipales de Naucalpan.",
        "media", "conversación coherente pero principalmente turística y externa al municipio",
    ),
    EditorialRule(
        frozenset({"toluca", "minuto", "libre", "cliente", "estimado", "informir", "viaje"}), 4,
        "Tiempos de traslado en la carretera Naucalpan-Toluca",
        "Reúne avisos recurrentes sobre minutos de recorrido, cuotas y condiciones de viaje entre Naucalpan y Toluca, especialmente por la vía libre. Es útil como pulso operativo de movilidad, aunque parte del volumen procede de mensajes automáticos y repetitivos.",
        "media", "información vial específica con alta repetición de un emisor operativo",
    ),
    EditorialRule(
        frozenset({"lenguaje", "comunicado", "enlace", "grupo", "mercado", "demanda", "esperanza", "dedicado"}), 3,
        "Comunicados accesibles y asuntos dispersos",
        "El vocabulario combina versiones institucionales en lectura fácil con menciones aisladas a grupos, mercados, demandas y seguridad. No existe suficiente continuidad para sostener un asunto único: conviene abrir los mensajes originales antes de usar este conjunto en una conclusión.",
        "baja", "mezcla de comunicados accesibles con conversaciones sin relación estable",
    ),
    EditorialRule(
        frozenset({"espacio", "publico", "transformacion", "recuperar", "urbano", "luminaria", "cancha", "rehabilitacion", "limpieza", "digno", "huellasdelatransformacion"}), 4,
        "Recuperación de espacios públicos y equipamiento urbano",
        "Documenta rehabilitación de parques, canchas, luminarias, áreas verdes y otros espacios deteriorados. La conversación permite observar cómo el gobierno municipal comunica obras de recuperación y cómo las audiencias valoran seguridad, mantenimiento, accesibilidad y calidad del entorno.",
        "alta", "firma clara de obra municipal y recuperación de espacios públicos",
    ),
    EditorialRule(
        frozenset({"gustar", "saludo", "hermoso", "abrazo", "querido", "lindo", "viva", "ganar", "sentir", "canal"}), 4,
        "Saludos, felicitaciones y reacciones de audiencia",
        "Concentra respuestas breves de aprobación, afecto, felicitación y pertenencia nacional en videos y canales digitales. Mide interacción emocional de la audiencia más que una demanda pública concreta, por lo que debe separarse de apoyo político o evaluación gubernamental.",
        "media", "interacción digital coherente pero poco sustantiva para política municipal",
    ),
    EditorialRule(
        frozenset({"servicio", "entrega", "programa", "tarjeta", "empresa", "alcalde", "acuerdo", "costo", "atencion", "medico", "convenio", "descuento"}), 4,
        "Convenios, servicios y apoyos para la economía familiar",
        "Reúne acuerdos municipales con prestadores de servicios, tarifas preferenciales, entrega de tarjetas y programas de atención médica o administrativa. El hilo común es reducir costos y acercar beneficios, aunque dentro del conjunto conviven instrumentos y poblaciones distintas.",
        "media", "eje de beneficios públicos reconocible con varios programas diferentes",
    ),
    EditorialRule(
        frozenset({"morena", "narco", "corrupto", "corrupcion", "claudia", "brugada", "sheinbaum", "pri", "pan", "robar"}), 4,
        "Acusaciones de corrupción y confrontación partidista",
        "Concentra críticas a Morena y a figuras de gobierno, acusaciones sobre corrupción, dinero, vínculos criminales e incompetencia, además de respuestas partidistas. Es un espacio de oposición y disputa nacional; las afirmaciones deben tratarse como señalamientos de usuarios, no como hechos comprobados.",
        "alta", "conversación política crítica con vocabulario consistente",
    ),
    EditorialRule(
        frozenset({"junio", "julio", "octubre", "parque", "escuela", "educacion", "estudiante", "escolar", "horas", "medioambiente", "activacion"}), 4,
        "Archivo mensual de parques, escuelas y actividades",
        "Combina listados fechados de parques, escuelas, jornadas ambientales y actividades públicas. El agrupamiento refleja páginas de archivo y etiquetas de medios más que una conversación homogénea, de modo que sus notas deben separarse por asunto antes de analizarlas.",
        "baja", "artefacto de archivo periodístico organizado por fechas y etiquetas",
    ),
    EditorialRule(
        frozenset({"edomex", "agosto", "lluvia", "registro", "cuautitlan", "izcalli", "vivienda", "temporada", "incremento", "mayo", "abril", "recoleccion"}), 4,
        "Lluvias y agenda estatal del norte del Edomex",
        "Reúne referencias a lluvias, vivienda, registros y servicios en Cuautitlán Izcalli y otros municipios del norte del Estado de México. Parte del patrón proviene de páginas de archivo que concatenan avances noticiosos, por lo que no debe atribuirse todo el conjunto a una misma coyuntura.",
        "baja", "agregación de etiquetas y avances informativos sobre asuntos estatales distintos",
    ),
    EditorialRule(
        frozenset({"cdmx", "video", "mexicano", "jalisco", "edificio", "taco", "coyoacan", "guadalajara", "comida", "saludos", "bonito"}), 4,
        "Turismo urbano, arquitectura y comida en México",
        "Agrupa videos y comentarios sobre recorridos por CDMX y otras ciudades, edificios, barrios, gastronomía y comparaciones culturales. Es útil para leer imagen urbana y recepción turística, pero la mayor parte de la conversación no se refiere específicamente a la gestión de Naucalpan.",
        "media", "tema turístico coherente con alcance geográfico más amplio que Naucalpan",
    ),
    EditorialRule(
        frozenset({"presidente", "montoya", "isaac", "gobierno", "naucalpens", "excelente", "compromiso", "encabezado", "desarrollo", "oportunidad"}), 4,
        "Gestión de Isaac Montoya y respaldo a su gobierno",
        "Concentra publicaciones sobre Isaac Montoya, compromisos de gobierno, obras y programas municipales, junto con mensajes de felicitación o respaldo. Es el tema más directo para estudiar la construcción pública de su liderazgo; conviene distinguir comunicación institucional de apoyo ciudadano espontáneo.",
        "alta", "referencias directas y reiteradas al alcalde y su gestión",
    ),
    EditorialRule(
        frozenset({"naucalpan", "aquigobiernalaesperanza", "invitar", "participar", "consulta", "actividad", "cultura", "informacion", "imnis", "curso", "taller", "gratuito"}), 4,
        "Cursos, talleres y convocatorias del IMNIS",
        "Reúne invitaciones del Instituto de las Mujeres Naucalpenses a cursos, talleres, consultas y actividades gratuitas. Permite observar la oferta institucional dirigida a mujeres y la respuesta del público, diferenciando difusión de servicios, participación efectiva y valoración del programa.",
        "alta", "firma institucional clara del IMNIS y sus actividades",
    ),
    EditorialRule(
        frozenset({"garcia", "columna", "noticias", "correo", "informativo", "resumen", "hernandez", "ramirez", "martinez"}), 4,
        "Columnas, nombres propios y boletines automáticos",
        "Combina firmas personales, columnas de opinión, resúmenes informativos y módulos automáticos de sitios de noticias. La proximidad entre nombres, parentescos y asuntos públicos es editorial, no temática; este conjunto debe conservarse para auditoría y excluirse de conclusiones sustantivas.",
        "baja", "boilerplate periodístico y nombres propios sin un asunto común",
    ),
    EditorialRule(
        frozenset({"delincuente", "carcel", "rata", "pena", "meter", "pinche", "ojala", "deber", "gente"}), 4,
        "Reacciones punitivas ante delitos y abusos",
        "Agrupa comentarios que exigen cárcel, castigo o expulsión frente a fraudes, agresiones y otros delitos. Más que narrar un caso único, muestra una postura ciudadana de endurecimiento penal, frecuentemente expresada con enojo, insultos o desconfianza hacia autoridades.",
        "alta", "patrón discursivo consistente de castigo y condena",
    ),
    EditorialRule(
        frozenset({"mexico", "inglaterra", "partido", "jugar", "fan", "reforma", "cerrar", "plaza", "unam", "cch"}), 4,
        "México-Inglaterra, Fan Fest y operación del espacio público",
        "El núcleo sigue el partido México-Inglaterra, las zonas para aficionados y los cierres u operativos asociados en Reforma y plazas públicas. Se cruza con referencias universitarias y agenda cultural, por lo que conviene separar la conversación deportiva de los efectos en movilidad y seguridad.",
        "media", "evento deportivo reconocible con cruces de movilidad y agenda universitaria",
    ),
    EditorialRule(
        frozenset({"calle", "policia", "satelite", "alcaldia", "bache", "camioneta", "multa", "automovil", "codigo", "comercio"}), 4,
        "Policía de tránsito, multas y deterioro vial",
        "Concentra denuncias y experiencias sobre policías, retiro de placas, multas, grúas y posibles abusos en calles de Satélite y otras zonas de Naucalpan. También incorpora baches y obstáculos viales, permitiendo analizar la intersección entre movilidad cotidiana, mantenimiento y confianza en la autoridad.",
        "alta", "conversación local consistente sobre tránsito, vialidad y actuación policial",
    ),
    EditorialRule(
        frozenset({"agua", "rio", "basura", "inundacion", "oapas", "hondo", "drenaje", "coladera", "desbordamiento", "presa", "colonia"}), 4,
        "Río Hondo, inundaciones, drenaje y basura",
        "Reúne alertas y reclamos por el desbordamiento del Río Hondo, encharcamientos, drenaje insuficiente y acumulación de basura. Permite seguir daños por lluvias, acciones de OAPAS y Protección Civil, prevención municipal y atribución de responsabilidades entre gobierno y habitantes.",
        "alta", "problema territorial claramente delimitado por agua e infraestructura hidráulica",
    ),
    EditorialRule(
        frozenset({"hombre", "autoridad", "presunto", "fiscalia", "caso", "cuerpo", "investigacion", "detenido", "crimen", "sujeto", "victima", "justicia", "denuncia"}), 5,
        "Homicidios, detenciones e investigaciones de la Fiscalía",
        "Concentra reportes de personas asesinadas, hallazgos de cuerpos, detenciones y carpetas de investigación en Naucalpan y municipios cercanos. Debe leerse como cobertura de casos policiacos específicos, distinguiendo hechos confirmados por autoridades de versiones preliminares o señalamientos en redes.",
        "alta", "firma policiaca consistente de casos, víctimas e investigación",
    ),
    EditorialRule(
        frozenset({"periferico", "norte", "municipio", "civil", "riesgo", "puente", "proteccion", "cierre", "tultitlan", "circulacion", "carretera", "tlalnepantla", "reportar"}), 5,
        "Periférico Norte: obras, cierres y riesgos viales",
        "Agrupa rehabilitación, accidentes, bloqueos y afectaciones a la circulación en Periférico Norte y sus conexiones con Naucalpan, Tlalnepantla y Tultitlán. Sirve para comparar el avance de obra pública con tiempos de traslado, seguridad vial y respuesta ante cierres o emergencias.",
        "media", "eje vial claro con coyunturas diferentes de obra, protesta y accidente",
    ),
    EditorialRule(
        frozenset({"padre", "maria", "amen", "jesus", "jose", "senor", "salud", "santo", "bendicion", "alma", "paz", "salve"}), 5,
        "Oraciones, rosarios y peticiones de salud",
        "Reúne plegarias a la Virgen y a Jesús, rosarios, agradecimientos y solicitudes por salud, protección o descanso de familiares. Es una comunidad devocional digital; las menciones a padre, madre e hijo expresan vínculos religiosos o intenciones de oración, no un tema general sobre vida familiar.",
        "alta", "vocabulario religioso y devocional altamente consistente",
    ),
    EditorialRule(
        frozenset({"seguridad", "municipal", "fortalecer", "prevencion", "estrategia", "guardiamunicipal", "proteger", "sector", "coordinacion", "operativo", "delito", "preventivo", "permanente"}), 5,
        "Operativos de la Guardia Municipal y prevención del delito",
        "Concentra comunicación sobre despliegues territoriales, patrullaje preventivo, coordinación con autoridades estatales y federales y vigilancia en zonas comerciales o de alta afluencia. Permite evaluar prioridades y narrativa oficial de seguridad, aunque los resultados anunciados requieren contrastarse con incidentes y percepción ciudadana.",
        "alta", "firma institucional clara de operativos y prevención municipal",
    ),
    EditorialRule(
        frozenset({"obra", "linea", "transporte", "metro", "estacion", "movilidad", "proyecto", "via", "tren", "mexicable", "vialidad", "avance"}), 5,
        "Mexicable y expansión del transporte público",
        "Reúne avances, plazos y expectativas sobre la nueva línea del Mexicable, estaciones y conexiones con otros sistemas de transporte. La conversación contrapone beneficios esperados —menor tiempo de traslado, acceso desde zonas altas y reactivación económica— con dudas sobre costo, ejecución y fecha de apertura.",
        "alta", "proyecto de movilidad e infraestructura claramente identificado",
    ),
)


def parse_topic_words(raw: Any) -> list[str]:
    return [
        part.split("(", 1)[0].strip().lower()
        for part in str(raw).split(",")
        if part.split("(", 1)[0].strip()
    ]


def matching_rule(words: list[str]) -> EditorialRule | None:
    word_set = set(words[:20])
    matches = [
        (len(word_set & rule.signature), rule)
        for rule in EDITORIAL_RULES
        if len(word_set & rule.signature) >= rule.minimum
    ]
    return max(matches, key=lambda item: item[0])[1] if matches else None


def coherence_quality(value: float) -> str:
    if value < 0.27:
        return "baja"
    if value < 0.42:
        return "media"
    return "alta"


def compute_per_topic_coherence(corpus_path: Path, topics: list[list[str]]) -> list[float]:
    from gensim.corpora import Dictionary
    from gensim.models.coherencemodel import CoherenceModel

    corpus_df = pd.read_csv(corpus_path, usecols=["lemas"])
    docs = [str(value).split() for value in corpus_df["lemas"].fillna("")]
    dictionary = Dictionary(docs)
    valid_topics = [
        [word for word in topic if word in dictionary.token2id]
        for topic in topics
    ]
    model = CoherenceModel(
        topics=valid_topics,
        texts=docs,
        dictionary=dictionary,
        coherence="c_v",
        processes=1,
    )
    return [float(value) for value in model.get_coherence_per_topic()]


def enrich_topics(clusters_dir: Path) -> pd.DataFrame:
    topics_path = clusters_dir / "temas_terminos.csv"
    corpus_path = clusters_dir / "corpus_modelado.csv"
    if not topics_path.exists() or not corpus_path.exists():
        raise SystemExit(f"Faltan insumos: {topics_path} o {corpus_path}")

    topics_df = pd.read_csv(topics_path)
    if not {"tema_id", "top_20_terminos"}.issubset(topics_df.columns):
        raise SystemExit("temas_terminos.csv no contiene tema_id y top_20_terminos")
    topic_words = [parse_topic_words(value) for value in topics_df["top_20_terminos"]]
    coherences = compute_per_topic_coherence(corpus_path, topic_words)

    enriched: list[dict[str, Any]] = []
    for (_, row), words, coherence in zip(topics_df.iterrows(), topic_words, coherences):
        rule = matching_rule(words)
        quality = rule.quality if rule else coherence_quality(coherence)
        title = rule.title if rule else ""
        if rule:
            summary = rule.summary
            reason = rule.reason
        elif quality == "baja":
            summary = (
                "Este agrupamiento tiene baja coherencia estadística y puede mezclar conversaciones distintas. "
                "Se conserva para auditoría, pero conviene revisar sus mensajes antes de usarlo en conclusiones."
            )
            reason = "coherencia c_v baja"
        else:
            summary = ""
            reason = "coherencia c_v"
        enriched.append({
            **row.to_dict(),
            "coherencia_tema_cv": round(coherence, 4),
            "calidad_tema": quality,
            "visible_por_defecto": quality != "baja",
            "titulo_curado": title,
            "resumen_curado": summary,
            "motivo_calidad": reason,
            "curacion_manual": bool(rule),
        })

    result = pd.DataFrame(enriched)
    result.to_csv(topics_path, index=False)
    report = {
        "n_temas": int(len(result)),
        "calidades": result["calidad_tema"].value_counts().to_dict(),
        "ocultos_por_defecto": result.loc[~result["visible_por_defecto"], "tema_id"].astype(int).tolist(),
        "criterio": "coherencia c_v por tema + reglas editoriales por firma lexica",
        "nota": "los temas de calidad baja se conservan y pueden recuperarse en la interfaz",
    }
    (clusters_dir / "calidad_temas.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clusters-dir", type=Path, default=DEFAULT_CLUSTERS)
    args = parser.parse_args()
    result = enrich_topics(args.clusters_dir)
    counts = result["calidad_tema"].value_counts().to_dict()
    print(f"Calidad temática: {counts}")
    print(f"Temas ocultos por defecto: {int((~result['visible_por_defecto']).sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
