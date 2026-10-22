"""Tests d'intégration : import du vrai fichier Excel, puis appels de l'API."""

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from catalog.importer import import_formations
from catalog.models import Formation

pytestmark = pytest.mark.django_db  # ces tests utilisent une base de test temporaire

EXCEL = settings.BASE_DIR / "data" / "diplome_specialite.xlsx"


@pytest.fixture
def imported():
    """Importe le fichier Excel réel avant chaque test."""
    return import_formations(EXCEL)


def count(**params) -> int:
    return APIClient().get("/api/formations/", params).json()["count"]


def test_import_loads_all_89_rows(imported):
    assert imported.created == 89
    assert Formation.objects.count() == 89
    assert not Formation.objects.filter(diploma_type__isnull=True).exists()


def test_import_is_idempotent(imported):
    second = import_formations(EXCEL)
    assert (second.created, second.updated) == (0, 89)
    assert Formation.objects.count() == 89


def test_import_reports_the_6_known_anomalies(imported):
    assert len(imported.warnings) == 6


def test_search_is_accent_and_case_insensitive(imported):
    assert count(q="Sécurité") == count(q="securite") > 0


def test_abbreviation_is_understood(imported):
    assert count(q="info") == count(q="informatique") == 28


def test_school_filter_accepts_city_name(imported):
    assert count(school="Sousse") == 28


def test_same_specialty_exists_in_several_schools(imported):
    # Cas « choix ambigu » de la Partie 3 : il faudra demander l'école au prospect.
    data = APIClient().get("/api/formations/", {"q": "reseaux securite", "diploma_type": "BTS"}).json()
    assert len({item["school"] for item in data["results"]}) == 4


def test_unknown_words_fall_back_to_partial_matches(imported):
    # « dès que possible » : une recherche à plusieurs mots ne renvoie pas un résultat vide
    assert count(q="informatique cuisine") > 0


def test_card_contains_official_criteria(imported):
    card = APIClient().get("/api/formations/", {"q": "batiment"}).json()["results"][0]
    assert card["diploma"] == "Licence"
    assert card["school"] == "IMSET SOUSSE"
    assert card["criteria"] == {"level": "Bac+ 2/ BTS", "nationality": "Tunisienne", "bac": "Toutes sections"}


def test_api_is_read_only(imported):
    assert APIClient().post("/api/formations/", {}).status_code == 405


def test_health_endpoint():
    assert APIClient().get("/api/health/").json() == {"status": "ok"}
