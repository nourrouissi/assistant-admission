"""
Outils de l'agent.

Chaque outil renvoie deux choses :
  - un résumé pour le LLM (il sait ce qui a été montré, pour la suite de la conversation) ;
  - les blocs affichés au candidat (texte et cartes), produits par le code et transmis
    tels quels par le nœud relay : le LLM n'écrit jamais lui-même un résultat.

Partie 1 : search_procedure.
Partie 2 : search_formations (recherche) et check_eligibility (vérification), deux
actions distinctes comme l'exige le sujet.
Partie 3 : start_registration (identification de la formation à laquelle s'inscrire).
"""

from __future__ import annotations

import functools
import threading
from typing import Annotated, Literal

from django.db import connections
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command

from catalog.eligibility import Profile
from config.i18n import DEFAULT_LANGUAGE, add_translations, current_language, join, tr
from catalog.serializers import MAX_EVALUATED, FormationSerializer
from catalog.services import eligibility_cards, formations_by_ids, search_catalog
from knowledge.rag import answer_procedure_question

from .registration_flow import new_registration

DiplomaCode = Literal["", "CAP", "BTP", "BTS", "LICENCE", "LICENCE_PRO", "BACHELOR", "INGENIEUR", "TITRE_RNCP", "SHORT_COURSE"]
LevelCode = Literal["", "9EME", "2EME_SEC", "3EME_SEC", "4EME_SEC", "CAP", "BTP", "BAC", "BAC_PLUS_2", "LICENCE", "LICENCE_PLUS_1", "MASTER"]
BacSectionCode = Literal["", "MATH", "SCIENCES_EXP", "TECHNIQUE", "INFORMATIQUE", "ECONOMIE_GESTION", "LETTRES", "SPORT"]

ELIGIBILITY_OFFER = "Si vous souhaitez vérifier votre éligibilité, indiquez-moi : {items}."
NO_FORMATION = "Je n'ai trouvé aucune formation correspondant à votre demande."
UNMATCHED_TEXT = "Aucune formation ne correspond à {words}."
UNMATCHED_GENERIC = "Une partie de votre demande ne correspond à aucune formation."  # anglais et arabe uniquement
FOUND_TEXT = "Voici {count} formation{plural} correspondant à votre demande."
NATIONALITY_NOT_UNDERSTOOD = "Je n'ai pas compris votre nationalité. Pouvez-vous l'indiquer en toutes lettres ?"
CHECKED_TEXT = (
    "Voici la vérification des critères d'après les informations que vous avez indiquées. "
    "La décision finale revient à l'équipe des admissions."
)
NEEDED_TEXT = "Pour compléter la vérification, j'ai besoin de : {items}."


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
    # En anglais ou en arabe, les mots-clés sont passés en français (langue du catalogue) :
    # ils ne sont pas cités au prospect, une phrase générale le prévient.
    if current_language() != DEFAULT_LANGUAGE:
        return tr(UNMATCHED_GENERIC)
    words = join(f"« {word} »" for word in unmatched)
    return tr(UNMATCHED_TEXT).format(words=words)


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
        sentences.append(tr(NO_FORMATION))
        text = " ".join(sentences)
        return text, [_text_block(text)]

    plural = "s" if len(cards) > 1 else ""
    sentences.append(tr(FOUND_TEXT).format(count=len(cards), plural=plural))
    # Seules les informations utiles pour ces formations sont demandées
    _, needed = eligibility_cards(formations, Profile())
    if needed:
        sentences.append(tr(ELIGIBILITY_OFFER).format(items=join(needed)))
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
        text = tr(NATIONALITY_NOT_UNDERSTOOD)
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
        sentences.append(tr(NO_FORMATION))
        text = " ".join(sentences)
        return text, [_text_block(text)]

    cards, needed = eligibility_cards(formations, profile)
    sentences.append(tr(CHECKED_TEXT))
    if needed:
        sentences.append(tr(NEEDED_TEXT).format(items=join(needed)))
    text = " ".join(sentences)
    return f"{text}\nFormations vérifiées :\n{_summary(cards)}", [_text_block(text), _cards_block(cards)]


# --- Partie 3 -----------------------------------------------------------------------------

ASK_FORMATION = (
    "À quelle formation souhaitez-vous vous inscrire ? Vous pouvez rechercher une formation, "
    "puis cliquer sur « S'inscrire » sur sa carte."
)
CHOOSE_FORMATION = (
    "Plusieurs formations correspondent à votre demande : cliquez sur « S'inscrire » "
    "sur celle qui vous intéresse."
)
NO_FORMATION_TO_REGISTER = (
    "Je n'ai trouvé aucune formation correspondant à votre demande : une demande d'inscription "
    "n'est possible que pour une formation proposée. Vous pouvez rechercher une formation."
)


@tool
@_closes_db_connection
def start_registration(
    tool_call_id: Annotated[str, InjectedToolCallId],
    keywords: str = "",
    diploma_type: DiplomaCode = "",
    school: str = "",
    formation_id: int | None = None,
):
    """Commence une demande d'inscription quand le candidat souhaite s'inscrire à une formation.
    `formation_id` : identifiant d'une formation déjà affichée, si le candidat la désigne ; sinon
    `keywords`, `diploma_type` et `school` comme pour search_formations.
    Les coordonnées du candidat ne sont jamais demandées ici : l'étape d'inscription les demande ensuite."""
    def answer(content: str, blocks: list[dict], update: dict | None = None) -> Command:
        message = ToolMessage(content, artifact=blocks, tool_call_id=tool_call_id)
        return Command(update={**(update or {}), "messages": [message]})

    if formation_id:
        formations, _unknown = formations_by_ids([formation_id])
    elif keywords or diploma_type or school:
        formations = list(search_catalog(query=keywords, school=school, diploma_type=diploma_type).formations[:MAX_EVALUATED])
    else:
        return answer(tr(ASK_FORMATION), [_text_block(tr(ASK_FORMATION))])

    if not formations:
        return answer(tr(NO_FORMATION_TO_REGISTER), [_text_block(tr(NO_FORMATION_TO_REGISTER))])
    if len(formations) > 1:
        # Choix ambigu : jamais de choix à la place du prospect
        cards = FormationSerializer(formations, many=True).data
        return answer(
            f"{CHOOSE_FORMATION}\nFormations affichées :\n{_summary(cards)}",
            [_text_block(tr(CHOOSE_FORMATION)), _cards_block(cards)],
        )
    formation = formations[0]
    return answer(
        f"Demande d'inscription commencée pour [id {formation.id}] : coordonnées demandées au candidat.",
        [],
        update={"registration": new_registration(formation.id)},
    )


# --- Traductions (le texte français ci-dessus reste la référence) -------------------------------

add_translations({
    ELIGIBILITY_OFFER: {
        "en": "If you would like to check your eligibility, please tell me: {items}.",
        "ar": "إذا كنت ترغب في التحقق من أهليتك، يُرجى إخباري بما يلي: {items}.",
    },
    NO_FORMATION: {
        "en": "I could not find any program matching your request.",
        "ar": "لم أجد أي برنامج يطابق طلبك.",
    },
    UNMATCHED_GENERIC: {
        "en": "Part of your request does not match any program.",
        "ar": "جزء من طلبك لا يطابق أي برنامج.",
    },
    UNMATCHED_TEXT: {
        "en": "No program matches {words}.",
        "ar": "لا يوجد أي برنامج يطابق {words}.",
    },
    FOUND_TEXT: {
        "en": "Here are the programs matching your request ({count}).",
        "ar": "إليك البرامج المطابقة لطلبك ({count}).",
    },
    NATIONALITY_NOT_UNDERSTOOD: {
        "en": "I did not understand your nationality. Could you write it out in full?",
        "ar": "لم أفهم جنسيتك. هل يمكنك كتابتها كاملة؟",
    },
    CHECKED_TEXT: {
        "en": "Here is the check of the criteria based on the information you provided. "
              "The final decision rests with the admissions team.",
        "ar": "إليك التحقق من الشروط بناءً على المعلومات التي قدمتها. القرار النهائي يعود إلى فريق القبول.",
    },
    NEEDED_TEXT: {
        "en": "To complete the check, I need: {items}.",
        "ar": "لإكمال التحقق، أحتاج إلى: {items}.",
    },
    ASK_FORMATION: {
        "en": "Which program would you like to apply for? You can search for a program, "
              "then click “Apply” on its card.",
        "ar": "في أي برنامج ترغب في التسجيل؟ يمكنك البحث عن برنامج ثم النقر على «سجّل» في بطاقته.",
    },
    CHOOSE_FORMATION: {
        "en": "Several programs match your request: click “Apply” on the one you are interested in.",
        "ar": "هناك عدة برامج تطابق طلبك: انقر على «سجّل» في البرنامج الذي يهمك.",
    },
    NO_FORMATION_TO_REGISTER: {
        "en": "I could not find any program matching your request: an application is only possible "
              "for a program we offer. You can search for a program.",
        "ar": "لم أجد أي برنامج يطابق طلبك: لا يمكن تقديم طلب تسجيل إلا لبرنامج نقدمه. يمكنك البحث عن برنامج.",
    },
})


TOOLS = [search_procedure, search_formations, check_eligibility, start_registration]
