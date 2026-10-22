"""Adresses (URL) du projet."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from catalog.views import FormationViewSet
from chatbot.views import ChatView

# Le routeur DRF génère automatiquement les adresses du ViewSet :
#   /api/formations/       -> liste (avec filtres)
#   /api/formations/{id}/  -> détail d'une formation
router = DefaultRouter()
router.register("formations", FormationViewSet, basename="formation")


def health(request):
    """Vérification simple de disponibilité de l'API."""
    return JsonResponse({"status": "ok"})


admin.site.site_header = "IMSET – Administration des admissions"
admin.site.site_title = "Administration des admissions"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/chat/", ChatView.as_view()),
    path("api/", include(router.urls)),
]