"""
Accès aux vecteurs : calcul des embeddings et recherche des extraits proches.

Tout ce qui touche aux vecteurs est isolé ici. Modèle multilingual-e5, exécuté
en local : il exige le préfixe « passage: » pour les textes indexés et
« query: » pour les questions.
"""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pgvector.django import CosineDistance

from .models import EMBEDDING_DIMENSIONS, ProcedureChunk

# Nombre d'extraits transmis au LLM
TOP_K = 3


@lru_cache(maxsize=1)
def _encoder():
    """Charge le modèle d'embeddings une seule fois (téléchargé au premier lancement)."""
    if settings.EMBEDDINGS_PROVIDER != "local":
        raise ImproperlyConfigured("EMBEDDINGS_PROVIDER : seule la valeur « local » est prise en charge.")
    if not settings.EMBEDDINGS_MODEL:
        raise ImproperlyConfigured("EMBEDDINGS_MODEL est vide dans le fichier .env.")
    from sentence_transformers import SentenceTransformer  # import lourd : seulement si nécessaire

    return SentenceTransformer(settings.EMBEDDINGS_MODEL)


def _embed(text: str) -> list[float]:
    vector = _encoder().encode(text, normalize_embeddings=True).tolist()
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ImproperlyConfigured(
            f"Le modèle d'embeddings renvoie {len(vector)} dimensions, {EMBEDDING_DIMENSIONS} attendues."
        )
    return vector


def embed_passage(text: str) -> list[float]:
    """Vecteur d'un extrait à indexer."""
    return _embed(f"passage: {text}")


def embed_query(question: str) -> list[float]:
    """Vecteur d'une question."""
    return _embed(f"query: {question}")


def search(question: str, k: int = TOP_K) -> list[ProcedureChunk]:
    """Les k extraits les plus proches de la question (similarité cosinus)."""
    vector = embed_query(question)
    return list(
        ProcedureChunk.objects.annotate(distance=CosineDistance("embedding", vector)).order_by("distance")[:k]
    )
