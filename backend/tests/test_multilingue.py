"""
Assistant multilingue : français (par défaut, inchangé), anglais, arabe.

Les tests existants vérifient le français sans le préciser : la langue par défaut.
Ici : les traductions sont complètes et cohérentes, et chaque langue arrive jusqu'aux
outils, au parcours d'inscription, au moteur d'éligibilité et aux instructions des modèles.
Aucun appel réseau : les modèles de langage sont simulés.
"""

import re
import string
import uuid

import pytest
from django.conf import settings
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from rest_framework.test import APIClient

from catalog.eligibility import Profile, evaluate, message_for
from catalog.importer import import_formations
from catalog.models import Formation
from catalog.normalization import normalize_nationality
from catalog.serializers import FormationSerializer
from catalog.services import search_catalog
from chatbot import graph, registration_flow
from chatbot.registration_flow import RegistrationMessage, validate
from config import i18n
from config.i18n import tr, use_language
from knowledge import rag

pytestmark = pytest.mark.django_db

EXCEL = settings.BASE_DIR / "data" / "diplome_specialite.xlsx"
ARABIC = re.compile(r"[؀-ۿ]")


@pytest.fixture(autouse=True)
def imported():
    import_formations(EXCEL)


@pytest.fixture
def batiment():
    return Formation.objects.get(specialty="Licence en Batiment")


def chat(session, **payload):
    response = APIClient().post("/api/chat/", {"session_id": session, **payload}, format="json")
    assert response.status_code == 200, response.content
    return response.json()["blocks"]


def texts(blocks):
    return " ".join(b["text"] for b in blocks if b["type"] == "text")


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


# --- Les traductions --------------------------------------------------------------------------

def test_french_is_returned_unchanged_and_is_the_default():
    assert i18n.current_language() == "fr"
    assert tr(registration_flow.MODIFY_TEXT) == registration_flow.MODIFY_TEXT


def test_every_text_is_translated_in_english_and_arabic_with_the_same_placeholders():
    for french, translations in i18n._catalog.items():
        assert set(translations) == {"en", "ar"}, french
        for language, text in translations.items():
            # Mêmes valeurs à insérer ; seul l'accord du pluriel français ({plural}) peut manquer
            assert placeholders(text) <= placeholders(french), (language, french)
            assert placeholders(french) - {"plural"} <= placeholders(text), (language, french)
        assert ARABIC.search(translations["ar"]), french


def test_every_catalog_value_is_translated():
    """Chaque diplôme, spécialité et critère du fichier des écoles a sa traduction (« All » excepté)."""
    values = set()
    for formation in Formation.objects.all():
        values |= {formation.diploma_label, formation.specialty, formation.level_raw,
                   formation.nationality_raw, formation.bac_raw}
    missing = sorted(v for v in values - {"All"} if v not in i18n._catalog)
    assert missing == []


def test_formation_card_is_unchanged_in_french(batiment):
    card = FormationSerializer(batiment).data
    assert card["specialty"] == "Licence en Batiment"
    assert card["diploma"] == batiment.diploma_label
    assert card["criteria"]["nationality"] == "Tunisienne"


@pytest.mark.parametrize("lang, specialty, nationality", [
    ("en", "Bachelor in building and construction", "Tunisian"),
    ("ar", "إجازة في البناء", "تونسية"),
])
def test_formation_card_is_translated(batiment, lang, specialty, nationality):
    with use_language(lang):
        card = FormationSerializer(batiment).data
    assert card["specialty"] == specialty
    assert card["criteria"]["nationality"] == nationality
    assert card["school"] == batiment.school          # nom propre, jamais traduit


def test_catalog_api_stays_in_french(batiment):
    response = APIClient().get("/api/formations/", {"q": "batiment"})
    assert response.status_code == 200
    assert "Licence en Batiment" in response.content.decode()


# --- Recherche et nationalité : le prospect écrit dans sa langue -----------------------------------

def test_arabic_search_also_understands_english_and_mixed_words():
    with use_language("ar"):
        found = search_catalog("développement web", school="Nabeul", diploma_type="BTS").formations
    assert [f.specialty for f in found] == ["Développement sur Internet"]


@pytest.mark.parametrize("lang, query", [("en", "building construction"), ("ar", "البناء")])
def test_search_finds_the_translated_name(batiment, lang, query):
    with use_language(lang):
        result = search_catalog(query)
    assert batiment in result.formations
    assert result.unmatched_terms == []


@pytest.mark.parametrize("school", ["نابل", "سوسة", "سوسه"])
def test_school_city_written_in_arabic(school):
    with use_language("ar"):
        found = search_catalog("", school=school, diploma_type="BTS").formations
    assert found.exists()
    assert {f.city for f in found} <= {"Nabeul", "Sousse"}


def test_bachelor_in_english_includes_the_licence(batiment):
    with use_language("en"):
        found = search_catalog("building", school="Sousse", diploma_type="BACHELOR").formations
    assert list(found) == [batiment]
    assert not search_catalog("batiment", diploma_type="BACHELOR").formations.exists()   # français inchangé


def test_french_search_ignores_translations(batiment):
    result = search_catalog("construction")
    assert not result.formations.exists()
    assert result.unmatched_terms == ["construction"]


@pytest.mark.parametrize("value", ["تونسية", "تونسي", "Tunisian"])
def test_tunisian_nationality_in_arabic_and_english(value):
    assert normalize_nationality(value) == "TN"


def test_other_nationality_in_arabic_is_understood_and_not_tunisian():
    assert normalize_nationality("جزائري") != "TN"


def test_unknown_language_falls_back_to_french():
    with use_language("de"):
        assert i18n.current_language() == "fr"


# --- Jusqu'au prospect, par l'API ------------------------------------------------------------------

@pytest.mark.parametrize("lang, expected", [
    ("fr", "Pour votre demande d'inscription à « Licence en Batiment »"),
    ("en", "For your application to “Bachelor in building and construction”"),
    ("ar", "لطلب التسجيل في «إجازة في البناء»"),
])
def test_registration_question_in_the_chosen_language(batiment, lang, expected):
    blocks = chat(f"t-{uuid.uuid4()}", action="register", formation_id=batiment.id, lang=lang)
    assert texts(blocks).startswith(expected)


def test_language_is_optional_and_french_by_default(batiment):
    blocks = chat(f"t-{uuid.uuid4()}", action="register", formation_id=batiment.id)
    assert texts(blocks).startswith("Pour votre demande d'inscription")


def test_unknown_language_is_refused_by_the_api():
    response = APIClient().post("/api/chat/", {"message": "hello", "lang": "de"}, format="json")
    assert response.status_code == 400


# Les outils s'exécutent dans un autre thread (LangGraph) : données réellement enregistrées
# (transaction=True). Ce test vérifie aussi que la langue arrive jusqu'à ce thread.
@pytest.mark.django_db(transaction=True)
def test_language_reaches_the_tools_run_by_the_graph(monkeypatch):
    call = AIMessage(content="", tool_calls=[{"name": "search_formations", "args": {"keywords": "informatique"}, "id": "1"}])
    answers = iter([call, AIMessage(content="")])
    monkeypatch.setattr(graph, "_agent_model", lambda: RunnableLambda(lambda _messages: next(answers)))
    blocks = chat(f"t-{uuid.uuid4()}", message="Which computer science programs do you offer?", lang="en")
    assert texts(blocks).startswith("Here are the programs matching your request (28).")


def test_whole_registration_in_english_until_confirmation(monkeypatch, batiment):
    message = "I am Sara Haddad, sara@test.com, 20 123 456"
    extracted = RegistrationMessage(intent="details", last_name="Haddad", first_name="Sara",
                                    email="sara@test.com", phone="20 123 456")
    monkeypatch.setattr(registration_flow, "_extractor", lambda: RunnableLambda(lambda _m: extracted))
    session = f"t-{uuid.uuid4()}"
    chat(session, action="register", formation_id=batiment.id, lang="en")
    summary = chat(session, message=message, lang="en")
    assert texts(summary).startswith("Here is the summary of your application.")
    confirmed = chat(session, action="confirm", lang="en")
    assert "has been received, with the status “New”" in texts(confirmed)
    assert "the final decision rests with them" in texts(confirmed)


def test_validation_errors_in_arabic():
    with use_language("ar"):
        _cleaned, errors = validate({"last_name": "Haddad", "first_name": "Sara", "email": "sara@", "phone": "12"})
    assert errors["phone"] == ["رقم هاتف غير صالح."]
    assert ARABIC.search(errors["email"][0])


def test_validation_errors_unchanged_in_french():
    _cleaned, errors = validate({"last_name": "Haddad", "first_name": "Sara", "email": "sara@", "phone": "12"})
    assert errors == {"email": ["Saisissez une adresse e-mail valide."], "phone": ["Numéro de téléphone invalide."]}


# --- Moteur d'éligibilité : motifs et critères officiels traduits ----------------------------------

def test_eligibility_reason_in_english_translates_the_official_criterion(batiment):
    with use_language("en"):
        result = evaluate(batiment, Profile(level="BAC_PLUS_2", nationality="FR"))
        message = message_for(result)
    assert result.reasons == ["required nationality: Tunisian"]
    assert message == "Based on the information provided, this criterion is not met: required nationality: Tunisian."


def test_eligibility_message_unchanged_in_french(batiment):
    result = evaluate(batiment, Profile(level="BAC_PLUS_2", nationality="FR"))
    assert message_for(result) == (
        "D'après les informations indiquées, ce critère n'est pas rempli : nationalité requise : Tunisienne."
    )


# --- Instructions des modèles : inchangées en français -------------------------------------------------

def test_model_instructions_are_unchanged_in_french():
    assert graph._system_prompt({"registration": None}) == graph.AGENT_PROMPT
    assert rag._system_prompt() == rag.SYSTEM_PROMPT


@pytest.mark.parametrize("lang, name", [("en", "anglais"), ("ar", "arabe")])
def test_model_instructions_ask_for_the_chosen_language(lang, name):
    with use_language(lang):
        agent_prompt = graph._system_prompt({"registration": None})
        rag_prompt = rag._system_prompt()
    assert f"Rédige toutes tes réponses en {name}" in agent_prompt
    assert "Les arguments des outils restent en français" in agent_prompt
    assert f"Rédige toutes tes réponses en {name}" in rag_prompt
    assert "Réponds en français" not in rag_prompt


# --- RAG : la réponse est vérifiée dans la langue du candidat -------------------------------------------

@pytest.mark.parametrize("lang, answer, expected", [
    ("ar", "يتكون ملف الترشيح من الوثائق التالية: نسخة من الشهادة. admissions@example.test", True),
    ("ar", "يتكون ملف الترشيح من شهادة BTS في IMSET SOUSSE.", True),
    ("ar", "Voici les étapes de la procédure d'admission : choix de la formation, préinscription.", False),
    ("en", "Here are the steps of the admission procedure.", True),
    ("en", "Voici les étapes : vous choisissez une formation selon votre profil.", False),
    ("fr", "Voici les étapes de la procédure.", True),
])
def test_answer_language_check(lang, answer, expected):
    with use_language(lang):
        assert rag.written_in_language(answer) is expected


def test_rag_answer_schema_unchanged_in_french():
    assert rag.ProcedureAnswer.model_fields["answer"].description == "Réponse au candidat, en français."
    assert "Réponds entièrement" not in rag._user_message("Question ?", [])


# --- Le prospect est servi dans la langue de son message -------------------------------------------------

@pytest.mark.parametrize("message, interface, expected", [
    ("Quels documents dois-je fournir pour déposer une candidature ?", "en", "fr"),
    ("Which documents do I need to provide?", "fr", "en"),
    ("ما هي الوثائق التي يجب تقديمها؟", "fr", "ar"),
    ("عندي BTS وجنسيتي فرنسية.", "en", "ar"),
    ("oui je confirme", "ar", "fr"),
    ("Am I sure to be admitted?", "fr", "en"),
    # Messages neutres : la langue de l'interface (de la conversation) est gardée
    ("Yasmine Trabelsi, yasmine@exemple.tn, 22 345 678", "ar", "ar"),
    ("Trabelsi", "en", "en"),
    ("ok", "fr", "fr"),
])
def test_detect_language(message, interface, expected):
    assert i18n.detect_language(message, interface) == expected


def test_reply_follows_the_language_of_the_message(monkeypatch):
    """Interface en français, message en arabe : réponse en arabe, et l'interface est invitée à suivre."""
    from chatbot import views
    monkeypatch.setattr(views, "reply", lambda _session, _message: [{"type": "text", "text": i18n.current_language()}])
    data = chat_response({"message": "ما هي الوثائق المطلوبة؟"})
    assert data["blocks"][0]["text"] == "ar" and data["lang"] == "ar"
    data = chat_response({"message": "Which documents do I need to provide?", "lang": "ar"})
    assert data["blocks"][0]["text"] == "en" and data["lang"] == "en"
    data = chat_response({"message": "Quels documents dois-je fournir ?", "lang": "en"})
    assert data["blocks"][0]["text"] == "fr" and data["lang"] == "fr"


def chat_response(payload):
    response = APIClient().post("/api/chat/", {"session_id": f"t-{uuid.uuid4()}", **payload}, format="json")
    assert response.status_code == 200, response.content
    return response.json()


def test_french_response_has_no_language_field(batiment):
    response = APIClient().post("/api/chat/", {"action": "register", "formation_id": batiment.id}, format="json")
    assert "lang" not in response.json()
