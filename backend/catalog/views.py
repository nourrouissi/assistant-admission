"""Vues API du catalogue. Les vues restent fines : la logique est dans services.py."""

from rest_framework import viewsets

from .serializers import FormationSerializer
from .services import search_formations


class FormationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/formations/?q=informatique&school=Sousse&diploma_type=BTS
    GET /api/formations/{id}/

    Lecture seule : les formations sont gérées par l'import Excel et l'administration.
    """

    serializer_class = FormationSerializer

    def get_queryset(self):
        params = self.request.query_params
        return search_formations(
            query=params.get("q", ""),
            school=params.get("school", ""),
            diploma_type=params.get("diploma_type", ""),
        )