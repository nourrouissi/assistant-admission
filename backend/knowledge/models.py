"""
Extraits du document « Procédure d'admission », stockés avec leur vecteur.

Un extrait = une section numérotée du document (titre + contenu complet).
"""

from django.db import models
from pgvector.django import VectorField

# Dimension des vecteurs du modèle multilingual-e5-small
EMBEDDING_DIMENSIONS = 384


class ProcedureChunk(models.Model):
    section_number = models.PositiveSmallIntegerField("numéro de section", unique=True)
    title = models.CharField("titre", max_length=255)
    content = models.TextField("contenu")
    embedding = VectorField("vecteur", dimensions=EMBEDDING_DIMENSIONS)

    class Meta:
        verbose_name = "extrait de la procédure"
        verbose_name_plural = "extraits de la procédure"
        ordering = ["section_number"]

    def __str__(self) -> str:
        return f"{self.section_number}. {self.title}"
