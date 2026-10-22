"""
Tests de la Partie 3 : inscription conversationnelle et notification.

Aucun appel réseau : l'agent et l'extraction des coordonnées (LLM) sont simulés.
Les garde-fous (valeurs inventées, validation, confirmation, doublons) sont, eux, testés réellement.
"""

import re
import uuid

import pytest
from django.conf import settings
from django.db import connection
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from catalog.importer import import_formations
from catalog.models import Formation
from chatbot import graph, registration_flow, tools
from chatbot.registration_flow import RegistrationMessage
from chatbot.tools import start_registration
from registrations import services
from registrations.forms import ApplicantForm
from registrations.models import Application
from registrations.services import DuplicateApplication, FormationUnavailable, submit_application

pytestmark = pytest.mark.django_db

EXCEL = settings.BASE_DIR / "data" / "diplome_specialite.xlsx"
FORBIDDEN = re.compile(r"\béligible|\binscrit\b|\badmise?s?\b|garanti", re.IGNORECASE)

VALID = {"last_name": "Ben Salah", "first_name": "Amira", "email": "Amira@Test.com", "phone": "20 123 456"}
CLEAN = {"last_name": "Ben Salah", "first_name": "Amira", "email": "amira@test.com", "phone": "+21620123456"}

# Message du prospect contenant toutes ses coordonnées, et ce que le LLM en extrait
DETAILS = "Je suis Amira Ben Salah, mon mail : Amira@Test.com, mon numéro : 20 123 456"
EXTRACTED = RegistrationMessage(intent="details", **VALID)


@pytest.fixture(autouse=True)
def imported():
    import_formations(EXCEL)


@pytest.fixture
def batiment():
    return Formation.objects.get(specialty="Licence en Batiment")


@pytest.fixture
def extractor(monkeypatch):
    """
    LLM d'extraction simulé : `replies` associe un message du prospect à ce que le LLM en comprend.
    Un message absent de `replies` est compris comme « autre chose ».
    """
    replies = {DETAILS: EXTRACTED}

    def understand(messages):
        written = messages[-1].content.split("Message du candidat : ", 1)[1]
        return replies.get(written, RegistrationMessage(intent="other"))

    monkeypatch.setattr(registration_flow, "_extractor", lambda: RunnableLambda(understand))
    return replies


def chat(session, **payload):
    response = APIClient().post("/api/chat/", {"session_id": session, **payload}, format="json")
    assert response.status_code == 200, response.content
    return response.json()["blocks"]


def block(blocks, kind):
    return next(b for b in blocks if b["type"] == kind)


def has_block(blocks, kind):
    return any(b["type"] == kind for b in blocks)


def texts(blocks):
    return " ".join(b["text"] for b in blocks if b["type"] == "text")


def new_session():
    return f"test-{uuid.uuid4()}"


def fake_agent(monkeypatch, response):
    monkeypatch.setattr(graph, "_agent_model", lambda: RunnableLambda(lambda _messages: response))


def to_summary(session, batiment):
    chat(session, action="register", formation_id=batiment.id)
    return chat(session, message=DETAILS)


# --- Validation des coordonnées par le code (I1) ------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("20 123 456", "+21620123456"),
    ("+216 20123456", "+21620123456"),
    ("+33 6 12 34 56 78", "+33612345678"),
])
def test_phone_is_normalized_to_e164(raw, expected):
    form = ApplicantForm({**VALID, "phone": raw})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["phone"] == expected
    assert form.cleaned_data["email"] == "amira@test.com"


@pytest.mark.parametrize("field, value", [
    ("email", "amira@"), ("email", "amira.test.com"),
    ("phone", "123"), ("phone", "abcdefgh"),
    ("last_name", "1234"), ("last_name", ""), ("first_name", "A"),
])
def test_invalid_values_are_rejected_on_their_field(field, value):
    form = ApplicantForm({**VALID, field: value})
    assert not form.is_valid()
    assert field in form.errors


def test_names_with_accents_hyphens_and_apostrophes_are_accepted():
    assert ApplicantForm({**VALID, "last_name": "D'Arcy-Ben Rhouma", "first_name": "Héla"}).is_valid()


# --- Garde-fou : le LLM ne peut rien inventer --------------------------------------------------------

@pytest.mark.parametrize("field, value, message, kept", [
    ("email", "amira@test.com", "mon mail est Amira@Test.com", True),
    ("email", "amira@gmail.com", "mon mail est Amira@Test.com", False),       # valeur modifiée
    ("phone", "+216 20 123 456", "mon numéro : 20 123 456", True),            # indicatif ajouté
    ("phone", "20 999 999", "mon numéro : 20 123 456", False),
    ("last_name", "Ben Salah", "je m'appelle amira ben salah", True),         # casse différente
    ("first_name", "Héla", "je suis Hela", True),                             # accent différent
    ("first_name", "Sarra", "je suis Amira", False),
])
def test_extracted_value_must_be_written_by_the_prospect(monkeypatch, field, value, message, kept):
    reply = RegistrationMessage(intent="details", **{field: value})
    monkeypatch.setattr(registration_flow, "_extractor", lambda: RunnableLambda(lambda _m: reply))
    result = registration_flow.extract_details(message, "")
    assert (getattr(result, field) == value) is kept


# --- Doublons : même e-mail OU même téléphone, toutes formations confondues (I7, R3) ------------------

def existing_application(formation, **overrides):
    return Application.objects.create(formation=formation, **{**CLEAN, **overrides})


@pytest.mark.parametrize("submitted", [
    {"email": "AMIRA@test.com", "phone": "+21698765432"},      # même e-mail (casse différente)
    {"email": "autre@test.com", "phone": "+216 20 123 456"},   # même téléphone (écriture différente)
])
def test_duplicate_email_or_phone_is_refused(batiment, submitted):
    existing_application(batiment)
    form = ApplicantForm({**VALID, **submitted})
    assert form.is_valid()            # le formulaire ne révèle pas les coordonnées déjà enregistrées
    with pytest.raises(DuplicateApplication):
        submit_application(form.cleaned_data, batiment.id)
    assert Application.objects.count() == 1


def test_duplicate_on_another_formation_is_refused(batiment):
    other = Formation.objects.exclude(id=batiment.id).first()
    existing_application(other)
    with pytest.raises(DuplicateApplication):
        submit_application(CLEAN, batiment.id)


def test_unique_constraint_catches_simultaneous_submissions(batiment, monkeypatch):
    # Le contrôle préalable ne voit rien (demande enregistrée au même moment) : la base refuse.
    existing_application(batiment)
    monkeypatch.setattr(services, "is_duplicate", lambda email, phone: False)
    with pytest.raises(DuplicateApplication):
        submit_application({**CLEAN, "phone": "+21698765432"}, batiment.id)
    assert Application.objects.count() == 1


# --- Enregistrement et notification (I6, I8, R2) ----------------------------------------------------------

def test_submit_saves_a_new_application_and_notifies_the_team(batiment, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        application = submit_application(CLEAN, batiment.id)
    assert application.status == Application.Status.NEW
    assert application.get_status_display() == "Nouvelle"
    assert len(mailoutbox) == 1
    mail = mailoutbox[0]
    assert mail.to == settings.BUSINESS_TEAM_EMAILS
    assert "Licence en Batiment" in mail.subject
    assert "amira@test.com" in mail.body and "+21620123456" in mail.body and "Statut : Nouvelle" in mail.body
    application.refresh_from_db()
    assert application.notified_at is not None


def test_email_failure_keeps_the_application(batiment, monkeypatch, django_capture_on_commit_callbacks):
    def fail(**_kwargs):
        raise ConnectionRefusedError("serveur e-mail arrêté")
    monkeypatch.setattr(services, "send_mail", fail)
    with django_capture_on_commit_callbacks(execute=True):
        submit_application(CLEAN, batiment.id)
    assert Application.objects.count() == 1
    assert Application.objects.get().notified_at is None      # visible dans l'administration


def test_admin_lists_applications_and_forbids_manual_creation(batiment, admin_client):
    submit_application(CLEAN, batiment.id)
    response = admin_client.get("/admin/registrations/application/")
    assert response.status_code == 200
    assert "Ben Salah" in response.content.decode()
    assert admin_client.get("/admin/registrations/application/add/").status_code == 403


@pytest.mark.parametrize("formation_id", [999999, "inactive"])
def test_unknown_or_inactive_formation_is_never_saved(batiment, formation_id):
    if formation_id == "inactive":
        batiment.is_active = False
        batiment.save()
        formation_id = batiment.id
    with pytest.raises(FormationUnavailable):
        submit_application(CLEAN, formation_id)
    assert not Application.objects.exists()


# --- Collecte conversationnelle des coordonnées (I1, I2) ----------------------------------------------------

def test_register_button_asks_for_the_contact_details_and_saves_nothing(batiment):
    blocks = chat(new_session(), action="register", formation_id=batiment.id)
    assert texts(blocks) == (
        "Pour votre demande d'inscription à « Licence en Batiment » (Diplome de LICENCE, IMSET SOUSSE), merci de "
        "m'indiquer votre nom, votre prénom, votre adresse e-mail et votre numéro de téléphone."
    )
    assert not Application.objects.exists()


def test_details_in_one_message_show_the_summary_with_three_buttons(batiment, extractor):
    blocks = to_summary(new_session(), batiment)
    summary = block(blocks, "registration_summary")
    assert summary["actions"] == ["confirm", "modify", "cancel"]
    assert summary["applicant"] == CLEAN
    assert summary["formation"]["id"] == batiment.id
    assert not FORBIDDEN.search(texts(blocks))
    assert not Application.objects.exists()


def test_details_given_over_several_messages(batiment, extractor):
    extractor["Amira Ben Salah"] = RegistrationMessage(intent="details", first_name="Amira", last_name="Ben Salah")
    extractor["amira@test.com et 20 123 456"] = RegistrationMessage(
        intent="details", email="amira@test.com", phone="20 123 456",
    )
    session = new_session()
    chat(session, action="register", formation_id=batiment.id)
    assert texts(chat(session, message="Amira Ben Salah")) == (
        "Merci de m'indiquer votre adresse e-mail et votre numéro de téléphone."
    )
    assert block(chat(session, message="amira@test.com et 20 123 456"), "registration_summary")["applicant"] == CLEAN


def test_invalid_value_is_asked_again_and_valid_ones_are_kept(batiment, extractor):
    extractor["Amira Ben Salah, amira@, 20 123 456"] = RegistrationMessage(
        intent="details", first_name="Amira", last_name="Ben Salah", email="amira@", phone="20 123 456",
    )
    extractor["pardon : amira@test.com"] = RegistrationMessage(intent="details", email="amira@test.com")
    session = new_session()
    chat(session, action="register", formation_id=batiment.id)
    text = texts(chat(session, message="Amira Ben Salah, amira@, 20 123 456"))
    assert text.startswith("Votre adresse e-mail n'est pas valide")
    assert text.endswith("Merci de m'indiquer votre adresse e-mail.")
    assert block(chat(session, message="pardon : amira@test.com"), "registration_summary")["applicant"] == CLEAN


def test_value_invented_by_the_llm_is_ignored_and_asked(batiment, extractor):
    extractor["Amira Ben Salah, 20 123 456"] = RegistrationMessage(
        intent="details", first_name="Amira", last_name="Ben Salah", email="amira@gmail.com", phone="20 123 456",
    )
    session = new_session()
    chat(session, action="register", formation_id=batiment.id)
    blocks = chat(session, message="Amira Ben Salah, 20 123 456")
    assert texts(blocks) == "Merci de m'indiquer votre adresse e-mail."
    assert not has_block(blocks, "registration_summary")


def test_the_agent_never_receives_the_contact_details(batiment, extractor, monkeypatch):
    session = new_session()
    to_summary(session, batiment)
    seen = []

    def agent(messages):
        seen.extend(messages)
        return AIMessage(content="Utilisez les boutons.")
    monkeypatch.setattr(graph, "_agent_model", lambda: RunnableLambda(agent))
    chat(session, message="Bonjour")
    sent = " ".join(str(message.content) for message in seen)
    assert seen and "Amira@Test.com" not in sent and "20 123 456" not in sent and "Ben Salah" not in sent


# --- Annulation ---------------------------------------------------------------------------------------------

def test_written_cancel_during_collection_saves_nothing(batiment, extractor):
    extractor["finalement j'abandonne"] = RegistrationMessage(intent="cancel")
    session = new_session()
    chat(session, action="register", formation_id=batiment.id)
    assert "aucune information n'a été enregistrée" in texts(chat(session, message="finalement j'abandonne"))
    assert texts(chat(session, action="confirm")) == "Aucune demande d'inscription n'est en cours."
    assert not Application.objects.exists()


@pytest.mark.parametrize("at_summary", [True, False])
def test_cancel_button_saves_nothing(batiment, extractor, at_summary):
    session = new_session()
    if at_summary:
        to_summary(session, batiment)
    else:
        chat(session, action="register", formation_id=batiment.id)
    assert "aucune information n'a été enregistrée" in texts(chat(session, action="cancel"))
    assert not Application.objects.exists()


# --- Récapitulatif et confirmation explicite (I3 à I6, R1, R4) ------------------------------------------------

def test_confirm_saves_notifies_and_never_promises_admission(batiment, extractor, mailoutbox, django_capture_on_commit_callbacks):
    session = new_session()
    to_summary(session, batiment)
    with django_capture_on_commit_callbacks(execute=True):
        blocks = chat(session, action="confirm")
    text = texts(blocks)
    assert Application.objects.get().status == Application.Status.NEW
    assert len(mailoutbox) == 1
    assert "a bien été prise en compte" in text and "la décision finale lui appartient" in text
    assert not FORBIDDEN.search(text)


def test_confirm_before_the_summary_saves_nothing(batiment):
    session = new_session()
    chat(session, action="register", formation_id=batiment.id)
    assert texts(chat(session, action="confirm")).startswith("Votre demande ne peut pas encore être confirmée")
    assert not Application.objects.exists()


def test_modify_asks_what_to_change_then_shows_a_new_summary(batiment, extractor):
    extractor["mon nouveau mail : nouvelle@test.com"] = RegistrationMessage(intent="details", email="nouvelle@test.com")
    session = new_session()
    to_summary(session, batiment)
    assert texts(chat(session, action="modify")) == registration_flow.MODIFY_TEXT
    summary = block(chat(session, message="mon nouveau mail : nouvelle@test.com"), "registration_summary")
    assert summary["applicant"] == {**CLEAN, "email": "nouvelle@test.com"}
    assert not Application.objects.exists()


def test_written_yes_never_confirms(batiment, extractor, monkeypatch):
    session = new_session()
    to_summary(session, batiment)
    fake_agent(monkeypatch, AIMessage(content="Pour confirmer votre demande, utilisez le bouton Confirmer."))
    blocks = chat(session, message="oui je confirme")
    assert not Application.objects.exists()
    assert block(blocks, "registration_summary")["applicant"] == CLEAN       # récapitulatif réaffiché


def test_action_without_pending_registration():
    assert texts(chat(new_session(), action="confirm")) == "Aucune demande d'inscription n'est en cours."


def test_duplicate_is_not_revealed_during_collection(batiment, extractor):
    existing_application(Formation.objects.exclude(id=batiment.id).first())   # autre formation : doublon aussi
    session = new_session()
    chat(session, action="register", formation_id=batiment.id)
    blocks = chat(session, message=DETAILS)
    assert block(blocks, "registration_summary")["applicant"] == CLEAN        # récapitulatif, sans alerte
    assert "existe déjà" not in texts(blocks)
    text = texts(chat(session, action="confirm"))                             # refus au clic seulement
    assert text.startswith("Une demande existe déjà avec cet e-mail ou ce numéro de téléphone")
    assert Application.objects.count() == 1


def test_duplicate_detected_at_confirmation(batiment, extractor):
    session = new_session()
    to_summary(session, batiment)
    existing_application(Formation.objects.exclude(id=batiment.id).first())   # enregistrée entre-temps
    text = texts(chat(session, action="confirm"))
    assert text.startswith("Une demande existe déjà avec cet e-mail ou ce numéro de téléphone")
    assert Application.objects.count() == 1


def test_formation_deactivated_before_confirmation(batiment, extractor):
    session = new_session()
    to_summary(session, batiment)
    Formation.objects.filter(id=batiment.id).update(is_active=False)
    assert texts(chat(session, action="confirm")).startswith("Cette formation n'est plus proposée")
    assert not Application.objects.exists()


# --- Scénario H : question libre pendant l'inscription --------------------------------------------------------

def agent_asking_procedure(monkeypatch):
    fake_agent(monkeypatch, AIMessage(content="", tool_calls=[
        {"name": "search_procedure", "args": {"question": "Quels documents fournir ?"}, "id": "call-1"},
    ]))
    monkeypatch.setattr(tools, "answer_procedure_question", lambda question: {"answer": "Réponse sur les documents."})


def test_question_during_collection_is_answered_then_missing_details_are_asked(batiment, extractor, monkeypatch):
    extractor["Amira Ben Salah"] = RegistrationMessage(intent="details", first_name="Amira", last_name="Ben Salah")
    session = new_session()
    chat(session, action="register", formation_id=batiment.id)
    chat(session, message="Amira Ben Salah")
    agent_asking_procedure(monkeypatch)
    blocks = chat(session, message="Quels documents dois-je fournir ?")
    assert blocks[0] == {"type": "text", "text": "Réponse sur les documents."}
    assert blocks[1]["text"] == "Merci de m'indiquer votre adresse e-mail et votre numéro de téléphone."


def test_question_during_the_summary_keeps_data_and_confirmation_still_works(batiment, extractor, monkeypatch):
    session = new_session()
    to_summary(session, batiment)
    agent_asking_procedure(monkeypatch)
    blocks = chat(session, message="Quels documents dois-je fournir ?")
    assert blocks[0]["text"] == "Réponse sur les documents."
    assert block(blocks, "registration_summary")["applicant"] == CLEAN
    chat(session, action="confirm")
    assert Application.objects.get().email == "amira@test.com"


def test_extraction_failure_keeps_the_registration(batiment, extractor, monkeypatch):
    session = new_session()
    chat(session, action="register", formation_id=batiment.id)

    def down(_messages):
        raise ConnectionError("quota dépassé")
    monkeypatch.setattr(registration_flow, "_extractor", lambda: RunnableLambda(down))
    assert texts(chat(session, message=DETAILS)).startswith("Je n'ai pas pu traiter votre message")
    monkeypatch.setattr(registration_flow, "_extractor", lambda: RunnableLambda(lambda _m: EXTRACTED))
    assert block(chat(session, message=DETAILS), "registration_summary")["applicant"] == CLEAN


# --- Identification de la formation par la conversation (I2, I3, R2) -------------------------------------------

def start(**args):
    command = start_registration.func(tool_call_id="call-1", **args)
    message = command.update["messages"][0]
    return command.update, message.artifact


def test_single_formation_starts_the_collection(batiment):
    update, blocks = start(keywords="batiment")
    assert update["registration"] == {"formation_id": batiment.id, "stage": "collect", "values": {}, "errors": {}}
    assert blocks == []


def test_several_formations_are_shown_to_choose():
    update, blocks = start(keywords="informatique gestion", diploma_type="BTS")
    assert "registration" not in update
    assert len(block(blocks, "formations")["items"]) > 1


def test_decoration_at_sousse_shows_both_formations():
    _update, blocks = start(keywords="decoration", diploma_type="BTS", school="Sousse")
    specialties = {card["specialty"] for card in block(blocks, "formations")["items"]}
    assert specialties == {"Décoration et design d'intérieur", "BTS-Décoration et design d'intérieur"}


def test_unknown_formation_is_not_registered():
    update, blocks = start(keywords="médecine", diploma_type="LICENCE")
    assert "registration" not in update
    assert texts(blocks).startswith("Je n'ai trouvé aucune formation")


def test_no_formation_given_asks_which_one():
    _update, blocks = start()
    assert texts(blocks).startswith("À quelle formation souhaitez-vous vous inscrire ?")


# L'outil s'exécute dans un autre thread (LangGraph) : données réellement enregistrées (transaction=True)
@pytest.mark.django_db(transaction=True)
def test_written_registration_request_asks_for_the_contact_details(batiment, monkeypatch):
    fake_agent(monkeypatch, AIMessage(content="", tool_calls=[
        {"name": "start_registration", "args": {"keywords": "batiment"}, "id": "call-1"},
    ]))
    blocks = chat(new_session(), message="Je veux m'inscrire à la licence en bâtiment")
    assert texts(blocks).startswith("Pour votre demande d'inscription à « Licence en Batiment »")


# --- Limite de requêtes et mémoire des conversations ------------------------------------------------------

def test_too_many_requests_are_refused(monkeypatch):
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "chat", "2/min")
    client, session = APIClient(), new_session()
    statuses = [client.post("/api/chat/", {"session_id": session, "action": "confirm"}, format="json").status_code
                for _ in range(3)]
    assert statuses == [200, 200, 429]


def test_conversations_survive_a_restart_with_postgres(batiment, extractor, settings):
    """Mémoire PostgreSQL : un nouveau graphe (redémarrage du serveur) retrouve l'inscription en cours."""
    from chatbot.memory import conninfo

    settings.CHAT_MEMORY = "postgres"
    session = new_session()
    try:
        graph.get_graph.cache_clear()
        to_summary(session, batiment)
        graph.get_graph().checkpointer.conn.close()       # « redémarrage » : nouvelles connexions
        graph.get_graph.cache_clear()
        assert block(chat(session, action="modify"), "text")["text"] == registration_flow.MODIFY_TEXT
    finally:
        saver = graph.get_graph().checkpointer
        saver.delete_thread(session)
        saver.conn.close()
        graph.get_graph.cache_clear()
    assert connection.settings_dict["NAME"] in conninfo()          # base de test, jamais la vraie base


# --- Informations pour l'interface : étape en cours et issue de l'inscription ----------------------------------

def chat_response(session, **payload):
    response = APIClient().post("/api/chat/", {"session_id": session, **payload}, format="json")
    assert response.status_code == 200, response.content
    return response.json()


def test_response_gives_the_registration_stage(batiment, extractor):
    session = new_session()
    assert chat_response(session, action="confirm")["registration"] is None
    assert chat_response(session, action="register", formation_id=batiment.id)["registration"] == "collect"
    assert chat_response(session, message=DETAILS)["registration"] == "summary"
    assert chat_response(session, action="modify")["registration"] == "collect"
    assert chat_response(session, action="cancel")["registration"] is None


def test_confirmation_gives_a_created_result_with_the_new_status(batiment, extractor):
    session = new_session()
    to_summary(session, batiment)
    response = chat_response(session, action="confirm")
    result = block(response["blocks"], "registration_result")
    assert result["outcome"] == "created"
    assert result["status"] == "Nouvelle"
    assert result["formation"]["id"] == batiment.id
    assert response["registration"] is None


@pytest.mark.parametrize("ending, outcome", [("duplicate", "duplicate"), ("cancel", "cancelled"), ("inactive", "unavailable")])
def test_other_endings_give_their_result_and_save_nothing_new(batiment, extractor, ending, outcome):
    session = new_session()
    to_summary(session, batiment)
    if ending == "duplicate":
        existing_application(Formation.objects.exclude(id=batiment.id).first())
    if ending == "inactive":
        Formation.objects.filter(id=batiment.id).update(is_active=False)
    blocks = chat(session, action="cancel" if ending == "cancel" else "confirm")
    result = block(blocks, "registration_result")
    assert result == {"type": "registration_result", "outcome": outcome}
    assert Application.objects.count() == (1 if ending == "duplicate" else 0)
