"""
Modèles de langage de l'assistant, tous appelés via une API compatible OpenAI.

Chaîne de secours : modèle principal -> second modèle du même fournisseur
(quota séparé) -> autre fournisseur. Un modèle sans nom ou sans clé dans le
.env est simplement absent de la chaîne. Les noms de modèles ne sont jamais
écrits dans le code.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

# Délai maximal d'un appel avant de passer au modèle suivant (secondes)
TIMEOUT_SECONDS = 30


def chat_models() -> list[ChatOpenAI]:
    """Les modèles configurés, dans l'ordre de la chaîne de secours. Température 0."""
    candidates = [
        (settings.LLM_PRIMARY_BASE_URL, settings.LLM_PRIMARY_API_KEY, settings.LLM_PRIMARY_MODEL),
        (settings.LLM_PRIMARY_BASE_URL, settings.LLM_PRIMARY_API_KEY, settings.LLM_SECONDARY_MODEL),
        (settings.LLM_FALLBACK_BASE_URL, settings.LLM_FALLBACK_API_KEY, settings.LLM_FALLBACK_MODEL),
    ]
    models = [
        ChatOpenAI(base_url=url, api_key=key, model=model, temperature=0, timeout=TIMEOUT_SECONDS, max_retries=1)
        for url, key, model in candidates
        if url and key and model
    ]
    if not models:
        raise ImproperlyConfigured("Aucun modèle de langage configuré : voir les variables LLM_* du fichier .env.")
    return models


def with_fallbacks(runnables: list[Runnable]) -> Runnable:
    """Enchaîne des modèles déjà préparés (sortie structurée, outils) : le suivant prend le relais en cas d'erreur."""
    first, *others = runnables
    return first.with_fallbacks(others) if others else first
