"""Interface d'administration des formations (consultation par l'équipe des admissions)."""

from django.contrib import admin

from .models import Formation


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    # Colonnes affichées dans la liste
    list_display = ("specialty", "diploma_type", "school", "min_level", "nationality_required", "bac_rule", "has_warnings")
    # Filtres dans la colonne de droite
    list_filter = ("school", "diploma_type", "bac_rule", "is_active")
    # Champs utilisés par la barre de recherche
    search_fields = ("specialty", "diploma_label", "school")
    # Champs calculés par l'import : visibles mais non modifiables à la main
    readonly_fields = ("search_text", "import_warnings", "created_at", "updated_at")

    @admin.display(boolean=True, description="anomalie ?")
    def has_warnings(self, obj: Formation) -> bool:
        """Affiche une icône quand l'import a signalé une anomalie sur cette ligne."""
        return bool(obj.import_warnings)