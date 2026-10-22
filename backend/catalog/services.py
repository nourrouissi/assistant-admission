"""
Services métier du catalogue : la recherche de formations.

La même fonction sert à l'API REST (/api/formations/) et servira à l'outil
de recherche de l'assistant : une seule source de vérité pour la recherche.
"""

from __future__ import annotations

from functools import reduce
from operator import or_

from django.db.models import Q, QuerySet

from .models import Formation
from .normalization import fold

# Mots trop courants pour être utiles dans une recherche (déjà « pliés »).
STOP_WORDS = {
    "de", "des", "du", "en", "et", "la", "le", "les", "un", "une", "d", "l",
    "a", "au", "aux", "pour", "dans", "sur", "formation", "formations",
}

# Abréviations courantes des prospects -> forme présente dans les données.
# La recherche se fait par « contient », donc un début de mot suffit
# (« comptab » trouve « comptabilité » et « comptable »).
SYNONYMS = {
    "info": "informatique",
    "infos": "informatique",
    "compta": "comptab",
    "inge": "ingenieur",
    "ingenierie": "ingenieur",
    "deco": "decoration",
    "reseau": "reseau",
    "securite": "securite",
}


def _keywords(query: str) -> list[str]:
    """Découpe la requête en mots-clés utiles : sans accents, sans petits mots, synonymes appliqués."""
    words = fold(query).replace("'", " ").replace("-", " ").split()
    return [SYNONYMS.get(word, word) for word in words if word not in STOP_WORDS]


def search_formations(query: str = "", school: str = "", diploma_type: str = "") -> QuerySet[Formation]:
    """
    Recherche des formations actives.

    - `query` : mots libres (« informatique », « réseaux sécurité »). Chaque mot
      doit apparaître dans le texte de recherche (ET logique), sans tenir compte
      des accents ni des majuscules. Si aucun résultat avec plusieurs mots, on
      élargit en OU logique pour proposer quand même des formations proches
      (le sujet demande d'afficher des résultats « dès que possible »).
    - `school` : nom ou ville de l'école (« Sousse », « IMSET TUNIS »).
    - `diploma_type` : code normalisé (« BTS », « LICENCE »…).
    """
    queryset = Formation.objects.filter(is_active=True)

    if school:
        school_folded = fold(school)
        queryset = queryset.filter(Q(school__icontains=school_folded) | Q(city__iexact=school_folded))
    if diploma_type:
        queryset = queryset.filter(diploma_type=diploma_type.upper())

    keywords = _keywords(query)
    if not keywords:
        return queryset

    # 1) Tous les mots doivent être présents (résultats les plus précis)
    strict = queryset
    for word in keywords:
        strict = strict.filter(search_text__contains=word)
    if strict.exists() or len(keywords) == 1:
        return strict

    # 2) Repli : au moins un des mots (résultats plus larges)
    return queryset.filter(reduce(or_, (Q(search_text__contains=word) for word in keywords)))