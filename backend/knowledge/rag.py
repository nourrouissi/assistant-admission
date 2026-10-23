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
import re
from typing import Literal

from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from chatbot.llm import chat_models, with_fallbacks
from config.i18n import add_translations, current_language, language_rule, tr

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


class TranslatedProcedureAnswer(ProcedureAnswer):
    """Même réponse structurée, rédigée dans la langue choisie par le candidat (anglais ou arabe)."""

    answer: str = Field(description="Réponse au candidat, rédigée entièrement dans la langue demandée.")


# Les règles de la section 6 du document (« Questions sans réponse ») sont reprises ici.
SYSTEM_PROMPT = """Tu es conseiller d'admission des écoles IMSET. Tu réponds aux questions des candidats sur la procédure d'admission.

Règles :
1. Réponds uniquement à partir des informations fournies dans le message. N'utilise aucune autre connaissance.
2. N'invente jamais de date, de tarif, de montant ou de condition d'admission. Si le candidat cite une date ou un montant qui ne figure pas dans les informations, ne le confirme pas.
3. Si l'information est absente, dis clairement que tu ne l'as pas. Si elle est incomplète, donne ce qui est connu et dis ce qui manque.
4. Ne mentionne jamais le service des admissions ni aucune adresse de contact : l'orientation vers ce service est ajoutée automatiquement après ta réponse quand l'information manque.
5. Ne confirme jamais qu'un candidat est éligible ou admis. S'il demande s'il sera admis, réponds clairement que l'admission n'est jamais garantie et que la décision finale appartient à l'équipe des admissions. S'il demande s'il est éligible, donne les critères généraux et propose de rechercher les formations qui correspondent à son profil.
6. Réponds seulement à la question posée : n'ajoute pas d'informations qui n'ont pas été demandées (par exemple, ne liste pas toutes les étapes de la procédure si la question porte sur un autre point).
7. Réponds en français, naturellement et simplement, à la première personne, comme un conseiller d'admission. Vouvoie toujours le candidat.
8. N'emploie jamais les mots « document », « extrait », « source » ou « contexte »."""

# Phrase ajoutée par le code quand la réponse est partielle ou absente
CONTACT_SENTENCE = "Pour plus de précisions, vous pouvez contacter le service des admissions : {contact}."

# Message fixe quand aucun modèle ne répond (quota, réseau) : jamais de réponse inventée
UNAVAILABLE_MESSAGE = (
    "Je ne peux pas répondre pour le moment. Vous pouvez contacter le service des admissions : {contact}."
)


FRENCH_RULE = "7. Réponds en français, naturellement"


def _system_prompt() -> str:
    """Instructions du modèle ; en français, exactement celles d'origine."""
    if current_language() == "fr":
        return SYSTEM_PROMPT
    return SYSTEM_PROMPT.replace(FRENCH_RULE, "7. Réponds naturellement") + language_rule()


def _answer_chain() -> Runnable:
    """Chaque modèle produit la sortie structurée, puis la chaîne de secours les enchaîne."""
    schema = ProcedureAnswer if current_language() == "fr" else TranslatedProcedureAnswer
    return with_fallbacks([
        model.with_structured_output(schema, method="function_calling") for model in chat_models()
    ])


# Autre langue que le français : la consigne est rappelée juste après la question (les informations
# fournies sont en français, et un modèle de secours pourrait sinon répondre en français)
ANSWER_LANGUAGE = {"en": "Réponds entièrement en anglais.", "ar": "Réponds entièrement en arabe."}
COVERAGE_REMINDER = (
    " La couverture s'évalue sur le fond, quelle que soit la langue : si la question porte sur une date, "
    "un montant ou un tarif précis qui ne figure pas dans les informations, la couverture est « partial » ou « none »."
)

_ARABIC_LETTER = re.compile(r"[ء-ي]")
_LATIN_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")
_FRENCH_WORDS = re.compile(r"\b(?:les|des|vous|votre|une|est|pour|dans|selon|avec)\b", re.IGNORECASE)


def _user_message(question: str, chunks) -> str:
    information = "\n\n".join(chunk.content for chunk in chunks) or "(aucune information)"
    message = f"Informations :\n{information}\n\nQuestion du candidat : {question}"
    # Rappel de la couverture dans toutes les langues : sans lui, un montant cité par le candidat
    # (« 50 dinars ») était parfois jugé « complete », et l'orientation vers les admissions manquait
    language = ANSWER_LANGUAGE.get(current_language(), "")
    return f"{message}\n\n{(language + COVERAGE_REMINDER).strip()}"


def written_in_language(answer: str) -> bool:
    """
    Vrai si la réponse est bien dans la langue du candidat (toujours vrai en français).
    Arabe : au moins 70 % de lettres arabes (sigles, noms d'écoles et e-mails restent en lettres latines).
    Anglais : aucune phrase française (mots français courants).
    """
    language = current_language()
    if language == "ar":
        arabic = len(_ARABIC_LETTER.findall(answer))
        # Mots latins écrits en minuscules seulement : sigles et noms d'écoles (BTS, IMSET SOUSSE) exclus
        words = re.sub(r"\S+@\S+", "", answer).split()
        latin = sum(len(_LATIN_LETTER.findall(word)) for word in words if any(ch.islower() for ch in word))
        return arabic >= 0.7 * (arabic + latin)
    if language == "en":
        return len(_FRENCH_WORDS.findall(answer)) < 3
    return True


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
        messages = [SystemMessage(_system_prompt()), HumanMessage(_user_message(question, chunks))]
        result: ProcedureAnswer = _answer_chain().invoke(messages)
        if not written_in_language(result.answer):
            # Réponse dans une autre langue que celle du candidat : une seconde tentative
            logger.warning("RAG procédure : réponse hors langue (%s), nouvelle tentative", current_language())
            result = _answer_chain().invoke(messages)
    except Exception:
        logger.exception("RAG procédure : aucun modèle n'a pu répondre (sections %s)", sections)
        return {"answer": tr(UNAVAILABLE_MESSAGE).format(contact=contact), "coverage": "none", "sections": sections}

    answer = result.answer.strip()
    if result.coverage != "complete" and contact not in answer:
        answer = f"{answer} {tr(CONTACT_SENTENCE).format(contact=contact)}"
    logger.info("RAG procédure : couverture %s, sections %s", result.coverage, sections)
    return {"answer": answer, "coverage": result.coverage, "sections": sections}


# --- Traductions (le texte français ci-dessus reste la référence) -------------------------------

add_translations({
    CONTACT_SENTENCE: {
        "en": "For more details, you can contact the admissions office: {contact}.",
        "ar": "لمزيد من التفاصيل، يمكنك التواصل مع مصلحة القبول: {contact}.",
    },
    UNAVAILABLE_MESSAGE: {
        "en": "I cannot answer at the moment. You can contact the admissions office: {contact}.",
        "ar": "لا يمكنني الرد في الوقت الحالي. يمكنك التواصل مع مصلحة القبول: {contact}.",
    },
})
