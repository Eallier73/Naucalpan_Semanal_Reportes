# Configuracion Centralizada de Queries

Este documento explica como gestionar las queries y parametros de los extractores desde un unico lugar.

## Ubicacion

```text
Scripts/queries_config.py
```

## Que contiene

### 1. YouTube (`YOUTUBE_*`)

- `YOUTUBE_CHANNELS`
- `YOUTUBE_SEARCH_QUERIES`
- `YOUTUBE_DEFAULT_MAX_VIDEOS_QUERY`
- `YOUTUBE_DEFAULT_MAX_VIDEOS_CHANNEL`

Ejemplo actual:

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

### 2. Twitter/X (`TWITTER_*`)

- `TWITTER_SEARCH_QUERIES`
- `TWITTER_DEFAULT_MAX_TWEETS`
- `TWITTER_DEFAULT_MAX_REPLIES_PER_TWEET`
- `TWITTER_DEFAULT_MAX_REPLY_SCROLLS`

Ejemplo actual:

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

### 3. Medios (`MEDIOS_*`)

- `MEDIOS_SITES`
- `MEDIOS_SEARCH_TERMS`
- `MEDIOS_DEFAULT_MODE_QUERIES`
- pausas entre requests

Ejemplo actual:

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

### 4. Facebook (`FACEBOOK_*`)

- `FACEBOOK_PAGES`
- `FACEBOOK_COMMENTS_DEFAULT_MAX_COMMENTS`
- `FACEBOOK_POSTS_DEFAULT_MAX_POSTS`

Ejemplo actual:

```python
FACEBOOK_PAGES = [
    "GuardiaMunicipalCiudadNaucalpan",
    "isaacmontoya24",
    "CiudadNaucalpan",
]
```

## Como se usa

Los extractores y el orquestador importan esta configuracion directamente.

```python
from queries_config import YOUTUBE_CHANNELS, YOUTUBE_SEARCH_QUERIES

DEFAULT_CHANNEL_HANDLES = YOUTUBE_CHANNELS
DEFAULT_SEARCH_QUERIES = YOUTUBE_SEARCH_QUERIES
```

Para ver la configuracion completa:

```bash
python Scripts/queries_config.py
```

Salida esperada:

```json
{
  "youtube": {
    "channels": ["CiudadNaucalpan"],
    "search_queries": ["presidente municipal de naucalpan", "..."]
  },
  "twitter": {
    "search_queries": ["to:isaacsolar", "..."]
  }
}
```

## Flujo recomendado para cambios

1. Modificar `Scripts/queries_config.py`.
2. Confirmar que el extractor correspondiente use imports desde ese archivo.
3. Ejecutar el pipeline requerido.

## Nota de medios

Aunque la referencia operativa incluya URLs concretas como `https://oem.com.mx/la-prensa/tags/temas/naucalpan`, el extractor de medios consume Google News RSS y por eso usa filtros `site:` compatibles con ese mecanismo.
