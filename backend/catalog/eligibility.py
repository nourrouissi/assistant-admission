"""
Moteur d'éligibilité : compare le profil déclaré d'un prospect aux critères d'une formation.

Règle du sujet : une recherche de formations n'est pas une validation d'éligibilité.
On ne confirme jamais l'éligibilité si un critère nécessaire n'est pas renseigné
ou n'est pas vérifiable.

Le calcul est déterministe (Python pur, sans LLM) : mêmes entrées, même résultat.
Il est donc reproductible, explicable et testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Formation
from .normalization import BacRule, BacSection, Level, is_all, normalize_nationality


# ===========================================================================
# ÉTAPE 1 · Les statuts, le profil et le résultat
# ===========================================================================

class Status:
    """Les 4 statuts possibles d'une formation pour un prospect."""

    INCOMPLETE = "incomplet"                      # il manque une information
    NOT_COMPATIBLE = "non_compatible"             # un critère n'est pas rempli
    CONDITIONAL = "a_confirmer"                   # le code ne peut ni confirmer ni refuser : l'équipe tranche
    COMPATIBLE = "compatible"                     # tous les critères déclarés sont remplis


# Sujet : « Afficher les formations pertinentes dès que possible, puis affiner les
# résultats selon les informations reçues ». Ordre d'affichage des cartes après une
# vérification : d'abord ce qui correspond au profil, en dernier ce qui ne correspond pas.
STATUS_ORDER = [Status.COMPATIBLE, Status.CONDITIONAL, Status.INCOMPLETE, Status.NOT_COMPATIBLE]


def status_rank(status: str) -> int:
    """Position d'un statut dans l'ordre d'affichage (0 = en premier)."""
    return STATUS_ORDER.index(status)


class Check:
    """Résultat d'UNE vérification (niveau, nationalité ou bac)."""

    OK = "ok"
    MISSING = "manquant"
    FAILED = "non"
    RESERVED = "sous_reserve"


# Précision ajoutée quand les données de la formation ont été signalées comme douteuses à l'import
UNVERIFIED_CRITERIA = "les critères de cette formation sont en cours de vérification par l'équipe des admissions"

# Toujours rappelée : la décision appartient à l'équipe, jamais au chatbot
FINAL_DECISION = "La décision finale revient à l'équipe des admissions."

# Libellés des informations à demander au prospect
MISSING_LEVEL = "niveau d'études"
MISSING_NATIONALITY = "nationalité"
MISSING_BAC_SECTION = "section du bac (ou du secondaire)"

# Diplômes professionnels et années du secondaire : le fichier ne dit pas s'ils
# sont équivalents, donc le code ne les compare pas (voir check_level).
PROFESSIONAL_LEVELS = {Level.CAP, Level.BTP}
SECONDARY_YEARS = {Level.DEUXIEME_SEC, Level.TROISIEME_SEC, Level.QUATRIEME_SEC}


@dataclass
class Profile:
    """
    Informations déclarées par le prospect. Tout est facultatif : on peut
    évaluer une formation sans rien savoir, le résultat sera « incomplet ».
    """

    level: str | None = None                 # code de Level : "BAC", "BAC_PLUS_2", "CAP", "BTP"…
    nationality: str | None = None           # code pays : "TN", "FR"…
    bac_section: str | None = None           # code de BacSection : "INFORMATIQUE"…

    def __post_init__(self) -> None:
        """Valide les valeurs : un code inconnu est refusé, jamais deviné."""
        if self.level is not None and self.level not in Level.RANK:
            raise ValueError(f"Niveau d'études inconnu : {self.level}")
        if self.bac_section is not None and self.bac_section not in BacSection.LABELS:
            raise ValueError(f"Section du bac inconnue : {self.bac_section}")
        if self.nationality:
            # « Tunisienne », « Tunisie », « tn »… -> "TN" ; « 123 » -> ValueError
            self.nationality = normalize_nationality(self.nationality)


@dataclass
class EligibilityResult:
    """Résultat de l'évaluation d'une formation pour un profil."""

    status: str
    missing: list[str] = field(default_factory=list)   # informations à demander
    reasons: list[str] = field(default_factory=list)   # critères non remplis ou à confirmer
    no_criteria: bool = False                          # la formation n'impose aucun critère


def _to_confirm(criterion: str, official_text: str) -> str:
    """Motif d'un critère que le code n'a pas compris : il est cité, jamais interprété."""
    return f"{criterion} à confirmer par l'équipe des admissions (critère officiel : « {official_text} »)"


def has_criteria(formation: Formation) -> bool:
    """Faux si la formation n'impose aucun critère (niveau, nationalité et bac « All », ou bac non requis)."""
    return not (
        is_all(formation.level_raw)
        and is_all(formation.nationality_raw)
        and (formation.bac_rule == BacRule.NOT_REQUIRED or is_all(formation.bac_raw))
    )


# ===========================================================================
# ÉTAPE 2 · Vérifier le niveau d'études
# ===========================================================================

def check_level(formation: Formation, profile: Profile) -> tuple[str, str]:
    """
    Compare le niveau du prospect au niveau minimal de la formation.
    Retourne (résultat, explication).
    """
    if formation.min_level is None:
        if is_all(formation.level_raw):
            return Check.OK, ""                               # « All » : aucune exigence
        # Texte non compris à l'import : on ne devine pas, l'équipe tranche
        return Check.RESERVED, _to_confirm("niveau", formation.level_raw)
    if profile.level is None:
        return Check.MISSING, MISSING_LEVEL

    # Voie alternative citée par le fichier : « … ou CAP / BTP dans le même secteur »
    if profile.level in formation.level_alternatives:
        if formation.alternatives_same_sector:
            return Check.RESERVED, (
                "accès possible avec votre diplôme professionnel, sous réserve que "
                "l'équipe des admissions confirme qu'il relève du même secteur"
            )
        return Check.OK, ""

    # CAP ou BTP face à une année du secondaire (ex. BTP et « 4ème année secondaire ») :
    # le fichier ne dit pas s'ils sont équivalents, on ne confirme ni ne refuse.
    if profile.level in PROFESSIONAL_LEVELS and formation.min_level in SECONDARY_YEARS:
        return Check.RESERVED, _to_confirm("niveau", formation.level_raw)

    if Level.RANK[profile.level] >= Level.RANK[formation.min_level]:
        return Check.OK, ""

    # On cite le texte officiel de l'école : il montre aussi les voies
    # « ou CAP / ou BTP dans le même secteur », que le seul niveau minimal cacherait.
    return Check.FAILED, f"niveau requis : {formation.level_raw}"


# ===========================================================================
# ÉTAPE 3 · Vérifier la nationalité
# ===========================================================================

def check_nationality(formation: Formation, profile: Profile) -> tuple[str, str]:
    """Vérifie la nationalité, seulement si la formation en exige une."""
    if formation.nationality_required is None:
        if is_all(formation.nationality_raw):
            return Check.OK, ""                               # toutes nationalités
        # Ex. « Tunisienne ou Algérienne » : non comprise à l'import, l'équipe tranche
        return Check.RESERVED, _to_confirm("nationalité", formation.nationality_raw)
    if profile.nationality is None:
        return Check.MISSING, MISSING_NATIONALITY
    if profile.nationality == formation.nationality_required:
        return Check.OK, ""
    return Check.FAILED, f"nationalité requise : {formation.nationality_raw}"


# ===========================================================================
# ÉTAPE 4 · Vérifier la nature du bac
# ===========================================================================

def check_bac(formation: Formation, profile: Profile) -> tuple[str, str]:
    """Vérifie la section du bac (ou du secondaire), seulement si elle est exigée."""
    if formation.bac_rule == BacRule.ANY and not is_all(formation.bac_raw):
        # Ex. « Bac français » : non comprise à l'import, l'équipe tranche
        return Check.RESERVED, _to_confirm("nature du bac", formation.bac_raw)
    if formation.bac_rule != BacRule.SECTIONS:
        return Check.OK, ""                                   # toutes sections ou bac non requis
    if profile.bac_section is None:
        return Check.MISSING, MISSING_BAC_SECTION
    if profile.bac_section in formation.bac_sections:
        return Check.OK, ""
    # On cite le texte officiel de l'école, sans le reformuler
    return Check.FAILED, f"section requise : {formation.bac_raw}"


# ===========================================================================
# ÉTAPE 5 · Combiner les vérifications et formuler le résultat
# ===========================================================================

def evaluate(formation: Formation, profile: Profile) -> EligibilityResult:
    """
    Évalue une formation pour un profil, en combinant les 3 vérifications.

    Ordre de priorité :
      1. un critère « non »         -> non_compatible (inutile de demander le reste)
      2. sinon, un critère manquant -> incomplet (avec la liste des informations)
      3. sinon, un critère réservé  -> a_confirmer
      4. sinon                      -> compatible

    Si l'import a signalé une anomalie sur cette formation, ses critères ne sont
    pas considérés comme vérifiés : le code ne la confirme pas et ne la refuse
    pas non plus. Un critère non rempli devient un point à confirmer par l'équipe.
    """
    checks = [
        check_level(formation, profile),
        check_nationality(formation, profile),
        check_bac(formation, profile),
    ]
    failed = [detail for outcome, detail in checks if outcome == Check.FAILED]
    missing = [detail for outcome, detail in checks if outcome == Check.MISSING]
    reserved = [detail for outcome, detail in checks if outcome == Check.RESERVED]

    if formation.import_warnings:
        # Données douteuses : ni confirmation ni refus ferme
        reserved += [f"d'après vos informations, ce critère ne semble pas rempli ({detail})" for detail in failed]
        reserved.append(UNVERIFIED_CRITERIA)
        failed = []

    if failed:
        return EligibilityResult(Status.NOT_COMPATIBLE, reasons=failed)
    if missing:
        # Les réserves déjà connues (dont « en cours de vérification ») restent visibles
        return EligibilityResult(Status.INCOMPLETE, missing=missing, reasons=reserved)
    if reserved:
        return EligibilityResult(Status.CONDITIONAL, reasons=reserved)
    return EligibilityResult(Status.COMPATIBLE, no_criteria=not has_criteria(formation))


def missing_information(results: list[EligibilityResult]) -> list[str]:
    """
    Regroupe, sans doublon et dans l'ordre, les informations manquantes de
    plusieurs formations : on ne demande au prospect que ce qui est utile
    pour les formations affichées.
    """
    collected: list[str] = []
    for result in results:
        for item in result.missing:
            if item not in collected:
                collected.append(item)
    return collected


def message_for(result: EligibilityResult) -> str:
    """
    Formulation fixe du statut, affichée au prospect.
    Jamais « éligible » ni « admis » : les informations sont déclarées et la
    décision finale appartient à l'équipe des admissions.
    """
    if result.status == Status.INCOMPLETE:
        message = "Pour vérifier les critères de cette formation, j'ai besoin de : " + ", ".join(result.missing) + "."
        if result.reasons:
            message += " À noter : " + " ; ".join(result.reasons) + "."
        return message

    if result.status == Status.NOT_COMPATIBLE:
        intro = "ces critères ne sont pas remplis" if len(result.reasons) > 1 else "ce critère n'est pas rempli"
        return f"D'après les informations indiquées, {intro} : " + " ; ".join(result.reasons) + "."

    if result.status == Status.CONDITIONAL:
        return (
            "Je ne peux pas confirmer automatiquement les critères de cette formation : "
            + " ; ".join(result.reasons) + ". " + FINAL_DECISION
        )

    if result.no_criteria:
        return "Cette formation n'impose pas de critère d'admission particulier. " + FINAL_DECISION
    return "Vous remplissez les critères affichés pour cette formation. " + FINAL_DECISION
