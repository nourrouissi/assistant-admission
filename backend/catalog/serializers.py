"""
Sérialiseurs : transforment les données en JSON (et valident le JSON reçu).

- FormationSerializer : une formation au format « carte » demandé par le sujet
  (diplôme, spécialité, école, critères d'éligibilité).
- SearchParamsSerializer : valide les filtres de la recherche (GET).
- ProfileSerializer / EligibilityRequestSerializer : valident le profil envoyé
  pour une vérification d'éligibilité.
"""

from rest_framework import serializers

from config.i18n import tr

from .models import Formation
from .normalization import BacSection, Level, normalize_nationality, parse_diploma_type_code

# Nombre maximal de formations évaluées en une demande (protection de l'API)
MAX_EVALUATED = 100


class FormationSerializer(serializers.ModelSerializer):
    diploma = serializers.SerializerMethodField()
    criteria = serializers.SerializerMethodField()
    criteria_under_review = serializers.SerializerMethodField()

    class Meta:
        model = Formation
        fields = ["id", "diploma", "diploma_type", "specialty", "school", "city", "criteria", "criteria_under_review"]

    def to_representation(self, instance: Formation) -> dict:
        """En anglais ou en arabe, la spécialité est affichée traduite (en français : inchangée)."""
        data = super().to_representation(instance)
        data["specialty"] = tr(data["specialty"])
        return data

    def get_diploma(self, obj: Formation) -> str:
        """
        Libellé officiel du diplôme, tel qu'il figure dans le fichier (« INGENIEUR CNAM »),
        sans rien ajouter ni retirer. Le type normalisé reste disponible dans `diploma_type`.
        En anglais ou en arabe, sa traduction (catalog/translations.py).
        """
        return tr(obj.diploma_label)

    def get_criteria(self, obj: Formation) -> dict:
        """
        Critères d'éligibilité à afficher sur la carte : le texte du fichier, tel quel
        (seuls les espaces en trop sont retirés à l'import). Aucune reformulation.
        En anglais ou en arabe, leur traduction.
        """
        return {
            "level": tr(obj.level_raw),
            "nationality": tr(obj.nationality_raw),
            "bac": tr(obj.bac_raw),
        }

    def get_criteria_under_review(self, obj: Formation) -> bool:
        """Vrai si l'import a signalé une anomalie : critères à confirmer par l'équipe."""
        return bool(obj.import_warnings)


def clean_diploma_type(value: str) -> str:
    """« bts » ou « BTS » -> "BTS" ; code inconnu -> erreur 400 avec les valeurs possibles."""
    if not value:
        return ""
    try:
        return parse_diploma_type_code(value)
    except ValueError as exc:
        raise serializers.ValidationError(str(exc)) from exc


class SearchParamsSerializer(serializers.Serializer):
    """Filtres de la recherche (paramètres de l'URL). Tous facultatifs."""

    q = serializers.CharField(required=False, allow_blank=True, default="")
    school = serializers.CharField(required=False, allow_blank=True, default="")
    diploma_type = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_diploma_type(self, value: str) -> str:
        return clean_diploma_type(value)


class ProfileSerializer(serializers.Serializer):
    """
    Profil déclaré par le prospect. Tous les champs sont facultatifs.
    Les choix possibles viennent de normalization.py : une valeur inconnue
    est refusée avec un message clair (erreur 400), jamais devinée.
    """

    level = serializers.ChoiceField(choices=Level.CHOICES, required=False, allow_null=True)
    nationality = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=40)
    bac_section = serializers.ChoiceField(choices=list(BacSection.LABELS.items()), required=False, allow_null=True)

    def validate_nationality(self, value: str | None) -> str | None:
        """« Tunisie » -> "TN" ; « 123 » -> erreur 400 « Nationalité non reconnue. »."""
        if not value:
            return None
        try:
            return normalize_nationality(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class EligibilityRequestSerializer(SearchParamsSerializer):
    """
    Demande de vérification : un profil + les formations à évaluer, désignées
    soit par leurs identifiants (`formation_ids`, 1 à 100), soit par les mêmes
    filtres que la recherche (`q`, `school`, `diploma_type`).
    """

    profile = ProfileSerializer(required=False, default=dict)
    formation_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, min_length=1, max_length=MAX_EVALUATED,
    )
