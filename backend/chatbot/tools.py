"""
Outils de l'agent.

Chaque outil renvoie deux choses :
  - un résumé pour le LLM (il sait ce qui a été montré, pour la suite de la conversation) ;
  - les blocs affichés au candidat (texte et cartes), produits par le code et transmis
    tels quels par le nœud relay : le LLM n'écrit jamais lui-même un résultat.

Partie 1 : search_procedure.
Partie 2 : search_formations (recherche) et check_eligibility (vérification), deux
actions distinctes comme l'exige le sujet.
"""

from __future__ import annotations

import functools
import threading
from typing import Literal

from django.db import connections
from langchain_core.tools import tool

from catalog.eligibility import Profile
from catalog.serializers import MAX_EVALUATED, FormationSerializer
from catalog.services import eligibility_cards, formations_by_ids, search_catalog
from knowledge.rag import answer_procedure_question

DiplomaCode = Literal["", "CAP", "BTP", "BTS", "LICENCE", "LICENCE_PRO", "BACHELOR", "INGENIEUR", "TITRE_RNCP", "SHORT_COURSE"]
LevelCode = Literal["", "9EME", "2EME_SEC", "3EME_SEC", "4EME_SEC", "CAP", "BTP", "BAC", "BAC_PLUS_2", "LICENCE", "LICENCE_PLUS_1", "MASTER"]
BacSectionCode = Literal["", "MATH", "SCIENCES_EXP", "TECHNIQUE", "INFORMATIQUE", "ECONOMIE_GESTION", "LETTRES", "SPORT"]

ELIGIBILITY_OFFER = "Si vous souhaitez vérifier votre éligibilité, indiquez-moi : {items}."
NO_FORMATION = "Je n'ai trouvé aucune formation correspondant à votre demande."


def _closes_db_connection(func):
    """
    LangGraph exécute les outils dans des threads à part : chaque thread ouvre sa propre
    connexion PostgreSQL. Elle est fermée à la fin de l'outil pour ne pas en accumuler.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            if threading.current_thread() is not threading.main_thread():
                connections.close_all()
    return wrapper


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _cards_block(cards: list[dict]) -> dict:
    return {"type": "formations", "items": cards}


def _summary(cards: list[dict]) -> str:
    """Une ligne par formation montrée, avec son identifiant (utile pour la suite de la conversation)."""
    lines = []
    for card in cards:
        line = f"[id {card['id']}] {card['diploma']} – {card['specialty']} – {card['school']}"
        if "eligibility" in card:
            line += f" : {card['eligibility']['status']}"
        lines.append(line)
    return "\n".join(lines)


def _unmatched_sentence(unmatched: list[str]) -> str:
    words = ", ".join(f"« {word} »" for word in unmatched)
    return f"Aucune formation ne correspond à {words}."


# --- Partie 1 -----------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
@_closes_db_connection
def search_procedure(question: str):
    """Répond à une question sur la procédure d'admission : étapes, pièces justificatives,
    dates limites, frais, conditions générales d'éligibilité.
    `question` : la question du candidat, complète et compréhensible seule."""
    answer = answer_procedure_question(question)["answer"]
    return answer, [_text_block(answer)]


# --- Partie 2 -----------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
@_closes_db_connection
def search_formations(keywords: str = "", diploma_type: DiplomaCode = "", school: str = ""):
    """Recherche des formations dans le catalogue et les affiche au candidat sous forme de cartes
    (diplôme, spécialité, école, critères d'éligibilité). Ne vérifie pas l'éligibilité.
    `keywords` : mots-clés de spécialité ou de domaine (ex. « informatique », « comptabilité »), sans les
    informations de profil (bac, niveau, nationalité).
    `diploma_type` : CAP, BTP (Brevet de Technicien Professionnel), BTS (Brevet de Technicien Supérieur),
    LICENCE, LICENCE_PRO, BACHELOR, INGENIEUR, TITRE_RNCP (Concepteur en architecture informatique),
    SHORT_COURSE (formation courte).
    `school` : école ou ville (Gabès, Nabeul, Sfax, Sousse, Tunis)."""
    result = search_catalog(query=keywords, school=school, diploma_type=diploma_type)
    formations = list(result.formations)
    cards = FormationSerializer(formations, many=True).data

    sentences = []
    if result.unmatched_terms:
        sentences.append(_unmatched_sentence(result.unmatched_terms))
    if not cards:
        sentences.append(NO_FORMATION)
        text = " ".join(sentences)
        return text, [_text_block(text)]

    plural = "s" if len(cards) > 1 else ""
    sentences.append(f"Voici {len(cards)} formation{plural} correspondant à votre demande.")
    # Seules les informations utiles pour ces formations sont demandées
    _, needed = eligibility_cards(formations, Profile())
    if needed:
        sentences.append(ELIGIBILITY_OFFER.format(items=", ".join(needed)))
    text = " ".join(sentences)
    return f"{text}\nFormations affichées :\n{_summary(cards)}", [_text_block(text), _cards_block(cards)]


@tool(response_format="content_and_artifact")
@_closes_db_connection
def check_eligibility(
    level: LevelCode = "",
    nationality: str = "",
    bac_section: BacSectionCode = "",
    formation_ids: list[int] | None = None,
    keywords: str = "",
    diploma_type: DiplomaCode = "",
    school: str = "",
):
    """Vérifie l'éligibilité du candidat aux formations, à partir des informations qu'il a déclarées.
    Donner toutes les informations de profil déjà indiquées dans la conversation :
    `level` : niveau d'études (9EME : 9e année de base ; 2EME_SEC, 3EME_SEC, 4EME_SEC : années du secondaire ;
    CAP ; BTP ; BAC ; BAC_PLUS_2 : Bac+2 ou BTS ; LICENCE : Bac+3 ; LICENCE_PLUS_1 : Bac+4 ; MASTER : Bac+5).
    `nationality` : nationalité déclarée, en toutes lettres (ex. « tunisienne »).
    `bac_section` : section du bac ou du secondaire.
    Formations à vérifier : `formation_ids` (identifiants des formations déjà affichées), ou à défaut les mêmes
    filtres que search_formations (`keywords`, `diploma_type`, `school`)."""
    try:
        profile = Profile(level=level or None, nationality=nationality or None, bac_section=bac_section or None)
    except ValueError:
        text = "Je n'ai pas compris votre nationalité. Pouvez-vous l'indiquer en toutes lettres ?"
        return text, [_text_block(text)]

    sentences = []
    if formation_ids:
        formations, _unknown = formations_by_ids(formation_ids[:MAX_EVALUATED])
    else:
        result = search_catalog(query=keywords, school=school, diploma_type=diploma_type)
        formations = list(result.formations[:MAX_EVALUATED])
        if result.unmatched_terms:
            sentences.append(_unmatched_sentence(result.unmatched_terms))
    if not formations:
        sentences.append(NO_FORMATION)
        text = " ".join(sentences)
        return text, [_text_block(text)]

    cards, needed = eligibility_cards(formations, profile)
    sentences.append(
        "Voici la vérification des critères d'après les informations que vous avez indiquées. "
        "La décision finale revient à l'équipe des admissions."
    )
    if needed:
        sentences.append(f"Pour compléter la vérification, j'ai besoin de : {', '.join(needed)}.")
    text = " ".join(sentences)
    return f"{text}\nFormations vérifiées :\n{_summary(cards)}", [_text_block(text), _cards_block(cards)]


TOOLS = [search_procedure, search_formations, check_eligibility]
