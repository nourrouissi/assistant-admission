"""Chaîne de secours des modèles : une réponse vide passe la main au modèle suivant."""

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from chatbot.llm import with_fallbacks


def _model(answer):
    return RunnableLambda(lambda _messages: answer)


def test_empty_answer_falls_back_to_next_model():
    # Ex. Gemini « MALFORMED_FUNCTION_CALL » : ni texte ni appel d'outil
    chain = with_fallbacks([_model(AIMessage("")), _model(AIMessage("Bonjour"))])
    assert chain.invoke([]).content == "Bonjour"


def test_missing_structured_output_falls_back_to_next_model():
    chain = with_fallbacks([_model(None), _model({"answer": "ok"})])
    assert chain.invoke([]) == {"answer": "ok"}


def test_tool_call_without_text_is_kept():
    call = AIMessage("", tool_calls=[{"name": "search_formations", "args": {}, "id": "1"}])
    chain = with_fallbacks([_model(call), _model(AIMessage("autre"))])
    assert chain.invoke([]).tool_calls[0]["name"] == "search_formations"
