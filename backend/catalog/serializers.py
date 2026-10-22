"""
Sérialiseurs : transforment une Formation en JSON pour l'API.

Le format correspond aux « cartes » demandées par le sujet : diplôme,
spécialité, école et critères d'éligibilité.
"""

from rest_framework import serializers

from .models import Formation
from .normalization import BacRule, BacSection


class FormationSerializer(serializers.ModelSerializer):
    diploma = serializers.SerializerMethodField()
    criteria = serializers.SerializerMethodField()

    class Meta:
        model = Formation
        fields = ["id", "diploma", "diploma_type", "specialty", "school", "city", "criteria"]

    def get_diploma(self, obj: Formation) -> str:
        """Libellé lisible du diplôme (« Brevet de Technicien Supérieur (BTS) »)."""
        return obj.get_diploma_type_display() or obj.diploma_label

    def get_criteria(self, obj: Formation) -> dict:
        """
        Critères d'éligibilité à afficher sur la carte.
        Le niveau reprend le texte officiel de l'école (valeur d'origine) ;
        la nationalité et le bac sont traduits en français lisible.
        """
        if obj.bac_rule == BacRule.SECTIONS:
            bac = " ou ".join(BacSection.LABELS.get(code, code) for code in obj.bac_sections)
        elif obj.bac_rule == BacRule.NOT_REQUIRED:
            bac = "Bac non requis"
        else:
            bac = "Toutes sections"

        if obj.nationality_required == "TN":
            nationality = "Tunisienne"
        else:
            nationality = obj.nationality_required or "Toutes"

        return {
            "level": obj.level_raw if obj.min_level else "Aucune exigence",
            "nationality": nationality,
            "bac": bac,
        }