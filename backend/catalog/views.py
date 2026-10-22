"""Vues API du catalogue. Les vues restent fines : la logique est dans services.py et eligibility.py."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .eligibility import Profile
from .serializers import MAX_EVALUATED, EligibilityRequestSerializer, FormationSerializer, SearchParamsSerializer
from .services import SearchResult, eligibility_cards, formations_by_ids, search_catalog


class FormationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/formations/?q=informatique&school=Sousse&diploma_type=BTS   recherche (paginée par 20)
    GET  /api/formations/{id}/                                            une formation
    POST /api/formations/eligibility/                                     vérification d'éligibilité

    Recherche et éligibilité sont deux actions distinctes : on peut proposer
    des formations sans rien savoir du prospect (règle du sujet).
    """

    serializer_class = FormationSerializer

    def _search(self) -> SearchResult:
        # Filtres validés : un diploma_type inconnu renvoie une erreur 400
        params = SearchParamsSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return search_catalog(**_search_filters(params.validated_data))

    def get_queryset(self):
        return self._search().formations

    def list(self, request, *args, **kwargs):
        """
        Liste paginée, complétée par `unmatched_terms`.
        Sujet : « Afficher les formations pertinentes » : le chatbot sait quels mots
        n'ont rien trouvé.
        """
        result = self._search()
        page = self.paginate_queryset(result.formations)     # pagination toujours active (PAGE_SIZE)
        response = self.get_paginated_response(self.get_serializer(page, many=True).data)
        response.data["unmatched_terms"] = result.unmatched_terms
        return response

    @action(detail=False, methods=["post"], serializer_class=EligibilityRequestSerializer)
    def eligibility(self, request):
        """
        Évalue des formations pour un profil déclaré.

        Corps JSON :
          {"profile": {"level": "BAC", "nationality": "TN", "bac_section": "INFORMATIQUE"},
           "q": "informatique"}                 (ou "formation_ids": [12, 50])

        Réponse : les cartes triées par statut, la liste regroupée des informations
        à demander au prospect, les identifiants introuvables et, pour une recherche
        par filtres, les mots non trouvés (`unmatched_terms`).
        """
        request_data = EligibilityRequestSerializer(data=request.data)
        request_data.is_valid(raise_exception=True)          # erreur 400 si la demande est invalide
        data = request_data.validated_data

        profile = Profile(**{key: value for key, value in data["profile"].items() if value})

        unknown_ids: list[int] = []
        search_details: dict = {}
        if "formation_ids" in data:                          # présence de la clé, pas sa valeur
            formations, unknown_ids = formations_by_ids(data["formation_ids"])
        else:
            result = search_catalog(**_search_filters(data))
            formations = list(result.formations[:MAX_EVALUATED])
            search_details = {"unmatched_terms": result.unmatched_terms}

        results, missing = eligibility_cards(formations, profile)

        return Response({
            "count": len(results),
            "missing_information": missing,
            "unknown_formation_ids": unknown_ids,
            **search_details,
            "results": results,
        })


def _search_filters(data: dict) -> dict:
    """Extrait les filtres de recherche (q, school, diploma_type) de données validées."""
    return {"query": data["q"], "school": data["school"], "diploma_type": data["diploma_type"]}
