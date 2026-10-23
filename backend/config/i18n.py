"""
Langue de l'assistant : français (par défaut), anglais, arabe.

Principe : le texte français reste la référence, inchangé, dans chaque module.
Les traductions anglaises et arabes sont déclarées à côté, avec le texte français
comme clé (add_translations). tr(texte) renvoie :
  - le texte français tel quel si la langue est le français (comportement d'origine) ;
  - sa traduction sinon (ou le français si une traduction manque).

La langue de la requête en cours est une variable de contexte : les fonctions
existantes gardent leurs paramètres, et tout ce qui est appelé pendant la requête
(agent, outils, inscription) la connaît. LangGraph transmet le contexte aux threads
des outils.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

LANGUAGES = ("fr", "en", "ar")
DEFAULT_LANGUAGE = "fr"

_language: ContextVar[str] = ContextVar("language", default=DEFAULT_LANGUAGE)
_catalog: dict[str, dict[str, str]] = {}

# Consigne de langue ajoutée aux instructions des modèles (jamais pour le français :
# les instructions françaises restent exactement celles d'origine)
LANGUAGE_NAMES = {"en": "anglais", "ar": "arabe"}
LANGUAGE_RULE = (
    "\n\nLangue : le candidat a choisi l'{name}. Rédige toutes tes réponses en {name}, "
    "même si les informations fournies sont en français. Pour les formations et les diplômes, "
    "reprends les noms tels qu'ils figurent dans les résultats des outils ; garde tels quels "
    "les noms des écoles (ex. IMSET SOUSSE) et les adresses e-mail. Ne mélange jamais les langues : "
    "traduis aussi les termes repris des informations fournies (diplôme, spécialité, établissement…)."
)


def normalize_language(value: str | None) -> str:
    """Code de langue accepté, sinon le français."""
    return value if value in LANGUAGES else DEFAULT_LANGUAGE


# --- Langue du message écrit par le prospect -------------------------------------------------------
# Le prospect est servi dans la langue de son message. Un message trop court ou neutre (un nom,
# un e-mail, un numéro, « ok ») ne permet pas de trancher : la langue de l'interface est alors gardée.

_ARABIC = re.compile(r"[ء-ي]")
_LATIN = re.compile(r"[a-zà-ÿ]")
_FRENCH_ACCENTS = re.compile(r"[éèêëàâçùûôîï]")
_FRENCH_WORDS = {
    "le", "la", "les", "des", "un", "une", "est", "je", "suis", "vous", "votre", "vos", "pour", "dans",
    "quel", "quelle", "quels", "quelles", "et", "ou", "mon", "ma", "mes", "au", "aux", "du", "de", "qui",
    "que", "avec", "sur", "sont", "c'est", "j'ai", "proposez", "combien", "comment", "pourquoi", "oui",
    "non", "bonjour", "merci", "m'inscrire", "inscrire", "frais", "formation", "formations", "dois", "veux",
    "m'appelle", "appelle", "nom", "prénom", "numéro", "proposez-vous", "sûre", "sûr",
}
_ENGLISH_WORDS = {
    "the", "is", "are", "i", "am", "i'm", "you", "your", "for", "in", "which", "what", "and", "or", "my",
    "to", "of", "do", "does", "have", "can", "with", "about", "how", "much", "many", "where", "when", "yes",
    "hello", "hi", "thanks", "thank", "apply", "fees", "program", "programs", "would", "like", "want", "need",
}


def detect_language(text: str, default: str) -> str:
    """
    Langue d'un message : « ar » s'il est écrit surtout en lettres arabes ; « fr » ou « en » selon
    les mots courants de chaque langue (accents français compris) ; sinon `default` (langue de l'interface).
    """
    # Les adresses e-mail sont retirées ; « dois-je » donne « dois » et « je »
    text = re.sub(r"\S+@\S+", " ", text.lower())
    words = re.findall(r"[\w'’.+]+", text)
    letters = "".join(words)
    arabic, latin = len(_ARABIC.findall(letters)), len(_LATIN.findall(letters))
    if arabic and arabic >= latin:
        return "ar"
    tokens = [word.replace("’", "'").strip(".") for word in words]
    french = sum(token in _FRENCH_WORDS for token in tokens) + len(_FRENCH_ACCENTS.findall(letters))
    english = sum(token in _ENGLISH_WORDS for token in tokens)
    if french >= 2 and french > english:
        return "fr"
    if english >= 2 and english > french:
        return "en"
    return normalize_language(default)


def current_language() -> str:
    return _language.get()


@contextmanager
def use_language(language: str | None) -> Iterator[None]:
    """Fixe la langue pendant le traitement d'une requête."""
    token = _language.set(normalize_language(language))
    try:
        yield
    finally:
        _language.reset(token)


def add_translations(entries: dict[str, dict[str, str]]) -> None:
    """Déclare des traductions : {texte français: {"en": ..., "ar": ...}}."""
    _catalog.update(entries)


def translation(text: str, language: str) -> str:
    """Traduction de `text` dans une langue donnée (le texte lui-même si elle manque)."""
    return _catalog.get(text, {}).get(language, text)


def tr(text: str) -> str:
    """Texte dans la langue en cours (le français est renvoyé tel quel)."""
    language = current_language()
    if language == DEFAULT_LANGUAGE:
        return text
    return _catalog.get(text, {}).get(language, text)


COMMA = ", "
SEMICOLON = " ; "
_catalog.update({COMMA: {"en": ", ", "ar": "، "}, SEMICOLON: {"en": "; ", "ar": "؛ "}})


def join(items, separator: str = COMMA) -> str:
    """Énumération avec la ponctuation de la langue (virgule arabe en arabe ; en français : inchangée)."""
    return tr(separator).join(items)


def language_rule() -> str:
    """Consigne de langue pour les instructions d'un modèle ; vide en français."""
    name = LANGUAGE_NAMES.get(current_language())
    return LANGUAGE_RULE.format(name=name) if name else ""
