"""
Enregistrement d'une demande d'inscription et notification de l'équipe métier.

Appelé uniquement après le clic sur « Confirmer » (confirmation explicite).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from catalog.models import Formation

from .models import Application

logger = logging.getLogger(__name__)


class DuplicateApplication(Exception):
    """Une demande existe déjà avec cet e-mail ou ce téléphone."""


class FormationUnavailable(Exception):
    """La formation n'existe pas ou n'est plus proposée."""


def is_duplicate(email: str, phone: str) -> bool:
    """Doublon : même e-mail OU même téléphone, toutes formations confondues."""
    return Application.objects.filter(Q(email=email) | Q(phone=phone)).exists()


def submit_application(data: dict, formation_id: int) -> Application:
    """
    Enregistre la demande avec le statut « Nouvelle », puis notifie l'équipe métier.

    `data` : coordonnées déjà validées par ApplicantForm.
    Doublon = même e-mail ou même téléphone, toutes formations confondues.
    Lève FormationUnavailable ou DuplicateApplication : rien n'est alors enregistré.
    """
    formation = Formation.objects.filter(id=formation_id, is_active=True).first()
    if formation is None:
        raise FormationUnavailable
    if is_duplicate(data["email"], data["phone"]):
        raise DuplicateApplication
    try:
        with transaction.atomic():
            application = Application.objects.create(formation=formation, **data)
    except IntegrityError as exc:       # demande identique enregistrée au même moment
        raise DuplicateApplication from exc
    # Après l'enregistrement en base seulement
    transaction.on_commit(lambda: notify_team(application))
    return application


def notify_team(application: Application) -> None:
    """
    E-mail à l'équipe métier. En cas de succès, la date d'envoi est enregistrée (notified_at).
    Un échec est journalisé : la demande reste enregistrée, sans date d'envoi, et
    l'équipe la retrouve dans l'administration (filtre « équipe notifiée »).
    """
    formation = application.formation
    body = "\n".join([
        "Nouvelle demande d'inscription reçue par l'assistant.",
        "",
        f"Statut : {application.get_status_display()}",
        f"Nom : {application.last_name}",
        f"Prénom : {application.first_name}",
        f"E-mail : {application.email}",
        f"Téléphone : {application.phone}",
        f"Formation : {formation.diploma_label} – {formation.specialty}",
        f"École : {formation.school}",
        f"Date : {application.created_at:%d/%m/%Y %H:%M}",
    ])
    try:
        send_mail(
            subject=f"Nouvelle demande d'inscription – {formation.specialty} ({formation.school})",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=settings.BUSINESS_TEAM_EMAILS,
        )
    except Exception:
        logger.exception("Inscription : e-mail à l'équipe non envoyé (demande %s)", application.id)
        return
    application.notified_at = timezone.now()
    application.save(update_fields=["notified_at"])
