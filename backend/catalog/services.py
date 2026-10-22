"""
Services métier du catalogue : la recherche de formations.

La même fonction sert à l'API REST (/api/formations/) et servira à l'outil
de recherche de l'assistant : une seule source de vérité pour la recherche.

Répartition des rôles : le LLM comprend la demande du prospect et en extrait
des mots-clés (« informatique »), le type de diplôme et l'école ; cette
recherche, elle, reste déterministe et ne contient aucune règle de langue
écrite à la main (ni synonymes, ni mots vides, ni domaines).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import reduce
from operator import and_

from django.db.models import Q, QuerySet

from .models import Formation
from .normalization import fold

# Les mots de moins de 3 lettres (« j », « en », « de ») sont ignorés :
# cherchés en début de mot, ils trouvaient n'importe quoi.
MIN_WORD_LENGTH = 3


def _keywords(query: str) -> list[str]:
    """
    Découpe la requête en mots-clés : texte plié (minuscules, sans accents),
    découpé sur tout ce qui n'est pas lettre ou chiffre, sans les mots trop
    courts ni les doublons.
    """
    keywords: list[str] = []
    for word in re.findall(r"[a-z0-9]+", fold(query)):
        if len(word) >= MIN_WORD_LENGTH and word not in keywords:
            keywords.append(word)
    return keywords


def _starts_a_word(term: str) -> Q:
    """
    « Un mot du texte de recherche commence par `term` ».

    Une recherche « contient » trouverait le mot au milieu d'un autre
    (« mobile » dans « automobile »). Expression régulière PostgreSQL : début
    du texte ou caractère qui n'est ni lettre ni chiffre, puis le terme
    (le texte de recherche est déjà plié, sans accents).
    """
    return Q(search_text__regex=rf"(^|[^a-z0-9]){re.escape(term)}")


@dataclass
class SearchResult:
    """
    Résultat d'une recherche.

    - `formations` : les formations trouvées ;
    - `unmatched_terms` : mots-clés qui ne correspondent à aucune formation du
      catalogue, retirés de la recherche (le chatbot ne doit pas présenter les
      résultats comme répondant à ces mots).
    """

    formations: QuerySet[Formation]
    unmatched_terms: list[str] = field(default_factory=list)


def search_catalog(query: str = "", school: str = "", diploma_type: str = "") -> SearchResult:
    """
    Recherche des formations actives, avec le détail des mots non trouvés.

    - `query` : mots-clés (« informatique », « réseaux sécurité »). Chaque mot
      doit commencer un mot des données (ET logique), sans tenir compte des
      accents ni des majuscules. Un mot qui ne correspond à aucune formation du
      catalogue (« cuisine », « Monastir ») est retiré et signalé dans
      `unmatched_terms` ; si tous les mots sont dans ce cas, aucune formation
      n'est renvoyée. Sans mot-clé, tout le catalogue est renvoyé.
    - `school` : nom ou ville de l'école (« Sousse », « IMSET TUNIS »).
    - `diploma_type` : code normalisé (« BTS », « LICENCE »…), validé en amont
      par le sérialiseur (voir SearchParamsSerializer).
    """
    queryset = Formation.objects.filter(is_active=True)

    if school:
        school_folded = fold(school)
        queryset = queryset.filter(Q(school__icontains=school_folded) | Q(city__iexact=school_folded))
    if diploma_type:
        queryset = queryset.filter(diploma_type=diploma_type.upper())

    keywords = _keywords(query)
    if not keywords:
        return SearchResult(queryset)

    # Mots absents de tout le catalogue actif : retirés et signalés
    catalog = Formation.objects.filter(is_active=True)
    unmatched = [word for word in keywords if not catalog.filter(_starts_a_word(word)).exists()]
    filters = [_starts_a_word(word) for word in keywords if word not in unmatched]
    if not filters:
        return SearchResult(queryset.none(), unmatched)

    # Tous les mots restants doivent être trouvés : aucun élargissement
    return SearchResult(queryset.filter(reduce(and_, filters)), unmatched)


def search_formations(query: str = "", school: str = "", diploma_type: str = "") -> QuerySet[Formation]:
    """Raccourci : uniquement les formations trouvées par search_catalog()."""
    return search_catalog(query, school, diploma_type).formations


def formations_by_ids(ids: list[int]) -> tuple[list[Formation], list[int]]:
    """
    Formations actives demandées par identifiant, et identifiants introuvables.

    Un identifiant inconnu ou d'une formation désactivée est renvoyé dans la
    seconde liste (dans l'ordre de la demande, sans doublon) : l'appelant peut
    le signaler au lieu de l'ignorer en silence.
    """
    formations = list(Formation.objects.filter(id__in=ids, is_active=True))
    found = {formation.id for formation in formations}
    unknown = [formation_id for formation_id in dict.fromkeys(ids) if formation_id not in found]
    return formations, unknown
