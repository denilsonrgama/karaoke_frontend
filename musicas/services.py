# musicas/services.py
import requests
from functools import lru_cache
from django.conf import settings

API_BASE_URL = getattr(settings, "API_MUSICAS_URL", "http://localhost:8000/api/musicas/")

@lru_cache(maxsize=128)
def buscar_musicas(pagina=1, artista=None, nome=None, codigo=None):
    params = {"page": pagina}

    if codigo:
        params["codigo"] = codigo
    if artista:
        params["artista"] = artista
    if nome:
        params["nome"] = nome

    response = requests.get(API_BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    return {
        "lista": data.get("results", []),
        "total": data.get("count", 0),
        "next": data.get("next"),
        "previous": data.get("previous"),
    }


def buscar_musica_por_codigo(codigo):
    url = f"{API_BASE_URL}{codigo}/"
    response = requests.get(url, timeout=10)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()