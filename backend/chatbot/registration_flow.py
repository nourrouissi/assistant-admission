"""
Inscription conversationnelle (Partie 3) : collecte, récapitulatif, confirmation.

Répartition des rôles :
  - le LLM comprend les messages du prospect : il extrait le nom, le prénom, l'e-mail
    et le téléphone (« je suis Amira Ben Salah, mon mail c'est … »), et reconnaît une
    demande d'annulation ou une question sans rapport ;
  - le code garantit les règles du sujet :
      * chaque valeur extraite doit figurer dans le message du prospect (le LLM ne peut
        rien inventer) ;
      * validation par un formulaire Django (ApplicantForm), jamais par le LLM ;
      * récapitulatif, puis confirmation explicite par bouton (pause LangGraph `interrupt`) ;
      * enregistrement après confirmation uniquement, statut « Nouvelle », sans doublon
        (vérifié au clic sur « Confirmer » : la collecte ne révèle pas les coordonnées connues) ;
      * jamais de garantie d'admission.

Les coordonnées restent dans l'état `registration` du graphe. Les messages qui les
contiennent sont retirés de l'historique : l'agent ne les voit jamais.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.graph import END
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from catalog.models import Formation
from catalog.normalization import fold
from catalog.serializers import FormationSerializer
from registrations.forms import ApplicantForm
from registrations.services import DuplicateApplication, FormationUnavailable, submit_application

from .llm import chat_models, with_fallbacks

logger = logging.getLogger(__name__)

FIELDS = ["last_name", "first_name", "email", "phone"]
FIELD_NAMES = {
    "last_name": "votre nom",
    "first_name": "votre prénom",
    "email": "votre adresse e-mail",
    "phone": "votre numéro de téléphone",
}

# Boutons du récapitulatif
SUMMARY_ACTIONS = ["confirm", "modify", "cancel"]

START_TEXT = "Pour votre demande d'inscription à « {specialty} » ({diploma}, {school}), merci de m'indiquer {fields}."
MISSING_TEXT = "Merci de m'indiquer {fields}."
ERROR_TEXT = "{field} n'est pas valide : {message}"
MODIFY_TEXT = "Quelle information souhaitez-vous modifier ? Écrivez simplement la nouvelle valeur."
SUMMARY_TEXT = (
    "Voici le récapitulatif de votre demande d'inscription. "
    "Vérifiez vos informations, puis confirmez, modifiez ou annulez votre demande avec les boutons."
)
CONFIRMED_TEXT = (
    "Votre demande d'inscription à « {specialty} » ({school}) a bien été prise en compte, "
    "avec le statut « Nouvelle ». L'équipe des admissions va l'étudier : la décision finale lui appartient."
)
CANCELLED_TEXT = "Votre demande d'inscription a été annulée : aucune information n'a été enregistrée."
DUPLICATE_TEXT = (
    "Une demande existe déjà avec cet e-mail ou ce numéro de téléphone : aucune "
    "nouvelle demande n'a été enregistrée. Pour toute question, vous pouvez contacter le service des "
    "admissions : {contact}."
)
UNAVAILABLE_TEXT = (
    "Cette formation n'est plus proposée : aucune demande n'a été enregistrée. "
    "Vous pouvez rechercher une autre formation."
)
EXTRACTION_FAILED_TEXT = (
    "Je n'ai pas pu traiter votre message pour le moment. Vous pouvez réessayer, "
    "ou contacter le service des admissions : {contact}."
)


# --- Extraction par le LLM -------------------------------------------------------------------

class RegistrationMessage(BaseModel):
    """Ce que le LLM comprend du dernier message du prospect."""

    intent: Literal["details", "cancel", "other"] = Field(description=(
        "details : le candidat donne ou corrige une ou plusieurs coordonnées ; "
        "cancel : il veut annuler ou abandonner sa demande d'inscription ; "
        "other : autre chose (question, autre sujet)."
    ))
    last_name: str = Field("", description="Nom de famille, recopié tel qu'écrit. Vide s'il n'est pas donné.")
    first_name: str = Field("", description="Prénom, recopié tel qu'écrit. Vide s'il n'est pas donné.")
    email: str = Field("", description="Adresse e-mail, recopiée telle qu'écrite. Vide si elle n'est pas donnée.")
    phone: str = Field("", description="Numéro de téléphone, recopié tel qu'écrit. Vide s'il n'est pas donné.")


EXTRACTION_PROMPT = """Tu aides à collecter les coordonnées d'un candidat pour sa demande d'inscription.
Analyse uniquement le dernier message du candidat.

Règles :
1. Recopie chaque valeur exactement comme elle est écrite dans le message. N'invente, ne complète et ne corrige rien.
2. Laisse vide toute information qui n'est pas dans le message.
3. Si le candidat donne son nom complet sans préciser, le premier mot est le prénom et le reste est le nom.
4. Une réponse courte à la question de l'assistant (ex. « Ben Salah » quand l'assistant demande le nom) est une coordonnée.
5. Une question ou une demande sans rapport avec ses coordonnées est « other »."""


def _extractor() -> Runnable:
    return with_fallbacks([
        model.with_structured_output(RegistrationMessage, method="function_calling") for model in chat_models()
    ])


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _written_in(field: str, value: str, message: str) -> bool:
    """
    Vrai si la valeur extraite figure dans le message du prospect.
    Garde-fou contre une valeur inventée par le LLM : elle est ignorée.
    """
    if field == "phone":
        digits = _digits(value)
        # Le LLM peut ajouter l'indicatif (+216) : les 8 derniers chiffres doivent avoir été écrits
        return len(digits) >= 3 and (digits in _digits(message) or digits[-8:] in _digits(message))
    if field == "email":
        return value.lower() in message.lower()
    return " ".join(fold(value).split()) in " ".join(fold(message).split())


def extract_details(message: str, question: str) -> RegistrationMessage:
    """Le LLM lit le message ; seules les valeurs réellement écrites par le prospect sont gardées."""
    result: RegistrationMessage = _extractor().invoke([
        SystemMessage(EXTRACTION_PROMPT),
        HumanMessage(f"Dernière question de l'assistant : {question}\n\nMessage du candidat : {message}"),
    ])
    for field in FIELDS:
        value = getattr(result, field).strip()
        if value and not _written_in(field, value, message):
            logger.warning("Inscription : valeur extraite absente du message, ignorée (%s)", field)
            value = ""
        setattr(result, field, value)
    return result


# --- Validation par le code ---------------------------------------------------------------------

def validate(values: dict) -> tuple[dict | None, dict]:
    """
    Valide les coordonnées connues avec le formulaire Django.

    Retour : (coordonnées nettoyées si tout est valide, erreurs des champs renseignés).
    Les doublons sont vérifiés seulement à la confirmation (submit_application).
    """
    form = ApplicantForm({field: values.get(field, "") for field in FIELDS})
    valid = form.is_valid()
    errors = {field: list(messages) for field, messages in form.errors.items() if values.get(field)}
    return (form.cleaned_data if valid else None), errors


# --- Blocs affichés -------------------------------------------------------------------------------

def new_registration(formation_id: int) -> dict:
    """Inscription qui commence : formation choisie, aucune coordonnée."""
    return {"formation_id": formation_id, "stage": "collect", "values": {}, "errors": {}}


def _card(formation_id: int) -> dict | None:
    formation = Formation.objects.filter(id=formation_id, is_active=True).first()
    return FormationSerializer(formation).data if formation else None


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _say(text: str) -> AIMessage:
    return AIMessage(text, response_metadata={"blocks": [_text_block(text)]})


# Issue d'une inscription, transmise à l'interface dans un bloc « registration_result »
CREATED, DUPLICATE, UNAVAILABLE, CANCELLED = "created", "duplicate", "unavailable", "cancelled"


def _end(text: str, outcome: str, **details) -> Command:
    """
    Fin de l'inscription : message au prospect, données de l'inscription effacées de l'état.
    Le bloc « registration_result » donne l'issue à l'interface, sans qu'elle ait à lire le texte.
    """
    message = AIMessage(text, response_metadata={"blocks": [
        _text_block(text), {"type": "registration_result", "outcome": outcome, **details},
    ]})
    return Command(update={"registration": None, "messages": [message]}, goto=END)


def _enumerate(fields: list[str]) -> str:
    names = [FIELD_NAMES[field] for field in fields]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} et {names[-1]}"


def _question(registration: dict, card: dict) -> str:
    """Question posée au prospect, selon ce qui manque ou est à corriger."""
    values, errors = registration["values"], registration["errors"]
    missing = [field for field in FIELDS if not values.get(field)]
    if not values:
        return START_TEXT.format(
            specialty=card["specialty"], diploma=card["diploma"], school=card["school"], fields=_enumerate(FIELDS),
        )
    sentences = [
        ERROR_TEXT.format(field=FIELD_NAMES[field].capitalize(), message=" ".join(messages))
        for field, messages in errors.items()
    ]
    to_ask = missing + [field for field in errors if field not in missing]
    if to_ask:
        sentences.append(MISSING_TEXT.format(fields=_enumerate([f for f in FIELDS if f in to_ask])))
    else:
        sentences.append(MODIFY_TEXT)       # tout est valide : le prospect a demandé une modification
    return " ".join(sentences)


def _summary_blocks(registration: dict, card: dict) -> list[dict]:
    return [
        _text_block(SUMMARY_TEXT),
        {
            "type": "registration_summary",
            "formation": card,
            "applicant": {field: registration["values"][field] for field in FIELDS},
            "actions": SUMMARY_ACTIONS,
        },
    ]


# --- Nœuds du graphe --------------------------------------------------------------------------------

def registration_ask(state: dict) -> Command:
    """Demande au prospect les coordonnées manquantes ou à corriger."""
    registration = state["registration"]
    card = _card(registration["formation_id"])
    if card is None:
        return _end(UNAVAILABLE_TEXT, UNAVAILABLE)
    return Command(update={"messages": [_say(_question(registration, card))]}, goto=END)


def registration_collect(state: dict) -> Command:
    """
    Message écrit pendant la collecte : le LLM l'analyse, le code valide.
    Une question sans rapport est confiée à l'agent ; la collecte reprend après sa réponse.
    """
    registration = state["registration"]
    formation_id = registration["formation_id"]
    if _card(formation_id) is None:
        return _end(UNAVAILABLE_TEXT, UNAVAILABLE)

    message = state["messages"][-1]
    question = next(
        (m.content for m in reversed(state["messages"][:-1]) if isinstance(m, AIMessage) and m.content), "",
    )
    try:
        extracted = extract_details(str(message.content), str(question))
    except Exception:
        logger.exception("Inscription : aucun modèle n'a pu analyser le message")
        return Command(
            update={"messages": [_say(EXTRACTION_FAILED_TEXT.format(contact=settings.ADMISSIONS_CONTACT))]},
            goto=END,
        )

    if extracted.intent == "cancel":
        return _end(CANCELLED_TEXT, CANCELLED)
    given = {field: getattr(extracted, field) for field in FIELDS if getattr(extracted, field)}
    if extracted.intent == "other" and not given:
        return Command(goto="agent")

    # Le message contient des coordonnées : il est retiré de l'historique lu par l'agent
    forget = [RemoveMessage(id=message.id)] if message.id else []
    values = {**registration["values"], **given}
    cleaned, errors = validate(values)
    if cleaned is not None and given:
        return Command(
            update={
                "registration": {**registration, "stage": "summary", "values": cleaned, "errors": {}},
                "messages": forget,
            },
            goto="registration_summary",
        )
    return Command(
        update={"registration": {**registration, "values": values, "errors": errors}, "messages": forget},
        goto="registration_ask",
    )


def registration_summary(state: dict) -> Command:
    """Affiche le récapitulatif et attend Confirmer / Modifier / Annuler (pause)."""
    registration = state["registration"]
    card = _card(registration["formation_id"])
    if card is None:
        return _end(UNAVAILABLE_TEXT, UNAVAILABLE)

    answer = interrupt({"stage": "summary", "blocks": _summary_blocks(registration, card)})
    action = answer.get("action")
    if action == "modify":
        return Command(update={"registration": {**registration, "stage": "collect"}}, goto="registration_ask")
    if action != "confirm":
        return _end(CANCELLED_TEXT, CANCELLED)

    # Confirmation explicite par le bouton : seul chemin qui enregistre une demande.
    # Les doublons sont vérifiés ici seulement, jamais pendant la collecte.
    try:
        application = submit_application(registration["values"], registration["formation_id"])
    except DuplicateApplication:
        return _end(DUPLICATE_TEXT.format(contact=settings.ADMISSIONS_CONTACT), DUPLICATE)
    except FormationUnavailable:
        return _end(UNAVAILABLE_TEXT, UNAVAILABLE)
    return _end(
        CONFIRMED_TEXT.format(specialty=card["specialty"], school=card["school"]),
        CREATED, status=application.get_status_display(), formation=card,
    )


def registration_cancel(state: dict) -> Command:
    """Bouton « Annuler » pendant la collecte."""
    return _end(CANCELLED_TEXT, CANCELLED)
