"""
Tests de la Partie 1 (questions sur la procédure d'admission).

Aucun appel réseau : le LLM et les embeddings sont remplacés par des versions simulées.
"""

import pytest
from django.conf import settings
from django.core.management import call_command
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from rest_framework.test import APIClient

from chatbot import graph
from knowledge import indexing, rag
from knowledge.indexing import read_sections
from knowledge.models import EMBEDDING_DIMENSIONS, ProcedureChunk
from knowledge.rag import ProcedureAnswer, answer_procedure_question

CONTACT = settings.ADMISSIONS_CONTACT


def fake_vector(_text: str) -> list[float]:
    return [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)


def fake_chain(answer: str, coverage: str):
    """Chaîne LLM simulée qui renvoie toujours la même réponse structurée."""
    return lambda: RunnableLambda(lambda _messages: ProcedureAnswer(answer=answer, coverage=coverage))


@pytest.fixture
def no_retrieval(monkeypatch):
    monkeypatch.setattr(rag.retrieval, "search", lambda question: [])


# --- Découpage et indexation ----------------------------------------------------------

def test_document_gives_sections_1_to_5_without_section_6():
    sections = read_sections(settings.PROCEDURE_DOCUMENT)
    assert [section.number for section in sections] == [1, 2, 3, 4, 5]
    assert all("Questions sans réponse" not in section.text for section in sections)
    pieces = next(section for section in sections if section.number == 2).text
    assert pieces.startswith("2. Pièces justificatives à fournir")
    assert "- Une photo d’identité récente." in pieces


@pytest.mark.django_db
def test_index_procedure_can_be_run_twice_without_duplicates(monkeypatch):
    monkeypatch.setattr(indexing.retrieval, "embed_passage", fake_vector)
    call_command("index_procedure")
    call_command("index_procedure")
    assert ProcedureChunk.objects.count() == 5
    assert list(ProcedureChunk.objects.values_list("section_number", flat=True)) == [1, 2, 3, 4, 5]


# --- Orientation vers le service des admissions -------------------------------------------

@pytest.mark.parametrize("coverage", ["partial", "none"])
def test_contact_is_added_when_answer_is_partial_or_missing(monkeypatch, no_retrieval, coverage):
    monkeypatch.setattr(rag, "_answer_chain", fake_chain("Je n'ai pas cette information.", coverage))
    result = answer_procedure_question("Y a-t-il des bourses ?")
    assert result["coverage"] == coverage
    assert result["answer"].endswith(f"service des admissions : {CONTACT}.")


def test_contact_is_not_added_when_answer_is_complete(monkeypatch, no_retrieval):
    monkeypatch.setattr(rag, "_answer_chain", fake_chain("Il faut une photo d'identité récente.", "complete"))
    result = answer_procedure_question("Quels documents fournir ?")
    assert result["answer"] == "Il faut une photo d'identité récente."


def test_contact_is_not_repeated_when_already_given(monkeypatch, no_retrieval):
    answer = f"Je n'ai pas cette date. Contactez le service des admissions : {CONTACT}."
    monkeypatch.setattr(rag, "_answer_chain", fake_chain(answer, "partial"))
    assert answer_procedure_question("Date limite ?")["answer"].count(CONTACT) == 1


def test_fixed_message_when_every_model_fails(monkeypatch, no_retrieval):
    def failing_chain():
        def fail(_messages):
            raise RuntimeError("quota dépassé")
        return RunnableLambda(fail)

    monkeypatch.setattr(rag, "_answer_chain", failing_chain)
    result = answer_procedure_question("Quels documents fournir ?")
    assert result["answer"] == f"Je ne peux pas répondre pour le moment. Vous pouvez contacter le service des admissions : {CONTACT}."
    assert result["coverage"] == "none"


# --- API du chatbot -------------------------------------------------------------------

def test_tool_answer_reaches_the_candidate_unchanged(monkeypatch):
    # L'agent demande l'outil ; la réponse de l'outil est transmise sans être relue par l'agent.
    from chatbot import tools

    calls = []

    def fake_agent(_messages):
        calls.append(1)
        return AIMessage(content="", tool_calls=[
            {"name": "search_procedure", "args": {"question": "Y a-t-il des bourses ?"}, "id": "call-1"},
        ])

    expected = f"Je n'ai pas cette information. Pour plus de précisions, vous pouvez contacter le service des admissions : {CONTACT}."
    monkeypatch.setattr(graph, "_agent_model", lambda: RunnableLambda(fake_agent))
    monkeypatch.setattr(tools, "answer_procedure_question", lambda question: {"answer": expected})
    response = APIClient().post("/api/chat/", {"session_id": "test-2", "message": "Y a-t-il des bourses ?"}, format="json")
    assert response.json()["blocks"] == [{"type": "text", "text": expected}]
    assert len(calls) == 1          # l'agent n'est appelé qu'une fois : il ne relit pas la réponse


def test_chat_endpoint_returns_a_text_block(monkeypatch):
    monkeypatch.setattr(graph, "_agent_model", lambda: RunnableLambda(lambda _messages: AIMessage(content="Bonjour !")))
    response = APIClient().post("/api/chat/", {"session_id": "test-1", "message": "Bonjour"}, format="json")
    assert response.status_code == 200
    assert response.json() == {"session_id": "test-1", "blocks": [{"type": "text", "text": "Bonjour !"}]}
