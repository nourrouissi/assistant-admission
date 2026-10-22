"""Tests unitaires de la normalisation : aucun accès à la base, exécution instantanée."""

import pytest

from catalog.normalization import (
    BacRule,
    BacSection,
    DiplomaType,
    Level,
    clean_specialty,
    consistency_warnings,
    fold,
    normalize_diploma_type,
    parse_bac_rule,
    parse_level_requirement,
    parse_nationality,
)


def test_fold_removes_accents_case_and_extra_spaces():
    assert fold("  Mathèmatique  Générale ") == "mathematique generale"


@pytest.mark.parametrize("label, expected", [
    ("Brevet de Technicien Professionnel", DiplomaType.BTP),
    ("Brevet de Technicien Supérieur", DiplomaType.BTS),
    ("Diplome de LICENCE", DiplomaType.LICENCE),
    ("Licence", DiplomaType.LICENCE),
    ("Licence Professionnelle", DiplomaType.LICENCE_PRO),
    ("INGENIEUR CNAM", DiplomaType.INGENIEUR),
    ("Ingénieur", DiplomaType.INGENIEUR),
    ("SHORT COURSES", DiplomaType.SHORT_COURSE),
    ("Certificat d'Aptitude Professionnelle", DiplomaType.CAP),
    ("Concepteur en architecture informatique", DiplomaType.TITRE_RNCP),
    ("Bachelor", DiplomaType.BACHELOR),
])
def test_diploma_labels_are_normalized(label, expected):
    assert normalize_diploma_type(label) == expected


@pytest.mark.parametrize("raw, min_level, alternatives, same_sector", [
    ("2ème avec succés ou CAP dans le même secteur", Level.DEUXIEME_SEC, [Level.CAP], True),
    ("bac ou BTP dans le même secteur", Level.BAC, [Level.BTP], True),
    ("Bac+2 / BTS", Level.BAC_PLUS_2, [], False),
    ("Bac+ 2/ BTS", Level.BAC_PLUS_2, [], False),  # variante d'écriture
    ("Licence +1 année d'approfondissement", Level.LICENCE_PLUS_1, [], False),
    ("Licence+1 année d'approfondissement", Level.LICENCE_PLUS_1, [], False),
    ("Licence ou équivalent", Level.LICENCE, [], False),
    ("4ème année secondaire", Level.QUATRIEME_SEC, [], False),
    ("2ème année secondaire  avec succés", Level.DEUXIEME_SEC, [], False),
    ("9ème année accomplie", Level.NEUVIEME, [], False),
    ("All", None, [], False),
])
def test_level_requirements_are_parsed(raw, min_level, alternatives, same_sector):
    req = parse_level_requirement(raw)
    assert req.parsed
    assert req.min_level == min_level
    assert req.alternatives == alternatives
    assert req.alternatives_same_sector is same_sector


def test_unknown_level_is_flagged_not_guessed():
    assert parse_level_requirement("niveau mystère").parsed is False


@pytest.mark.parametrize("raw, rule, sections", [
    ("All", BacRule.ANY, []),
    ("san bac", BacRule.NOT_REQUIRED, []),  # faute de frappe du fichier
    ("sans bac", BacRule.NOT_REQUIRED, []),
    (" Sciences expérimentales ou Mathèmatique", BacRule.SECTIONS, [BacSection.MATH, BacSection.SCIENCES_EXP]),
])
def test_bac_rules_are_parsed(raw, rule, sections):
    assert parse_bac_rule(raw) == (rule, sections)


def test_nationality():
    assert parse_nationality("All") is None
    assert parse_nationality("Tunisienne") == "TN"


def test_specialty_prefix_and_spacing_are_cleaned():
    assert clean_specialty("BTS-Comptabilité et Finances") == "Comptabilité et Finances"
    assert clean_specialty("BTS_Bioanalyses et Controles") == "Bioanalyses et Controles"
    assert clean_specialty("Réseaux et Sécurité Informatiques(cours du soir)") == "Réseaux et Sécurité Informatiques (cours du soir)"


def test_inconsistent_rows_are_reported():
    # BTS demandant seulement la 2ème année : incohérence repérée à IMSET Sousse
    low = parse_level_requirement("2ème avec succés ou CAP dans le même secteur")
    assert consistency_warnings(DiplomaType.BTS, low, BacRule.ANY)
    # « sans bac » alors que le bac est requis
    bac = parse_level_requirement("bac ou BTP dans le même secteur")
    assert consistency_warnings(DiplomaType.BTP, bac, BacRule.NOT_REQUIRED)
    # Ligne cohérente : aucune alerte
    assert consistency_warnings(DiplomaType.BTS, bac, BacRule.ANY) == []
