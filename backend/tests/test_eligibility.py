"""
Tests du moteur d'éligibilité et de son API.

Les cas de référence couvrent chaque règle du moteur (information manquante,
critère refusé, voie « même secteur », section du bac, formation sans critère…),
sur les vraies formations du fichier Excel.
"""

import re

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from catalog.eligibility import Profile, Status, evaluate, message_for, missing_information
from catalog.importer import import_formations
from catalog.models import Formation
from catalog.services import search_formations

pytestmark = pytest.mark.django_db

EXCEL = settings.BASE_DIR / "data" / "diplome_specialite.xlsx"


@pytest.fixture
def catalog():
    """Importe le fichier réel et renvoie les formations utilisées dans les tests."""
    import_formations(EXCEL)
    return {
        "batiment": Formation.objects.get(specialty__icontains="batiment"),           # Bac+2, tunisienne
        "compta": Formation.objects.get(specialty="Comptabilité et Finances", school="IMSET TUNIS"),  # bac ou BTP
        "pharmacie": Formation.objects.get(specialty__icontains="pharmacie"),         # 4ème + maths / sciences
        "cableur": Formation.objects.get(specialty__icontains="cableur"),             # aucun critère
        "info_gestion": Formation.objects.get(
            diploma_type="BTS", specialty__iexact="informatique de gestion", school="IMSET TUNIS"
        ),
    }


# --- Le profil ------------------------------------------------------------------

def test_profile_normalizes_nationality():
    assert Profile(nationality="Tunisienne").nationality == "TN"


def test_profile_rejects_unknown_codes():
    with pytest.raises(ValueError):
        Profile(level="XYZ")
    with pytest.raises(ValueError):
        Profile(bac_section="CUISINE")


# --- Les 9 cas de référence --------------------------------------------------------

@pytest.mark.parametrize("case, formation, profile, expected", [
    ("profil vide sur une formation à critères", "batiment", {}, Status.INCOMPLETE),
    ("nationalité différente de celle exigée", "batiment", {"level": "BAC_PLUS_2", "nationality": "FR"}, Status.NOT_COMPATIBLE),
    ("niveau et nationalité remplis", "batiment", {"level": "BAC_PLUS_2", "nationality": "Tunisienne"}, Status.COMPATIBLE),
    ("niveau inférieur au minimum", "batiment", {"level": "BAC"}, Status.NOT_COMPATIBLE),
    ("voie BTP « même secteur » à confirmer", "compta", {"level": "BTP"}, Status.CONDITIONAL),
    ("section du bac exigée mais non indiquée", "pharmacie", {"level": "4EME_SEC"}, Status.INCOMPLETE),
    ("section du bac non autorisée", "pharmacie", {"level": "4EME_SEC", "bac_section": "LETTRES"}, Status.NOT_COMPATIBLE),
    ("formation sans aucun critère", "cableur", {}, Status.COMPATIBLE),
    ("niveau supérieur au minimum", "info_gestion", {"level": "LICENCE"}, Status.COMPATIBLE),
])
def test_specification_cases(catalog, case, formation, profile, expected):
    assert evaluate(catalog[formation], Profile(**profile)).status == expected, case


def test_failed_criterion_wins_over_missing_information(catalog):
    # Niveau insuffisant + nationalité inconnue : on ne demande pas la nationalité.
    result = evaluate(catalog["batiment"], Profile(level="BAC"))
    assert result.status == Status.NOT_COMPATIBLE
    assert result.missing == []


def test_missing_information_lists_only_what_is_needed(catalog):
    result = evaluate(catalog["batiment"], Profile())
    assert result.missing == ["niveau d'études", "nationalité"]
    # Pour toutes les formations en informatique, seul le niveau est utile.
    results = [evaluate(f, Profile()) for f in search_formations("informatique")]
    assert missing_information(results) == ["niveau d'études"]


def test_subject_example_bac_informatique(catalog):
    # Exemple 2 du sujet : « J'ai un bac informatique, quelles spécialités me correspondent ? »
    profile = Profile(level="BAC", bac_section="INFORMATIQUE")
    statuses = [evaluate(f, profile).status for f in search_formations("informatique")]
    # 28 formations contenant « informatique »
    assert statuses.count(Status.COMPATIBLE) == 18
    assert statuses.count(Status.CONDITIONAL) == 1      # la ligne contradictoire (Sousse)
    assert statuses.count(Status.NOT_COMPATIBLE) == 9


# --- Les données signalées comme douteuses ------------------------------------------------

def test_suspicious_formation_is_never_confirmed(catalog):
    # BTS à Sousse signalé à l'import comme doublon probable de « BTS-Décoration… ».
    suspicious = Formation.objects.get(
        diploma_type="BTS", school="IMSET SOUSSE", specialty="Décoration et design d'intérieur"
    )
    assert suspicious.import_warnings
    result = evaluate(suspicious, Profile(level="BAC"))
    assert result.status == Status.CONDITIONAL
    assert any("en cours de vérification" in reason for reason in result.reasons)


def test_suspicious_formation_is_never_refused(catalog):
    # Données douteuses : un critère non rempli devient un point à confirmer, pas un refus.
    suspicious = Formation.objects.get(
        diploma_type="BTS", school="IMSET SOUSSE", specialty="Décoration et design d'intérieur"
    )
    result = evaluate(suspicious, Profile(level="9EME"))
    assert result.status == Status.CONDITIONAL
    assert any("ne semble pas rempli" in reason for reason in result.reasons)
    assert any("en cours de vérification" in reason for reason in result.reasons)


def test_contradictory_line_is_never_refused(catalog):
    # Ligne 34 : « bac ou BTP » mais « san bac ».
    contradictory = Formation.objects.get(
        diploma_type="BTP", school="IMSET SOUSSE", specialty="Maintenance Micro-système Informatique"
    )
    assert evaluate(contradictory, Profile(level="2EME_SEC")).status == Status.CONDITIONAL


def test_no_firm_refusal_on_any_flagged_formation(catalog):
    profiles = [{"level": "9EME"}, {"level": "2EME_SEC"}, {"level": "BAC", "nationality": "FR"}]
    for formation in Formation.objects.exclude(import_warnings=[]):
        for profile in profiles:
            assert evaluate(formation, Profile(**profile)).status != Status.NOT_COMPATIBLE


# --- Diplôme professionnel face à une année du secondaire ------------------------------

@pytest.mark.parametrize("level", ["CAP", "BTP"])
def test_professional_diploma_vs_secondary_year_is_to_confirm(catalog, level):
    # Préparateur en Pharmacie : « 4ème année secondaire ». Le fichier ne dit pas
    # si un CAP ou un BTP vaut une 4ème année : ni refus ni confirmation.
    result = evaluate(catalog["pharmacie"], Profile(level=level, bac_section="MATH"))
    assert result.status == Status.CONDITIONAL
    assert any("4ème année secondaire" in reason for reason in result.reasons)


def test_professional_diploma_listed_as_alternative_is_still_same_sector(catalog):
    # « bac ou BTP dans le même secteur » : la voie BTP est citée par le fichier.
    result = evaluate(catalog["compta"], Profile(level="BTP"))
    assert result.status == Status.CONDITIONAL
    assert any("même secteur" in reason for reason in result.reasons)


def test_professional_diploma_not_listed_for_bac_level_is_refused(catalog):
    # « bac ou BTP » ne cite pas le CAP : le refus s'appuie sur le fichier.
    assert evaluate(catalog["compta"], Profile(level="CAP")).status == Status.NOT_COMPATIBLE


def test_profile_has_no_professional_diploma_field():
    with pytest.raises(TypeError):
        Profile(professional_diploma="CAP")


# --- Les messages : jamais de confirmation d'admission ---------------------------------

def test_messages_never_promise_admission(catalog):
    profiles = [{}, {"level": "BAC"}, {"level": "MASTER", "nationality": "TN", "bac_section": "MATH"}]
    for formation in catalog.values():
        for profile in profiles:
            message = message_for(evaluate(formation, Profile(**profile))).lower()
            # \b = limite de mot : « admis » est interdit, mais « admissions » est autorisé
            assert not re.search(r"\badmise?s?\b", message)
            assert not re.search(r"\béligible", message)


def test_compatible_message_mentions_final_decision(catalog):
    message = message_for(evaluate(catalog["cableur"], Profile()))
    assert "décision finale revient à l'équipe des admissions" in message


# --- L'API ------------------------------------------------------------------------------

def post(payload):
    return APIClient().post("/api/formations/eligibility/", payload, format="json")


def test_api_returns_cards_with_status(catalog):
    response = post({"profile": {"level": "BAC", "bac_section": "INFORMATIQUE"}, "q": "informatique"})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 28
    assert data["missing_information"] == []
    assert {"status", "missing", "reasons", "message"} <= data["results"][0]["eligibility"].keys()


def test_api_without_profile_lists_missing_information(catalog):
    data = post({"q": "batiment"}).json()
    assert data["missing_information"] == ["niveau d'études", "nationalité"]


def test_api_accepts_formation_ids(catalog):
    data = post({"profile": {"level": "BAC_PLUS_2", "nationality": "TN"}, "formation_ids": [catalog["batiment"].id]}).json()
    assert data["results"][0]["eligibility"]["status"] == Status.COMPATIBLE


def test_api_rejects_invalid_profile(catalog):
    assert post({"profile": {"level": "XYZ"}, "q": "batiment"}).status_code == 400


def test_search_and_eligibility_stay_separate(catalog):
    # La recherche seule ne renvoie jamais de statut d'éligibilité.
    card = APIClient().get("/api/formations/", {"q": "batiment"}).json()["results"][0]
    assert "eligibility" not in card