"""
Tests de la Partie 2 dans le chatbot : outils search_formations et check_eligibility.

Aucun appel réseau : l'agent (LLM) est simulé ; les outils utilisent le vrai catalogue.
"""

import re

import pytest
from django.conf import settings
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from rest_framework.test import APIClient

from catalog.importer import import_formations
from chatbot import graph
from chatbot.tools import check_eligibility, search_formations

pytestmark = pytest.mark.django_db

EXCEL = settings.BASE_DIR / "data" / "diplome_specialite.xlsx"
ADMISSION_PROMISE = re.compile(r"\badmise?s?\b|\béligible\b|garanti", re.IGNORECASE)


@pytest.fixture(autouse=True)
def imported():
    import_formations(EXCEL)


def blocks_of(tool, **args):
    _summary, blocks = tool.func(**args)
    return blocks


def cards_of(blocks):
    return next(block["items"] for block in blocks if block["type"] == "formations")


# --- Recherche ------------------------------------------------------------------------

def test_search_shows_cards_with_diploma_specialty_school_and_criteria():
    blocks = blocks_of(search_formations, keywords="informatique")
    assert blocks[0] == {"type": "text", "text": (
        "Voici 28 formations correspondant à votre demande. "
        "Si vous souhaitez vérifier votre éligibilité, indiquez-moi : niveau d'études."
    )}
    card = cards_of(blocks)[0]
    assert {"diploma", "specialty", "school", "criteria"} <= card.keys()


def test_search_never_gives_an_eligibility_status():
    for card in cards_of(blocks_of(search_formations, keywords="batiment")):
        assert "eligibility" not in card


def test_search_asks_only_the_information_needed_for_the_formations_shown():
    text = blocks_of(search_formations, keywords="batiment")[0]["text"]
    assert text.endswith("indiquez-moi : niveau d'études, nationalité.")


def test_search_without_result_says_so():
    assert blocks_of(search_formations, keywords="cuisine") == [{"type": "text", "text": (
        "Aucune formation ne correspond à « cuisine ». "
        "Je n'ai trouvé aucune formation correspondant à votre demande."
    )}]


def test_search_combines_diploma_and_school():
    cards = cards_of(blocks_of(search_formations, keywords="reseaux", diploma_type="BTS", school="Tunis"))
    assert {card["school"] for card in cards} == {"IMSET TUNIS"}


# --- Vérification de l'éligibilité --------------------------------------------------------------

def test_eligibility_cards_are_sorted_and_never_promise_admission():
    blocks = blocks_of(check_eligibility, level="BAC", bac_section="INFORMATIQUE", keywords="informatique")
    statuses = [card["eligibility"]["status"] for card in cards_of(blocks)]
    order = ["compatible", "a_confirmer", "incomplet", "non_compatible"]
    assert [order.index(s) for s in statuses] == sorted(order.index(s) for s in statuses)
    assert not ADMISSION_PROMISE.search(blocks[0]["text"])
    assert "La décision finale revient à l'équipe des admissions." in blocks[0]["text"]


def test_eligibility_asks_for_missing_information():
    text = blocks_of(check_eligibility, level="BAC_PLUS_2", keywords="batiment")[0]["text"]
    assert text.endswith("Pour compléter la vérification, j'ai besoin de : nationalité.")


def test_eligibility_by_formation_ids():
    ids = [card["id"] for card in cards_of(blocks_of(search_formations, keywords="batiment"))]
    cards = cards_of(blocks_of(check_eligibility, level="BAC_PLUS_2", nationality="tunisienne", formation_ids=ids))
    assert [card["eligibility"]["status"] for card in cards] == ["compatible"]


def test_invalid_nationality_is_asked_again():
    assert blocks_of(check_eligibility, nationality="123", keywords="batiment") == [{"type": "text", "text": (
        "Je n'ai pas compris votre nationalité. Pouvez-vous l'indiquer en toutes lettres ?"
    )}]


# --- Dans le chatbot -----------------------------------------------------------------------

def agent_calling(name, args):
    """Agent simulé qui demande un seul outil."""
    return lambda: RunnableLambda(lambda _messages: AIMessage(content="", tool_calls=[
        {"name": name, "args": args, "id": "call-1"},
    ]))


def chat(message, session_id="test-formations"):
    return APIClient().post("/api/chat/", {"session_id": session_id, "message": message}, format="json").json()


# Les outils s'exécutent dans un autre thread (LangGraph) : il faut des données réellement
# enregistrées, visibles depuis une autre connexion (transaction=True).
@pytest.mark.django_db(transaction=True)
def test_chat_shows_formation_cards(monkeypatch):
    monkeypatch.setattr(graph, "_agent_model", agent_calling("search_formations", {"keywords": "informatique"}))
    blocks = chat("Quelles spécialités proposez-vous en informatique ?")["blocks"]
    assert [block["type"] for block in blocks] == ["text", "formations"]
    assert len(blocks[1]["items"]) == 28


def test_tool_error_gives_the_fixed_message(monkeypatch):
    monkeypatch.setattr(graph, "_agent_model", agent_calling("search_formations", {"diploma_type": "XYZ"}))
    blocks = chat("Formations XYZ ?", session_id="test-error")["blocks"]
    assert blocks == [{"type": "text", "text": (
        f"Je ne peux pas répondre pour le moment. Vous pouvez contacter le service des admissions : {settings.ADMISSIONS_CONTACT}."
    )}]
