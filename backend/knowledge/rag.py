"""
Réponses aux questions sur la procédure d'admission (RAG).

Exigences du sujet appliquées ici :
  - répondre à partir du document « Procédure d'admission », sans rien inventer ;
  - si la réponse est introuvable ou incomplète, le signaler et orienter vers le
    service des admissions. Cette orientation est ajoutée par le code : elle ne
    dépend pas du LLM.
"""

from __future__ import annotations

import logging
from typing import Literal

from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from chatbot.llm import chat_models, with_fallbacks

from . import retrieval

logger = logging.getLogger(__name__)


class ProcedureAnswer(BaseModel):
    """Réponse structurée du LLM."""

    answer: str = Field(description="Réponse au candidat, en français.")
    coverage: Literal["complete", "partial", "none"] = Field(
        description=(
            "complete : les informations répondent entièrement à la question ; "
            "partial : elles n'y répondent qu'en partie ; "
            "none : elles ne contiennent pas la réponse."
        )
    )


# Les règles de la section 6 du document (« Questions sans réponse ») sont reprises ici.
SYSTEM_PROMPT = """Tu es conseiller d'admission des écoles IMSET. Tu réponds aux questions des candidats sur la procédure d'admission.

Règles :
1. Réponds uniquement à partir des informations fournies dans le message. N'utilise aucune autre connaissance.
2. N'invente jamais de date, de tarif, de montant ou de condition d'admission. Si le candidat cite une date ou un montant qui ne figure pas dans les informations, ne le confirme pas.
3. Si l'information est absente, dis clairement que tu ne l'as pas. Si elle est incomplète, donne ce qui est connu et dis ce qui manque.
4. Quand l'information manque, propose de contacter le service des admissions : {contact}.
5. Ne confirme jamais qu'un candidat est éligible ou admis. Donne les critères généraux et propose de rechercher les formations qui correspondent à son profil.
6. Réponds en français, naturellement et simplement, à la première personne, comme un conseiller d'admission. Vouvoie toujours le candidat.
7. N'emploie jamais les mots « document », « extrait », « source » ou « contexte »."""

# Phrase ajoutée par le code quand la réponse est partielle ou absente
CONTACT_SENTENCE = "Pour plus de précisions, vous pouvez contacter le service des admissions : {contact}."

# Message fixe quand aucun modèle ne répond (quota, réseau) : jamais de réponse inventée
UNAVAILABLE_MESSAGE = (
    "Je ne peux pas répondre pour le moment. Vous pouvez contacter le service des admissions : {contact}."
)


def _answer_chain() -> Runnable:
    """Chaque modèle produit la sortie structurée, puis la chaîne de secours les enchaîne."""
    return with_fallbacks([
        model.with_structured_output(ProcedureAnswer, method="function_calling") for model in chat_models()
    ])


def _user_message(question: str, chunks) -> str:
    information = "\n\n".join(chunk.content for chunk in chunks) or "(aucune information)"
    return f"Informations :\n{information}\n\nQuestion du candidat : {question}"


def answer_procedure_question(question: str) -> dict:
    """
    Répond à une question sur la procédure d'admission.

    Retour : {"answer": str, "coverage": "complete" | "partial" | "none", "sections": [numéros]}.
    `sections` (sections retrouvées) sert aux logs et aux tests, pas à l'affichage.
    """
    contact = settings.ADMISSIONS_CONTACT
    sections: list[int] = []
    try:
        chunks = retrieval.search(question)
        sections = [chunk.section_number for chunk in chunks]
        result: ProcedureAnswer = _answer_chain().invoke([
            SystemMessage(SYSTEM_PROMPT.format(contact=contact)),
            HumanMessage(_user_message(question, chunks)),
        ])
    except Exception:
        logger.exception("RAG procédure : aucun modèle n'a pu répondre (sections %s)", sections)
        return {"answer": UNAVAILABLE_MESSAGE.format(contact=contact), "coverage": "none", "sections": sections}

    answer = result.answer.strip()
    if result.coverage != "complete" and contact not in answer:
        answer = f"{answer} {CONTACT_SENTENCE.format(contact=contact)}"
    logger.info("RAG procédure : couverture %s, sections %s", result.coverage, sections)
    return {"answer": answer, "coverage": result.coverage, "sections": sections}
