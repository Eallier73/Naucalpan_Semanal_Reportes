# Centralizacion de Queries - Mapa Visual

Esta guia resume donde vive la configuracion de queries y como fluye hacia el resto del pipeline.

## Arquitectura

```text
Naucalpan_Semanal_Reportes/
|
├── Scripts/
│   ├── queries_config.py           ← fuente central de queries
│   │   ├── YOUTUBE_*
│   │   ├── TWITTER_*
│   │   ├── MEDIOS_*
│   │   └── FACEBOOK_*
│   │
│   ├── 00_orquestador_general.py  ← importa la configuracion central
│   ├── 1_extractors_youtube.py    ← usa queries_config.py
│   ├── 2_extractors_twitter.py    ← usa queries_config.py
│   ├── 3_extractors_medios.py     ← usa queries_config.py
│   ├── 4_extractors_facebook_posts.py         ← usa queries_config.py
│   └── 5_extractors_facebook_comentarios.py   ← usa queries_config.py
│
└── QUERIES_CONFIG_GUIDE.md        ← documentacion de uso
```

## Flujo de datos

```text
Usuario modifica queries_config.py
            ↓
00_orquestador_general.py importa cambios
            ↓
Extractores toman defaults desde queries_config.py
            ↓
Se ejecutan busquedas y descargas con la nueva configuracion
```

## Estado actual

| Extractor | Archivo | Queries en queries_config.py | Estado |
|-----------|---------|------------------------------|--------|
| **YouTube** | `1_extractors_youtube.py` | `YOUTUBE_CHANNELS`, `YOUTUBE_SEARCH_QUERIES` | ✅ Actualizado |
| **Twitter** | `2_extractors_twitter.py` | `TWITTER_SEARCH_QUERIES` | ✅ Actualizado |
| **Medios** | `3_extractors_medios.py` | `MEDIOS_SITES`, `MEDIOS_SEARCH_TERMS` | ✅ Actualizado |
| **Facebook Posts** | `4_extractors_facebook_posts.py` | `FACEBOOK_PAGES` | ✅ Actualizado |
| **Facebook Comentarios** | `5_extractors_facebook_comentarios.py` | `FACEBOOK_PAGES` | ✅ Actualizado |
| **Orquestador** | `00_orquestador_general.py` | Todos | ✅ Actualizado |

## Configuracion vigente

### YouTube

```python
YOUTUBE_CHANNELS = [
    "CiudadNaucalpan",
]

YOUTUBE_SEARCH_QUERIES = [
    "presidente municipal de naucalpan",
    "Gobierno de Naucalpan",
    "gobierno de naucalpan",
    "guardia municipal de naucalpan",
    "ciudad naucalpan",
]
```

### Twitter/X

```python
TWITTER_SEARCH_QUERIES = [
    "to:isaacsolar",
    "from:isaacsolar",
    "to:GobNau",
    "from:GobNau",
    "@GobNau",
    "@isaacsolar",
    "isaac montoya",
    "gobierno de naucalpan",
    "naucalpan",
    "guardia municipal de naucalpan",
]
```

### Medios

```python
MEDIOS_SITES = [
    "site:oem.com.mx",
    "site:diariodenaucalpan.com",
]

MEDIOS_SEARCH_TERMS = [
    '"Isaac Montoya"',
    '"gobierno de naucalpan"',
    '"naucalpan"',
    '"guardia municipal de naucalpan"',
]
```

### Facebook

```python
FACEBOOK_PAGES = [
    "GuardiaMunicipalCiudadNaucalpan",
    "isaacmontoya24",
    "CiudadNaucalpan",
]
```

## Nota de medios

El extractor de medios trabaja con Google News RSS. Por eso la configuracion usa filtros `site:` compatibles con ese flujo, aunque la referencia operativa incluya rutas mas especificas como la seccion de Naucalpan en OEM.

## Referencias

- [Guia de uso de queries_config.py](./QUERIES_CONFIG_GUIDE.md)
- [`Scripts/queries_config.py`](./Scripts/queries_config.py)
- [`Scripts/00_orquestador_general.py`](./Scripts/00_orquestador_general.py)
