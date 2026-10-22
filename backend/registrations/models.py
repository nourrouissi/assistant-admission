"""
Demandes d'inscription des prospects.

Sujet : enregistrer la demande avec le statut « Nouvelle », en vérifiant les
doublons sur l'e-mail et le téléphone. Un e-mail ou un téléphone ne peut
figurer que dans une seule demande, toutes formations confondues : contraintes
d'unicité en base (e-mail en minuscules, téléphone au format E.164).
"""

from django.db import models

from catalog.models import Formation


class Application(models.Model):
    class Status(models.TextChoices):
        NEW = "NOUVELLE", "Nouvelle"

    last_name = models.CharField("nom", max_length=60)
    first_name = models.CharField("prénom", max_length=60)
    email = models.EmailField("e-mail", unique=True)
    phone = models.CharField("téléphone (E.164)", max_length=16, unique=True)
    formation = models.ForeignKey(
        Formation, verbose_name="formation", on_delete=models.PROTECT, related_name="applications"
    )
    status = models.CharField("statut", max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField("créée le", auto_now_add=True)
    notified_at = models.DateTimeField(
        "équipe notifiée le", null=True, blank=True,
        help_text="Vide = l'e-mail à l'équipe n'a pas pu être envoyé.",
    )

    class Meta:
        verbose_name = "demande d'inscription"
        verbose_name_plural = "demandes d'inscription"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} – {self.formation}"
