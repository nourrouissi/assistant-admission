"""
Tests des règles du catalogue : recherche, nationalité, valeurs non comprises,
API d'éligibilité, cartes, messages et import.

Les tests marqués « db » importent le vrai fichier Excel dans une base temporaire ;
les autres construisent une formation en mémoire (aucun accès à la base).
"""

import re
from io import StringIO

import pytest
from django.conf import settings
from django.core.management import call_command
from rest_framework.test import APIClient

from catalog.eligibility import Profile, Status, evaluate, message_for
from catalog.importer import build_formation_fields, import_formations
from catalog.models import Formation
from catalog import normalization
from catalog.normalization import Level
from catalog.serializers import FormationSerializer
from catalog.services import _keywords

EXCEL = settings.BASE_DIR / "data" / "diplome_specialite.xlsx"

# Une garantie d'admission est interdite. « admissions » contient « admis » :
# la limite de mot (\b) évite ce faux positif.
ADMISSION_PROMISE = re.compile(r"\badmise?s?\b|\béligible|garanti", re.IGNORECASE)


@pytest.fixture
def imported(db):
    """Importe le fichier Excel réel dans la base de test."""
    return import_formations(EXCEL)


def search(**params):
    return APIClient().get("/api/formations/", params)


def count(**params) -> int:
    return search(**params).json()["count"]


def all_ids(**params) -> set[int]:
    """Identifiants de toutes les formations trouvées (toutes pages confondues)."""
    ids, page = set(), 1
    while True:
        data = search(page=page, **params).json()
        ids |= {item["id"] for item in data["results"]}
        if not data["next"]:
            return ids
        page += 1


def post_eligibility(payload):
    return APIClient().post("/api/formations/eligibility/", payload, format="json")


def formation_from(**overrides) -> Formation:
    """Formation en mémoire construite comme à l'import, à partir d'une ligne Excel fictive."""
    row = {
        "diploma": "Brevet de Technicien Supérieur", "specialty": "Test", "school": "IMSET TUNIS",
        "level": "bac", "nationality": "All", "bac": "All",
    }
    row.update(overrides)
    return Formation(specialty_raw=row["specialty"], **build_formation_fields(row))


# ===========================================================================
# Découpage des mots de la recherche
# ===========================================================================

def test_keywords_are_folded_split_and_deduplicated():
    assert _keywords("Informatique, réseaux ; informatique") == ["informatique", "reseaux"]


def test_short_words_are_ignored():
    assert _keywords("BTS en info") == ["bts", "info"]


def test_punctuation_does_not_break_search(imported):
    assert count(q="informatique,") == count(q="informatique ?") == count(q="informatique") > 0


def test_no_hand_written_language_rules(imported):
    # Ni synonymes, ni mots vides, ni domaines : le LLM extrait les mots-clés,
    # la recherche trouve les formations qui contiennent ces mots, rien de plus.
    from catalog import services
    for name in ("SYNONYMS", "STOP_WORDS", "DOMAINS"):
        assert not hasattr(services, name)
    assert count(q="informatique") == 28


# ===========================================================================
# Mots-clés en début de mot, combinés en ET
# ===========================================================================

def test_prefix_finds_ingenieur_and_ingenierie(imported):
    bachelor = Formation.objects.get(diploma_type="BACHELOR", specialty="Ingénierie")
    engineers = set(Formation.objects.filter(diploma_type="INGENIEUR").values_list("id", flat=True))
    assert bachelor.id in all_ids(q="ingénierie")
    assert engineers <= all_ids(q="ingénieur")
    assert all_ids(q="inge") == engineers | {bachelor.id}


def test_keywords_are_combined_with_and(imported):
    # « informatique sousse » = informatique ET école de Sousse
    assert all_ids(q="informatique sousse") == all_ids(q="informatique", school="Sousse")


# ===========================================================================
# Nationalité
# ===========================================================================

@pytest.mark.parametrize("value", ["Tunisienne", "tunisien", "Tunisie", "tunisian", "TUNISIA", "TN", "tun", "  Tunisienne "])
def test_tunisian_variants_are_recognized(value):
    assert normalization.normalize_nationality(value) == "TN"


@pytest.mark.parametrize("value", ["123", "??", "a", "tn1"])
def test_invalid_nationality_is_rejected(value):
    with pytest.raises(ValueError):
        normalization.normalize_nationality(value)


def test_tunisie_is_not_refused_for_a_tunisian_only_formation(imported):
    batiment = Formation.objects.get(specialty="Licence en Batiment")
    card = post_eligibility({"profile": {"nationality": "Tunisie"}, "formation_ids": [batiment.id]}).json()["results"][0]
    assert card["eligibility"]["status"] != Status.NOT_COMPATIBLE
    assert "nationalité" not in card["eligibility"]["missing"]


def test_invalid_nationality_returns_400(imported):
    response = post_eligibility({"profile": {"nationality": "123"}, "q": "batiment"})
    assert response.status_code == 400
    assert "Nationalité non reconnue." in str(response.json())


@pytest.mark.parametrize("raw", ["Tunisienne ou Algérienne", "Tunisienne, Libyenne"])
def test_multi_valued_nationality_is_flagged_not_reduced(raw):
    formation = formation_from(nationality=raw)
    assert "Nationalité éligible non comprise." in formation.import_warnings
    assert formation.nationality_required != "TN"
    # Un prospect algérien n'est ni refusé ni confirmé : l'équipe tranche.
    result = evaluate(formation, Profile(level="BAC", nationality="Algérienne"))
    assert result.status == Status.CONDITIONAL


# ===========================================================================
# Valeurs non comprises dans l'Excel
# ===========================================================================

def test_unknown_bac_nature_is_flagged_and_never_confirmed():
    formation = formation_from(bac="Bac français")
    assert "Nature du bac non comprise." in formation.import_warnings
    assert evaluate(formation, Profile(level="BAC", bac_section="MATH")).status == Status.CONDITIONAL


def test_unknown_level_is_flagged_and_never_confirmed():
    formation = formation_from(level="Niveau à définir")
    assert "Niveau éligible non compris." in formation.import_warnings
    assert evaluate(formation, Profile(level="MASTER")).status == Status.CONDITIONAL


def test_sans_bac_in_level_text_is_not_read_as_bac():
    # « sans bac » précise que le bac n'est pas exigé : ce n'est pas un niveau.
    assert formation_from(level="4ème sans bac").min_level == Level.QUATRIEME_SEC


# ===========================================================================
# API éligibilité : formation_ids
# ===========================================================================

def test_empty_formation_ids_is_rejected(imported):
    assert post_eligibility({"formation_ids": []}).status_code == 400


def test_too_many_formation_ids_is_rejected(imported):
    assert post_eligibility({"formation_ids": list(range(1, 102))}).status_code == 400


def test_unknown_and_inactive_formation_ids_are_reported(imported):
    batiment = Formation.objects.get(specialty="Licence en Batiment")
    inactive = Formation.objects.get(specialty__icontains="cableur")
    inactive.is_active = False
    inactive.save()
    response = post_eligibility({"formation_ids": [batiment.id, 99999, inactive.id]})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["unknown_formation_ids"] == [99999, inactive.id]


def test_search_request_reports_no_unknown_ids(imported):
    assert post_eligibility({"q": "batiment"}).json()["unknown_formation_ids"] == []


# ===========================================================================
# Validation de diploma_type
# ===========================================================================

def test_unknown_diploma_type_returns_400_with_choices(imported):
    response = search(diploma_type="XYZ")
    assert response.status_code == 400
    assert "BTS" in str(response.json())
    assert post_eligibility({"diploma_type": "XYZ"}).status_code == 400


def test_diploma_type_is_case_insensitive(imported):
    assert count(diploma_type="bts") == count(diploma_type="BTS") == 41
    assert post_eligibility({"diploma_type": "bts"}).json()["count"] == 41


# ===========================================================================
# Cartes fidèles aux données
# ===========================================================================

def test_card_shows_official_diploma_label(imported):
    gabes = Formation.objects.get(diploma_type="INGENIEUR", school="IMSET GABES")
    assert FormationSerializer(gabes).data["diploma"] == "INGENIEUR CNAM"
    # Aucun « Titre RNCP » ajouté quand le fichier ne le dit pas
    tunis = Formation.objects.get(diploma_type="TITRE_RNCP", school="IMSET TUNIS")
    assert FormationSerializer(tunis).data["diploma"] == "Concepteur en architecture informatique"


def test_card_flags_formation_under_review(imported):
    suspicious = Formation.objects.get(diploma_type="BTP", school="IMSET SOUSSE",
                                       specialty="Maintenance Micro-système Informatique")
    assert FormationSerializer(suspicious).data["criteria_under_review"] is True
    batiment = Formation.objects.get(specialty="Licence en Batiment")
    assert FormationSerializer(batiment).data["criteria_under_review"] is False


def test_card_never_says_no_requirement_for_an_unparsed_level():
    criteria = FormationSerializer(formation_from(level="Niveau à définir")).data["criteria"]
    assert criteria["level"] == "Niveau à définir"
    # Le texte du fichier est affiché tel quel, même « All »
    assert FormationSerializer(formation_from(level="All")).data["criteria"]["level"] == "All"


def test_card_criteria_are_copied_from_the_file(imported):
    pharmacie = Formation.objects.get(specialty="Préparateur en Pharmacie")
    assert FormationSerializer(pharmacie).data["criteria"] == {
        "level": "4ème année secondaire", "nationality": "All",
        "bac": "Sciences expérimentales ou Mathèmatique",
    }
    btp = Formation.objects.get(specialty="Informatique de Gestion", school="IMSET GABES", diploma_type="BTP")
    assert FormationSerializer(btp).data["criteria"]["bac"] == "san bac"


def test_card_keeps_the_specialty_prefix_of_the_file(imported):
    assert Formation.objects.filter(specialty="BTS-Comptabilité et Finances", school="IMSET SOUSSE").exists()
    assert Formation.objects.filter(specialty="BTS_Bioanalyses et Controles").exists()


def test_card_shows_unparsed_bac_text():
    assert FormationSerializer(formation_from(bac="Bac français")).data["criteria"]["bac"] == "Bac français"


# ===========================================================================
# Messages et motifs
# ===========================================================================

def test_level_refusal_quotes_official_text_with_btp_route(imported):
    compta = Formation.objects.get(specialty="Comptabilité et Finances", school="IMSET TUNIS")
    result = evaluate(compta, Profile(level="2EME_SEC"))
    assert result.status == Status.NOT_COMPATIBLE
    assert any("BTP" in reason for reason in result.reasons)


def test_level_label_does_not_say_sans_bac():
    assert Level.LABELS[Level.QUATRIEME_SEC] == "4ème année secondaire"


def test_formation_without_criteria_has_dedicated_message(imported):
    cableur = Formation.objects.get(specialty__icontains="cableur")
    message = message_for(evaluate(cableur, Profile()))
    assert message == ("Cette formation n'impose pas de critère d'admission particulier. "
                       "La décision finale revient à l'équipe des admissions.")


def test_several_failed_criteria_use_plural(imported):
    batiment = Formation.objects.get(specialty="Licence en Batiment")
    message = message_for(evaluate(batiment, Profile(level="BAC", nationality="FR")))
    assert "ces critères ne sont pas remplis" in message


def test_incomplete_result_keeps_review_notice(imported):
    suspicious = Formation.objects.get(diploma_type="BTS", school="IMSET SOUSSE", specialty="Décoration et design d'intérieur")
    result = evaluate(suspicious, Profile())
    assert result.status == Status.INCOMPLETE
    assert "en cours de vérification" in message_for(result)


def test_conditional_message_never_promises_admission(imported):
    compta = Formation.objects.get(specialty="Comptabilité et Finances", school="IMSET TUNIS")
    result = evaluate(compta, Profile(level="BTP"))
    assert result.status == Status.CONDITIONAL
    message = message_for(result)
    assert not ADMISSION_PROMISE.search(message)
    assert "décision finale revient à l'équipe des admissions" in message


def test_no_message_promises_admission_on_whole_catalog(imported):
    profiles = [{}, {"level": "9EME"}, {"level": "BAC", "bac_section": "LETTRES"},
                {"level": "BTP"},
                {"level": "MASTER", "nationality": "FR", "bac_section": "MATH"}]
    seen = set()
    for formation in Formation.objects.all():
        for profile in profiles:
            result = evaluate(formation, Profile(**profile))
            seen.add(result.status)
            assert not ADMISSION_PROMISE.search(message_for(result))
    assert seen == {Status.INCOMPLETE, Status.NOT_COMPATIBLE, Status.CONDITIONAL, Status.COMPATIBLE}


# ===========================================================================
# Import : formations retirées du fichier
# ===========================================================================

def test_formation_missing_from_file_is_deactivated_then_reactivated(imported):
    removed = Formation.objects.get(specialty="Licence en Batiment")
    removed.diploma_label = "Ancien libellé"      # n'existe plus dans le fichier
    removed.save()

    report = import_formations(EXCEL)
    removed.refresh_from_db()
    assert report.deactivated == 1
    assert removed.is_active is False
    assert Formation.objects.filter(is_active=True).count() == 89

    # Une formation désactivée qui revient dans le fichier redevient active.
    back = Formation.objects.get(specialty__icontains="cableur")
    back.is_active = False
    back.save()
    second = import_formations(EXCEL)
    back.refresh_from_db()
    assert back.is_active is True
    assert second.deactivated == 0


def test_import_command_reports_deactivated_count(db):
    out = StringIO()
    call_command("import_formations", stdout=out)
    assert "89 formations importées" in out.getvalue()
    assert "0 formation désactivée" in out.getvalue()


# ===========================================================================
# Les anomalies sont identifiées, pas seulement comptées
# ===========================================================================

def test_the_3_anomalies_are_the_expected_formations(imported):
    # Seuls les faits sont signalés : une contradiction dans la ligne et un doublon
    # probable. Aucune alerte sur un niveau jugé « inhabituel » (supposition).
    flagged = {
        (f.diploma_type, f.school, f.specialty)
        for f in Formation.objects.exclude(import_warnings=[])
    }
    assert flagged == {
        ("BTP", "IMSET SOUSSE", "Maintenance Micro-système Informatique"),
        ("BTS", "IMSET SOUSSE", "Décoration et design d'intérieur"),
        ("BTS", "IMSET SOUSSE", "BTS-Décoration et design d'intérieur"),
    }


# ===========================================================================
# Exemples du sujet : statuts attendus sur le vrai fichier
# ===========================================================================

def _status_counts(payload) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in post_eligibility(payload).json()["results"]:
        status = card["eligibility"]["status"]
        counts[status] = counts.get(status, 0) + 1
    return counts


def test_bac_informatique_on_it_domain(imported):
    profile = {"level": "BAC", "bac_section": "INFORMATIQUE"}
    # 28 formations contenant « informatique » ; à confirmer : la ligne contradictoire (Sousse)
    assert _status_counts({"profile": profile, "q": "informatique"}) == {
        Status.COMPATIBLE: 18, Status.CONDITIONAL: 1, Status.NOT_COMPATIBLE: 9,
    }


def test_bac_informatique_on_whole_catalog(imported):
    profile = {"level": "BAC", "bac_section": "INFORMATIQUE"}
    assert _status_counts({"profile": profile}) == {
        # À confirmer : les 3 lignes signalées (contradiction + 2 doublons probables)
        Status.COMPATIBLE: 68, Status.CONDITIONAL: 3, Status.NOT_COMPATIBLE: 18,
    }
