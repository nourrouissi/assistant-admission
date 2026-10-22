"""Interface d'administration des demandes d'inscription (consultation par l'équipe des admissions)."""

from django.contrib import admin

from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    # Colonnes affichées dans la liste
    list_display = ("last_name", "first_name", "formation", "status", "created_at", "notified")
    # Filtres dans la colonne de droite
    list_filter = ("status", "formation__school", "formation__diploma_type", ("notified_at", admin.EmptyFieldListFilter))
    # Champs utilisés par la barre de recherche
    search_fields = ("last_name", "first_name", "email", "phone", "formation__specialty")
    date_hierarchy = "created_at"
    list_select_related = ("formation",)
    # Données saisies par le prospect et dates techniques : consultables, non modifiables
    readonly_fields = ("last_name", "first_name", "email", "phone", "formation", "created_at", "notified_at")

    @admin.display(boolean=True, description="équipe notifiée ?")
    def notified(self, obj: Application) -> bool:
        """Icône rouge quand l'e-mail à l'équipe n'a pas pu être envoyé."""
        return obj.notified_at is not None

    def has_add_permission(self, request) -> bool:
        """Les demandes viennent uniquement de l'assistant, après confirmation du prospect."""
        return False
