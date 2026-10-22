"""
Agent conversationnel (LangGraph).

Graphe : START -> agent -> (outil demandé ?) -> tools -> relay -> END.
La réponse de l'outil est transmise telle quelle au candidat (nœud relay) :
l'agent ne la relit pas, il ne peut donc ni la modifier ni retirer le contact
des admissions ajouté par le code.
La Partie 3 ajoutera ses outils à TOOLS.
Les outils renvoient des blocs (texte, cartes de formations) affichés tels quels.
La conversation est gardée en mémoire par session (MemorySaver, développement).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from .llm import chat_models, with_fallbacks
from .tools import TOOLS

logger = logging.getLogger(__name__)

AGENT_PROMPT = """Tu es l'assistant d'admission des écoles IMSET.

Choisis l'outil selon la demande du candidat :
- search_procedure : questions sur la procédure d'admission, les étapes, les pièces justificatives, les dates limites, les frais, les conditions générales d'éligibilité, et toute autre demande d'information. Donne la question complète, compréhensible seule (reprends les éléments utiles des messages précédents).
- search_formations : dès que le candidat cherche des formations ou des spécialités (domaine, diplôme, école), même s'il n'a donné aucune information personnelle.
- check_eligibility : dès que le candidat donne son niveau d'études, sa nationalité ou la nature de son baccalauréat (y compris dans le même message que sa recherche, ex. « j'ai un bac informatique, quelles spécialités me correspondent ? » = niveau BAC, section INFORMATIQUE, mots-clés « informatique »), ou demande s'il est éligible. Donne toutes les informations de profil déjà indiquées dans la conversation, et les formations concernées (identifiants des formations déjà affichées, ou mots-clés, diplôme, école).
La réponse des outils est transmise directement au candidat.

Ne réponds jamais à une demande d'information de mémoire et n'invente aucune information.
Ne dis jamais toi-même qu'un candidat est éligible ou admis.
Tu ne réponds sans outil qu'aux salutations et aux remerciements.
Réponds en français et vouvoie toujours le candidat."""

# Message fixe si aucun modèle ou aucun outil ne répond : jamais de réponse inventée
UNAVAILABLE_MESSAGE = (
    "Je ne peux pas répondre pour le moment. Vous pouvez contacter le service des admissions : {contact}."
)


def _unavailable() -> str:
    return UNAVAILABLE_MESSAGE.format(contact=settings.ADMISSIONS_CONTACT)


def _tool_error(error: Exception) -> str:
    """Erreur dans un outil : message fixe pour le candidat, détail dans les logs."""
    logger.error("Assistant : erreur dans un outil : %r", error)
    return _unavailable()


def _agent_model() -> Runnable:
    """Chaque modèle connaît les outils, puis la chaîne de secours les enchaîne."""
    return with_fallbacks([model.bind_tools(TOOLS) for model in chat_models()])


def agent(state: MessagesState) -> dict:
    response = _agent_model().invoke([SystemMessage(AGENT_PROMPT), *state["messages"]])
    return {"messages": [response]}


def relay(state: MessagesState) -> dict:
    """
    Réponse finale = les blocs (texte, cartes) des outils qui viennent d'être appelés,
    sans modification. Les blocs sont rangés dans response_metadata, qui n'est jamais
    envoyé au LLM ; le texte reste dans l'historique de la conversation.
    """
    blocks: list[dict] = []
    for message in reversed(state["messages"]):
        if not isinstance(message, ToolMessage):
            break
        blocks[:0] = message.artifact or [{"type": "text", "text": _text(message.content)}]
    text = "\n\n".join(block["text"] for block in blocks if block["type"] == "text")
    return {"messages": [AIMessage(text, response_metadata={"blocks": blocks})]}


@lru_cache(maxsize=1)
def get_graph():
    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(TOOLS, handle_tool_errors=_tool_error))
    builder.add_node("relay", relay)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)   # outil demandé -> tools, sinon fin
    builder.add_edge("tools", "relay")
    builder.add_edge("relay", END)
    return builder.compile(checkpointer=MemorySaver())


def _text(content) -> str:
    """Contenu d'un message : texte simple ou liste de morceaux de texte."""
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


def reply(session_id: str, message: str) -> list[dict]:
    """Blocs de réponse (texte, cartes) au message du candidat, dans la conversation `session_id`."""
    try:
        state = get_graph().invoke(
            {"messages": [HumanMessage(message)]},
            config={"configurable": {"thread_id": session_id}},
        )
    except Exception:
        logger.exception("Assistant : aucun modèle n'a pu répondre (session %s)", session_id)
        return [{"type": "text", "text": _unavailable()}]
    last = state["messages"][-1]
    return last.response_metadata.get("blocks") or [{"type": "text", "text": _text(last.content).strip()}]
