"""
Agent conversationnel (LangGraph).

Graphe :
  START -> agent -> (outil demandé ?) -> tools -> relay -> (inscription en cours ?) -> END
  START -> registration_ask (bouton « S'inscrire ») : demande des coordonnées
  START -> registration_collect (message pendant la collecte) : le LLM extrait, le code valide
           -> registration_ask (manquant ou invalide) | registration_summary | agent (autre question)
  registration_summary : pause, puis Confirmer / Modifier / Annuler (boutons)

- Les outils renvoient des blocs (texte, cartes de formations) transmis tels quels
  au prospect par le nœud relay : l'agent ne les relit pas.
- Une inscription en cours est gardée dans l'état `registration`. Les messages qui
  contiennent des coordonnées sont retirés de l'historique : l'agent ne les voit jamais.
  Après une question libre, l'étape en cours (question ou récapitulatif) est reprise.
- La conversation est enregistrée par session dans PostgreSQL (voir memory.py).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from .llm import chat_models, with_fallbacks
from .memory import checkpointer
from .registration_flow import (
    SUMMARY_ACTIONS,
    new_registration,
    registration_ask,
    registration_cancel,
    registration_collect,
    registration_summary,
)
from .tools import TOOLS

logger = logging.getLogger(__name__)


class ChatState(MessagesState):
    event: str                    # « message », « register » (bouton S'inscrire) ou « cancel »
    registration: dict | None     # inscription en cours (formation, étape, coordonnées)


AGENT_PROMPT = """Tu es l'assistant d'admission des écoles IMSET.

Choisis l'outil selon la demande du candidat :
- search_procedure : questions sur la procédure d'admission, les étapes, les pièces justificatives, les dates limites, les frais, les conditions générales d'éligibilité, et toute autre demande d'information. Donne la question complète, compréhensible seule (reprends les éléments utiles des messages précédents).
- search_formations : dès que le candidat cherche des formations ou des spécialités (domaine, diplôme, école), même s'il n'a donné aucune information personnelle.
- check_eligibility : dès que le candidat donne son niveau d'études, sa nationalité ou la nature de son baccalauréat (y compris dans le même message que sa recherche, ex. « j'ai un bac informatique, quelles spécialités me correspondent ? » = niveau BAC, section INFORMATIQUE, mots-clés « informatique »), ou demande s'il est éligible. Donne toutes les informations de profil déjà indiquées dans la conversation, et les formations concernées (identifiants des formations déjà affichées, ou mots-clés, diplôme, école).
- start_registration : dès que le candidat souhaite s'inscrire ou déposer une demande pour une formation (identifiant d'une formation déjà affichée, ou mots-clés, diplôme, école).
La réponse des outils est transmise directement au candidat.

Ne réponds jamais à une demande d'information de mémoire et n'invente aucune information.
Ne dis jamais toi-même qu'un candidat est éligible, inscrit ou admis.
Ne demande jamais toi-même le nom, le prénom, l'e-mail ou le téléphone du candidat : ils sont demandés par l'étape d'inscription, après start_registration.
Tu ne réponds sans outil qu'aux salutations, aux remerciements et aux messages sur une inscription en cours.
Réponds en français et vouvoie toujours le candidat."""

PENDING_COLLECT = "indiquer ses coordonnées, qui lui seront redemandées après ta réponse"
PENDING_SUMMARY = (
    "utiliser le récapitulatif, avec les boutons Confirmer, Modifier ou Annuler, qui lui sera réaffiché après ta réponse"
)
PENDING_PROMPT = (
    "\n\nUne demande d'inscription est en cours : le candidat doit {step}. Un message écrit (« oui », "
    "« je confirme ») ne confirme pas la demande : s'il veut confirmer, modifier ou annuler, invite-le en une "
    "phrase à utiliser les boutons, sans appeler d'outil."
)

# Message fixe si aucun modèle ou aucun outil ne répond : jamais de réponse inventée
UNAVAILABLE_MESSAGE = (
    "Je ne peux pas répondre pour le moment. Vous pouvez contacter le service des admissions : {contact}."
)
NO_PENDING_REGISTRATION = "Aucune demande d'inscription n'est en cours."
COLLECT_IN_PROGRESS = (
    "Votre demande ne peut pas encore être confirmée : indiquez d'abord votre nom, votre prénom, "
    "votre adresse e-mail et votre numéro de téléphone."
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


def _system_prompt(state: ChatState) -> str:
    registration = state.get("registration")
    if not registration:
        return AGENT_PROMPT
    step = PENDING_COLLECT if registration["stage"] == "collect" else PENDING_SUMMARY
    return AGENT_PROMPT + PENDING_PROMPT.format(step=step)


def agent(state: ChatState) -> dict:
    response = _agent_model().invoke([SystemMessage(_system_prompt(state)), *state["messages"]])
    return {"messages": [response]}


def relay(state: ChatState) -> dict:
    """
    Réponse finale = les blocs (texte, cartes) des outils qui viennent d'être appelés,
    sans modification. Les blocs sont rangés dans response_metadata, qui n'est jamais
    envoyé au LLM ; le texte reste dans l'historique de la conversation.
    """
    blocks: list[dict] = []
    for message in reversed(state["messages"]):
        if not isinstance(message, ToolMessage):
            break
        blocks[:0] = message.artifact if message.artifact is not None else [
            {"type": "text", "text": _text(message.content)}
        ]
    if not blocks:       # ex. début d'inscription : la question est posée par le nœud suivant
        return {}
    text = "\n\n".join(block["text"] for block in blocks if block["type"] == "text")
    return {"messages": [AIMessage(text, response_metadata={"blocks": blocks})]}


# --- Routage ---------------------------------------------------------------------------------

def route_start(state: ChatState) -> str:
    event = state.get("event")
    if event == "register":
        return "registration_ask"
    if event == "cancel":
        return "registration_cancel"
    registration = state.get("registration")
    if registration and registration["stage"] == "collect":
        return "registration_collect"
    return "agent"


def route_pending(state: ChatState) -> str:
    """Inscription en cours : reprendre son étape (question des coordonnées ou récapitulatif)."""
    registration = state.get("registration")
    if not registration:
        return END
    return "registration_ask" if registration["stage"] == "collect" else "registration_summary"


def route_after_agent(state: ChatState) -> str:
    return "tools" if state["messages"][-1].tool_calls else route_pending(state)


@lru_cache(maxsize=1)
def get_graph():
    builder = StateGraph(ChatState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(TOOLS, handle_tool_errors=_tool_error))
    builder.add_node("relay", relay)
    builder.add_node("registration_ask", registration_ask, destinations=(END,))
    builder.add_node(
        "registration_collect", registration_collect,
        destinations=("registration_ask", "registration_summary", "agent", END),
    )
    builder.add_node("registration_summary", registration_summary, destinations=("registration_ask", END))
    builder.add_node("registration_cancel", registration_cancel, destinations=(END,))
    builder.add_conditional_edges(
        START, route_start, ["agent", "registration_ask", "registration_collect", "registration_cancel"],
    )
    pending = ["registration_ask", "registration_summary", END]
    builder.add_conditional_edges("agent", route_after_agent, ["tools", *pending])
    builder.add_edge("tools", "relay")
    builder.add_conditional_edges("relay", route_pending, pending)
    return builder.compile(checkpointer=checkpointer())


# --- Appels depuis l'API ------------------------------------------------------------------------

def _text(content) -> str:
    """Contenu d'un message : texte simple ou liste de morceaux de texte."""
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _run(session_id: str, graph_input) -> list[dict]:
    """
    Exécute le graphe et renvoie les blocs à afficher : réponses produites pendant ce tour,
    puis le récapitulatif d'inscription en attente, s'il y en a un.
    """
    graph = get_graph()
    config = _config(session_id)
    try:
        before = len(graph.get_state(config).values.get("messages", []))
        result = graph.invoke(graph_input, config=config)
    except Exception:
        # Modèles indisponibles, base de données, etc. : le détail est dans la trace ci-dessous
        logger.exception("Assistant : message non traité (session %s)", session_id)
        return [{"type": "text", "text": _unavailable()}]

    blocks: list[dict] = []
    for message in result["messages"][before:]:
        if isinstance(message, AIMessage) and not message.tool_calls:
            text = _text(message.content).strip()
            blocks += message.response_metadata.get("blocks") or ([{"type": "text", "text": text}] if text else [])
    for pending in result.get("__interrupt__", []):
        blocks += pending.value["blocks"]
    if not blocks:      # jamais de tour sans réponse affichée
        logger.error("Assistant : aucune réponse produite (session %s)", session_id)
        return [{"type": "text", "text": _unavailable()}]
    return blocks


def reply(session_id: str, message: str) -> list[dict]:
    """Message écrit du prospect."""
    return _run(session_id, {"messages": [HumanMessage(message)], "event": "message"})


def register(session_id: str, formation_id: int) -> list[dict]:
    """Bouton « S'inscrire » d'une carte : l'identifiant exact de la formation est connu."""
    return _run(session_id, {"event": "register", "registration": new_registration(formation_id)})


def registration_stage(session_id: str) -> str | None:
    """
    Étape de l'inscription en cours, pour l'interface : « collect » (coordonnées demandées,
    bouton Annuler), « summary » (récapitulatif en attente des boutons) ou None.
    """
    try:
        registration = get_graph().get_state(_config(session_id)).values.get("registration")
    except Exception:
        logger.exception("Assistant : état de l'inscription illisible (session %s)", session_id)
        return None
    return registration["stage"] if registration else None


def registration_action(session_id: str, action: str) -> list[dict]:
    """Bouton Confirmer / Modifier / Annuler du récapitulatif, ou Annuler pendant la collecte."""
    state = get_graph().get_state(_config(session_id))
    registration = state.values.get("registration")
    if not registration:
        return [{"type": "text", "text": NO_PENDING_REGISTRATION}]
    if registration["stage"] == "collect":
        if action == "cancel":
            return _run(session_id, {"event": "cancel"})
        return [{"type": "text", "text": COLLECT_IN_PROGRESS}]     # rien à confirmer avant le récapitulatif
    if not state.interrupts or action not in SUMMARY_ACTIONS:
        return [{"type": "text", "text": NO_PENDING_REGISTRATION}]
    return _run(session_id, Command(resume={"action": action}))
