"""Réglages communs aux tests."""

import pytest
from django.core.cache import cache

from chatbot import graph


@pytest.fixture(autouse=True)
def chat_memory_in_ram(settings):
    """Conversations en mémoire vive, nouveau graphe et compteurs de requêtes remis à zéro à chaque test."""
    settings.CHAT_MEMORY = "memory"
    graph.get_graph.cache_clear()
    cache.clear()
    yield
    graph.get_graph.cache_clear()
