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


def test_import_reports_the_3_known_anomalies(imported):
    # 1 contradiction (« san bac » avec un niveau « bac ») + 1 message « Doublon
    # probable » sur chacune des 2 lignes « Décoration et design d'intérieur » (BTS, Sousse).
    assert len(imported.warnings) == 3


def test_search_is_accent_and_case_insensitive(imported):
    assert count(q="Sécurité") == count(q="securite") > 0


def test_keyword_matches_the_start_of_a_word(imported):
    # « info » trouve « informatique » et « infographie » ; aucun synonyme ajouté
    assert count(q="informatique") == 28
    assert count(q="info") == 29


def test_school_filter_accepts_city_name(imported):
    assert count(school="Sousse") == 28


def test_same_specialty_exists_in_several_schools(imported):
    # Cas « choix ambigu » de la Partie 3 : il faudra demander l'école au prospect.
    data = APIClient().get("/api/formations/", {"q": "reseaux securite", "diploma_type": "BTS"}).json()
    assert len({item["school"] for item in data["results"]}) == 4


def test_unknown_word_does_not_block_known_words(imported):
    # « cuisine » n'existe pas dans le catalogue : il est retiré, « informatique » reste
    assert count(q="informatique cuisine") == count(q="informatique")


def test_card_contains_official_criteria(imported):
    card = APIClient().get("/api/formations/", {"q": "batiment"}).json()["results"][0]
    # La carte affiche le libellé officiel du fichier, sans rien ajouter ni retirer.
    assert card["diploma"] == "Diplome de LICENCE"
    assert card["school"] == "IMSET SOUSSE"
    assert card["criteria"] == {"level": "Bac+ 2/ BTS", "nationality": "Tunisienne", "bac": "All"}


def test_api_is_read_only(imported):
    assert APIClient().post("/api/formations/", {}).status_code == 405


def test_health_endpoint():
    assert APIClient().get("/api/health/").json() == {"status": "ok"}
