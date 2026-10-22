"""
Normalisation des données brutes du fichier Excel « diplôme spécialité ».

Le fichier est saisi à la main : libellés hétérogènes, faute de frappe
(« san bac »), espaces parasites, niveaux en texte libre.
Ce module transforme chaque valeur brute en une valeur *structurée* et
*comparable* par du code, ce qui permet :
  - une recherche fiable (diplôme normalisé, texte sans accents) ;
  - un calcul d'éligibilité déterministe (niveaux ordonnés).

Toutes les fonctions sont pures (aucun accès à la base) : elles sont donc
faciles à tester unitairement.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Outils texte
# ---------------------------------------------------------------------------

def clean_spaces(value: str | None) -> str:
    """Supprime les espaces en début/fin et réduit les espaces multiples à un seul."""
    return re.sub(r"\s+", " ", (value or "")).strip()


def fold(value: str | None) -> str:
    """
    Met un texte sous une forme « comparable » : minuscules, sans accents,
    espaces normalisés. Exemple : "Mathèmatique " -> "mathematique".
    Sert à la recherche insensible aux accents et à l'analyse des règles.
    """
    text = unicodedata.normalize("NFKD", clean_spaces(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


# ---------------------------------------------------------------------------
# Types de diplômes : 11 libellés bruts -> 9 types normalisés
# ---------------------------------------------------------------------------

class DiplomaType:
    CAP = "CAP"
    BTP = "BTP"
    BTS = "BTS"
    LICENCE = "LICENCE"
    LICENCE_PRO = "LICENCE_PRO"
    BACHELOR = "BACHELOR"
    INGENIEUR = "INGENIEUR"
    TITRE_RNCP = "TITRE_RNCP"
    SHORT_COURSE = "SHORT_COURSE"

    LABELS = {
        CAP: "Certificat d'Aptitude Professionnelle (CAP)",
        BTP: "Brevet de Technicien Professionnel (BTP)",
        BTS: "Brevet de Technicien Supérieur (BTS)",
        LICENCE: "Licence",
        LICENCE_PRO: "Licence professionnelle",
        BACHELOR: "Bachelor",
        INGENIEUR: "Diplôme d'ingénieur",
        TITRE_RNCP: "Titre RNCP – Concepteur en architecture informatique",
        SHORT_COURSE: "Formation courte",
    }
    CHOICES = list(LABELS.items())


# L'ordre compte : les motifs les plus spécifiques d'abord
# (« licence professionnelle » doit être testé avant « licence »).
_DIPLOMA_PATTERNS: list[tuple[str, str]] = [
    ("brevet de technicien professionnel", DiplomaType.BTP),
    ("brevet de technicien superieur", DiplomaType.BTS),
    ("certificat d'aptitude professionnelle", DiplomaType.CAP),
    ("licence professionnelle", DiplomaType.LICENCE_PRO),
    ("licence", DiplomaType.LICENCE),
    ("ingenieur", DiplomaType.INGENIEUR),
    ("bachelor", DiplomaType.BACHELOR),
    ("concepteur en architecture informatique", DiplomaType.TITRE_RNCP),
    ("short course", DiplomaType.SHORT_COURSE),
]


def normalize_diploma_type(label: str) -> str | None:
    """« Diplome de LICENCE » -> "LICENCE" ; None si le libellé est inconnu."""
    folded = fold(label)
    for pattern, code in _DIPLOMA_PATTERNS:
        if pattern in folded:
            return code
    return None


# ---------------------------------------------------------------------------
# Spécialités et écoles
# ---------------------------------------------------------------------------

_SPECIALTY_PREFIX = re.compile(r"^(bts|btp)\s*[-_]\s*", re.IGNORECASE)


def clean_specialty(raw: str) -> str:
    """Nettoie une spécialité pour l'affichage : « BTS-Comptabilité » -> « Comptabilité »."""
    text = _SPECIALTY_PREFIX.sub("", clean_spaces(raw))
    text = re.sub(r"(\S)\(", r"\1 (", text)  # « Informatiques(cours du soir) » -> espace avant « ( »
    return text[:1].upper() + text[1:] if text else text


def school_city(school: str) -> str:
    """« IMSET SOUSSE » -> « Sousse »."""
    parts = clean_spaces(school).split(" ", 1)
    return parts[1].title() if len(parts) == 2 else ""


# ---------------------------------------------------------------------------
# Niveaux d'études : ordonnés par un rang pour pouvoir les comparer
# ---------------------------------------------------------------------------

class Level:
    """
    Niveaux d'études du système tunisien. Le *rang* permet la comparaison :
    un prospect atteint le niveau requis si son rang est >= au rang demandé.
    """

    NEUVIEME = "9EME"            # 9ème année de base accomplie
    DEUXIEME_SEC = "2EME_SEC"    # 2ème année secondaire réussie
    TROISIEME_SEC = "3EME_SEC"
    QUATRIEME_SEC = "4EME_SEC"   # année du bac, sans le bac
    CAP = "CAP"
    BTP = "BTP"
    BAC = "BAC"
    BAC_PLUS_2 = "BAC_PLUS_2"    # BTS, 2 années réussies
    LICENCE = "LICENCE"          # Bac+3
    LICENCE_PLUS_1 = "LICENCE_PLUS_1"  # Bac+4
    MASTER = "MASTER"

    RANK = {
        NEUVIEME: 1, CAP: 1, DEUXIEME_SEC: 2, BTP: 3, TROISIEME_SEC: 3,
        QUATRIEME_SEC: 4, BAC: 5, BAC_PLUS_2: 6, LICENCE: 7,
        LICENCE_PLUS_1: 8, MASTER: 9,
    }

    LABELS = {
        NEUVIEME: "9ème année de base accomplie",
        DEUXIEME_SEC: "2ème année secondaire réussie",
        TROISIEME_SEC: "3ème année secondaire",
        QUATRIEME_SEC: "4ème année secondaire (sans bac)",
        CAP: "CAP",
        BTP: "BTP",
        BAC: "Baccalauréat",
        BAC_PLUS_2: "Bac+2 / BTS",
        LICENCE: "Licence (Bac+3)",
        LICENCE_PLUS_1: "Licence + 1 année (Bac+4)",
        MASTER: "Master (Bac+5)",
    }
    CHOICES = list(LABELS.items())


@dataclass
class LevelRequirement:
    """
    Condition de niveau d'une formation, sous forme structurée.
    Ex. « 2ème avec succès ou CAP dans le même secteur » ->
        min_level="2EME_SEC", alternatives=["CAP"], alternatives_same_sector=True
    """

    min_level: str | None = None           # None = aucune exigence (« All »)
    alternatives: list[str] = field(default_factory=list)
    alternatives_same_sector: bool = False
    parsed: bool = True                    # False si le texte n'a pas été compris


def parse_level_requirement(raw: str) -> LevelRequirement:
    """
    Convertit le texte libre de la colonne « Niveau éligible » en LevelRequirement.

    On travaille sur le texte « plié » et sans espaces pour absorber les variantes :
    « Bac+2 / BTS » et « Bac+ 2/ BTS » donnent le même résultat.
    L'ordre des tests est important : on cherche les niveaux les plus hauts
    d'abord, car « bac+2 » contient aussi le mot « bac ».
    """
    text = fold(raw)
    compact = text.replace(" ", "")

    if text in {"", "all", "tous", "toutes"}:
        return LevelRequirement(min_level=None)

    req = LevelRequirement()
    if "licence+1" in compact:
        req.min_level = Level.LICENCE_PLUS_1
    elif "licence" in text:
        req.min_level = Level.LICENCE
    elif "bac+2" in compact:
        req.min_level = Level.BAC_PLUS_2
    elif re.search(r"\bbac\b", text):
        req.min_level = Level.BAC
    elif "4eme" in text:
        req.min_level = Level.QUATRIEME_SEC
    elif "2eme" in text:
        req.min_level = Level.DEUXIEME_SEC
    elif "9eme" in text:
        req.min_level = Level.NEUVIEME
    else:
        req.parsed = False  # on signale au lieu de deviner

    # Alternatives professionnelles : « … ou CAP », « … ou BTP »
    if re.search(r"\bou cap\b", text):
        req.alternatives.append(Level.CAP)
    if re.search(r"\bou btp\b", text):
        req.alternatives.append(Level.BTP)
    req.alternatives_same_sector = bool(req.alternatives) and "meme secteur" in text
    return req


# ---------------------------------------------------------------------------
# Nature du bac
# ---------------------------------------------------------------------------

class BacRule:
    ANY = "ANY"                    # « All » : pas de restriction
    NOT_REQUIRED = "NOT_REQUIRED"  # « san bac » : accessible sans bac
    SECTIONS = "SECTIONS"          # sections précises exigées

    CHOICES = [
        (ANY, "Toutes sections"),
        (NOT_REQUIRED, "Bac non requis"),
        (SECTIONS, "Sections précises"),
    ]


class BacSection:
    MATH = "MATH"
    SCIENCES_EXP = "SCIENCES_EXP"
    TECHNIQUE = "TECHNIQUE"
    INFORMATIQUE = "INFORMATIQUE"
    ECONOMIE_GESTION = "ECONOMIE_GESTION"
    LETTRES = "LETTRES"
    SPORT = "SPORT"

    LABELS = {
        MATH: "Mathématiques",
        SCIENCES_EXP: "Sciences expérimentales",
        TECHNIQUE: "Sciences techniques",
        INFORMATIQUE: "Sciences de l'informatique",
        ECONOMIE_GESTION: "Économie et gestion",
        LETTRES: "Lettres",
        SPORT: "Sport",
    }

    # Mots-clés (texte plié) -> section. Servira aussi à comprendre le prospect :
    # « j'ai un bac info » -> INFORMATIQUE.
    KEYWORDS = {
        "math": MATH, "experimental": SCIENCES_EXP, "technique": TECHNIQUE,
        "informatique": INFORMATIQUE, "info": INFORMATIQUE,
        "economie": ECONOMIE_GESTION, "gestion": ECONOMIE_GESTION,
        "lettre": LETTRES, "sport": SPORT,
    }


def detect_bac_sections(text: str) -> list[str]:
    """Retourne les sections du bac citées dans un texte, sans doublon, dans l'ordre."""
    folded = fold(text)
    found: list[str] = []
    for keyword, section in BacSection.KEYWORDS.items():
        if re.search(rf"\b{keyword}", folded) and section not in found:
            found.append(section)
    return found


def parse_bac_rule(raw: str) -> tuple[str, list[str]]:
    """
    « All » -> (ANY, []) ; « san bac » (faute de frappe) -> (NOT_REQUIRED, []) ;
    « Sciences expérimentales ou Mathèmatique » -> (SECTIONS, [MATH, SCIENCES_EXP]).
    """
    text = fold(raw)
    if text in {"", "all", "tous", "toutes"}:
        return BacRule.ANY, []
    if re.fullmatch(r"sans? bac", text):
        return BacRule.NOT_REQUIRED, []
    sections = detect_bac_sections(text)
    if sections:
        return BacRule.SECTIONS, sections
    return BacRule.ANY, []


# ---------------------------------------------------------------------------
# Nationalité
# ---------------------------------------------------------------------------

def parse_nationality(raw: str) -> str | None:
    """« All » -> None (toutes nationalités) ; « Tunisienne » -> "TN"."""
    text = fold(raw)
    if text in {"", "all", "toutes", "tous"}:
        return None
    if text.startswith("tunisien"):
        return "TN"
    return text.upper()


# ---------------------------------------------------------------------------
# Contrôle de cohérence : signaler sans corriger
# ---------------------------------------------------------------------------

_EXPECTED_MIN_RANK = {
    DiplomaType.BTS: Level.RANK[Level.BAC],
    DiplomaType.LICENCE: Level.RANK[Level.BAC_PLUS_2],
    DiplomaType.LICENCE_PRO: Level.RANK[Level.BAC_PLUS_2],
    DiplomaType.INGENIEUR: Level.RANK[Level.LICENCE],
}


def consistency_warnings(diploma_type: str | None, level: LevelRequirement, bac_rule: str) -> list[str]:
    """
    Détecte les lignes probablement mal saisies, sans les modifier : on ne change
    pas les données métier de l'école, on les signale pour que l'équipe tranche.
    """
    warnings: list[str] = []
    if diploma_type is None:
        warnings.append("Type de diplôme non reconnu.")
    if not level.parsed:
        warnings.append("Niveau éligible non compris.")

    expected = _EXPECTED_MIN_RANK.get(diploma_type or "")
    if expected and level.min_level and Level.RANK[level.min_level] < expected:
        warnings.append(
            f"Niveau requis ({Level.LABELS[level.min_level]}) inhabituellement bas "
            "pour ce type de diplôme : saisie à vérifier."
        )
    if bac_rule == BacRule.NOT_REQUIRED and level.min_level and Level.RANK[level.min_level] >= Level.RANK[Level.BAC]:
        warnings.append("Contradiction : « sans bac » alors que le niveau requis est au moins le bac.")
    return warnings