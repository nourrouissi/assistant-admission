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


# Valeurs du fichier qui signifient « aucune restriction » (texte plié)
_ALL_VALUES = {"", "all", "tous", "toutes"}


def is_all(value: str | None) -> bool:
    """« All », « Toutes »… : la colonne n'impose aucune restriction."""
    return fold(value) in _ALL_VALUES


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


def parse_diploma_type_code(value: str) -> str:
    """
    Code de type de diplôme envoyé à l'API (« bts », « BTS ») -> code normalisé.
    Un code inconnu est refusé avec la liste des valeurs possibles, jamais deviné.
    """
    code = clean_spaces(value).upper()
    if code not in DiplomaType.LABELS:
        raise ValueError(
            f"Type de diplôme inconnu : « {value} ». Valeurs possibles : {', '.join(DiplomaType.LABELS)}."
        )
    return code


# ---------------------------------------------------------------------------
# Spécialités et écoles
# ---------------------------------------------------------------------------

_SPECIALTY_PREFIX = re.compile(r"^(bts|btp)\s*[-_]\s*", re.IGNORECASE)


def clean_specialty(raw: str) -> str:
    """
    Forme comparable d'une spécialité, utilisée seulement pour repérer les doublons
    (« BTS-Comptabilité » ~ « Comptabilité ») : l'affichage garde le texte du fichier.
    """
    text = _SPECIALTY_PREFIX.sub("", clean_spaces(raw))
    text = re.sub(r"(\S)\(", r"\1 (", text)  # « Informatiques(cours du soir) » -> espace avant « ( »
    return text[:1].upper() + text[1:] if text else text


def school_city(school: str) -> str:
    """« IMSET SOUSSE » -> « Sousse »."""
    parts = clean_spaces(school).split(" ", 1)
    return parts[1].title() if len(parts) == 2 else ""


def duplicate_key(diploma_label: str, specialty_raw: str, school: str) -> tuple:
    """
    Clé de comparaison de deux lignes de l'Excel : même type de diplôme, même
    spécialité nettoyée (sans préfixe « BTS- », sans accents ni casse), même école.

    Sujet : l'assistant « ne doit pas confirmer l'éligibilité si les critères
    nécessaires ne sont pas […] vérifiés ». Deux lignes de même clé sont un
    doublon probable, souvent avec des critères différents : on les signale.
    Ex. « Décoration et design d'intérieur » et « BTS-Décoration et design
    d'intérieur » à IMSET SOUSSE.
    """
    return (
        normalize_diploma_type(diploma_label),
        fold(clean_specialty(specialty_raw)),
        clean_spaces(school).upper(),
    )


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
        QUATRIEME_SEC: "4ème année secondaire",
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

    if text in _ALL_VALUES:
        return LevelRequirement(min_level=None)

    # « sans bac » précise que le bac n'est PAS exigé : ce « bac » ne doit pas
    # être lu comme un niveau requis (« 4ème sans bac » = 4ème année).
    without_sans_bac = re.sub(r"\bsans? bac\b", " ", text)

    req = LevelRequirement()
    if "licence+1" in compact:
        req.min_level = Level.LICENCE_PLUS_1
    elif "licence" in text:
        req.min_level = Level.LICENCE
    elif "bac+2" in compact:
        req.min_level = Level.BAC_PLUS_2
    elif re.search(r"\bbac\b", without_sans_bac):
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

    # Mots-clés (texte plié) -> section, pour lire la colonne « Nature du bac » du fichier.
    KEYWORDS = {
        "math": MATH, "experimental": SCIENCES_EXP, "technique": TECHNIQUE,
        "informatique": INFORMATIQUE,
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
    Une valeur non comprise renvoie aussi (ANY, []) : bac_rule_understood() permet
    de la distinguer d'un vrai « All » pour la signaler comme anomalie.
    """
    text = fold(raw)
    if text in _ALL_VALUES:
        return BacRule.ANY, []
    if re.fullmatch(r"sans? bac", text):
        return BacRule.NOT_REQUIRED, []
    sections = detect_bac_sections(text)
    if sections:
        return BacRule.SECTIONS, sections
    return BacRule.ANY, []


def bac_rule_understood(raw: str) -> bool:
    """Faux si la nature du bac n'a pas été comprise (ex. « Bac français »)."""
    rule, _ = parse_bac_rule(raw)
    return rule != BacRule.ANY or is_all(raw)


# ---------------------------------------------------------------------------
# Nationalité
# ---------------------------------------------------------------------------

# Formes reconnues de la nationalité tunisienne (texte plié) : nationalité,
# pays, anglais, arabe, codes ISO à 2 et 3 lettres.
_TUNISIAN = {
    "tunisienne", "tunisien", "tunisiennes", "tunisiens",
    "tunisie", "tunisia", "tunisian", "tunisians", "tn", "tun",
    "تونسية", "تونسي", "تونسيه", "تونس", "التونسية", "التونسي",
}

# Une nationalité déclarée : des lettres latines ou arabes (espaces, tirets, apostrophes admis), 2 à 40 caractères.
_NATIONALITY_SHAPE = re.compile(r"[a-z\u0621-\u064a][a-z\u0621-\u064a' -]{1,39}")

# Séparateurs d'une double nationalité déclarée : « et », virgule, barre oblique.
_DUAL_NATIONALITY_SEPARATOR = re.compile(r"\s*(?:,|/|\bet\b)\s*")


def parse_nationality(raw: str) -> str | None:
    """
    Colonne « Nationalité éligible » de l'Excel -> code de la nationalité exigée.
    « All » -> None (toutes nationalités) ; « Tunisienne » -> "TN".

    Toute autre valeur (« Tunisienne ou Algérienne », nationalité inconnue) n'est
    pas comprise : on renvoie None au lieu de la réduire à "TN", et l'import la
    signale comme anomalie (voir nationality_understood). Le moteur d'éligibilité
    laisse alors ce critère à l'équipe des admissions (« sous réserve »).
    """
    return "TN" if fold(raw) in _TUNISIAN else None


def nationality_understood(raw: str) -> bool:
    """Vrai si la colonne « Nationalité éligible » est « All » ou la nationalité tunisienne."""
    return is_all(raw) or fold(raw) in _TUNISIAN


def normalize_nationality(value: str) -> str:
    """
    Nationalité déclarée par le prospect -> code comparable au critère de la formation.

    « Tunisie », « tunisian », « TUN »… -> "TN". Une autre nationalité est gardée
    pliée en majuscules (« Française » -> "FRANCAISE") : elle ne correspond pas à
    "TN", ce qui est voulu. Une valeur qui ne ressemble pas à une nationalité
    (« 123 », « ?? ») lève ValueError : elle est refusée, jamais transformée en
    refus d'éligibilité.
    """
    text = fold(value)
    if text in _TUNISIAN:
        return "TN"

    # Sujet : critère « la nationalité ». Double nationalité (« Tunisienne et
    # française », « tunisienne, française », « tunisienne / française ») : le
    # prospect a la nationalité tunisienne. Chaque partie doit ressembler à une
    # nationalité, sinon la valeur est refusée.
    parts = [part.strip() for part in _DUAL_NATIONALITY_SEPARATOR.split(text)]
    if len(parts) > 1 and all(_NATIONALITY_SHAPE.fullmatch(part) for part in parts):
        if any(part in _TUNISIAN for part in parts):
            return "TN"

    if not _NATIONALITY_SHAPE.fullmatch(text):
        raise ValueError("Nationalité non reconnue.")
    return text.upper()


# ---------------------------------------------------------------------------
# Contrôle de cohérence : signaler sans corriger
# ---------------------------------------------------------------------------

def consistency_warnings(
    diploma_type: str | None,
    level: LevelRequirement,
    bac_rule: str,
    *,
    bac_parsed: bool = True,
    nationality_parsed: bool = True,
) -> list[str]:
    """
    Détecte les lignes que le code ne peut pas lire de façon sûre, sans les modifier :
    valeur non comprise, ou contradiction interne à la ligne. Aucune supposition sur
    le niveau « normal » d'un diplôme : les critères de l'école font foi.
    Une formation avec anomalie n'est jamais confirmée « compatible » (voir eligibility.py).
    """
    warnings: list[str] = []
    if diploma_type is None:
        warnings.append("Type de diplôme non reconnu.")
    if not level.parsed:
        warnings.append("Niveau éligible non compris.")
    if not nationality_parsed:
        warnings.append("Nationalité éligible non comprise.")
    if not bac_parsed:
        warnings.append("Nature du bac non comprise.")
    if bac_rule == BacRule.NOT_REQUIRED and level.min_level and Level.RANK[level.min_level] >= Level.RANK[Level.BAC]:
        warnings.append("Contradiction : « sans bac » alors que le niveau requis est au moins le bac.")
    return warnings