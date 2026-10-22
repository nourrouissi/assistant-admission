"""
Modèle des formations proposées par les écoles IMSET.

Chaque ligne du fichier Excel devient une `Formation`. On conserve à la fois :
  - les valeurs d'origine (`*_raw`, `diploma_label`) : traçabilité et affichage
    fidèle des critères officiels de l'école ;
  - les valeurs normalisées : recherche et calcul de l'éligibilité par le code.
"""

from django.db import models

from .normalization import BacRule, DiplomaType, Level


class Formation(models.Model):
    # --- Diplôme ---------------------------------------------------------------
    diploma_label = models.CharField("diplôme (libellé d'origine)", max_length=150)
    diploma_type = models.CharField(
        "type de diplôme", max_length=20, choices=DiplomaType.CHOICES,
        null=True, blank=True, db_index=True,
    )

    # --- Spécialité et école -----------------------------------------------------
    specialty_raw = models.CharField("spécialité (libellé d'origine)", max_length=255)
    specialty = models.CharField("spécialité", max_length=255)
    school = models.CharField("école", max_length=100, db_index=True)
    city = models.CharField("ville", max_length=60, blank=True)

    # --- Critère : niveau d'études ---------------------------------------------------
    level_raw = models.CharField("niveau éligible (texte d'origine)", max_length=255)
    min_level = models.CharField(
        "niveau minimal", max_length=20, choices=Level.CHOICES, null=True, blank=True,
        help_text="Vide = aucune exigence de niveau.",
    )
    level_alternatives = models.JSONField(
        "diplômes alternatifs", default=list, blank=True,
        help_text='Ex. ["CAP"] pour « 2ème année avec succès ou CAP ».',
    )
    alternatives_same_sector = models.BooleanField(
        "alternative limitée au même secteur", default=False,
        help_text="Critère non vérifiable automatiquement : à confirmer par l'équipe.",
    )

    # --- Critère : nationalité ---------------------------------------------------------
    nationality_raw = models.CharField("nationalité éligible (texte d'origine)", max_length=60)
    nationality_required = models.CharField(
        "nationalité exigée", max_length=10, null=True, blank=True,
        help_text="Code pays (ex. TN). Vide = toutes nationalités.",
    )

    # --- Critère : nature du bac ----------------------------------------------------------
    bac_raw = models.CharField("nature du bac (texte d'origine)", max_length=120)
    bac_rule = models.CharField(
        "règle sur le bac", max_length=20, choices=BacRule.CHOICES, default=BacRule.ANY,
    )
    bac_sections = models.JSONField("sections autorisées", default=list, blank=True)

    # --- Technique ------------------------------------------------------------------------
    search_text = models.TextField(
        "texte de recherche", blank=True,
        help_text="Version sans accents ni majuscules, utilisée par la recherche.",
    )
    import_warnings = models.JSONField("anomalies détectées à l'import", default=list, blank=True)
    is_active = models.BooleanField("active", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "formation"
        verbose_name_plural = "formations"
        ordering = ["school", "diploma_type", "specialty"]
        constraints = [
            # Clé « naturelle » d'une ligne de l'Excel : une formation = un diplôme,
            # une spécialité, une école. Empêche les doublons et permet un import
            # idempotent (relancer l'import met à jour au lieu de dupliquer).
            models.UniqueConstraint(
                fields=["diploma_label", "specialty_raw", "school"],
                name="unique_formation_per_school",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_diploma_type_display() or self.diploma_label} – {self.specialty} ({self.school})"