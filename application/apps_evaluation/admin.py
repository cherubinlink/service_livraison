# ═══════════════════════════════════════════════════════════════════════
# apps_evaluation/admin.py
# ═══════════════════════════════════════════════════════════════════════
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Evaluation


class RecommandeFilter(admin.SimpleListFilter):
    """Filtre pratique pour isoler rapidement les avis négatifs à traiter en priorité."""
    title = _('Recommandation')
    parameter_name = 'recommande'

    def lookups(self, request, model_admin):
        return (
            ('oui', _('Recommande')),
            ('non', _('Ne recommande pas')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'oui':
            return queryset.filter(recommande=True)
        if self.value() == 'non':
            return queryset.filter(recommande=False)
        return queryset


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = (
        'livraison', 'entreprise_display', 'livreur_display',
        'note_globale', 'recommande', 'date',
    )
    list_filter = ('note_globale', RecommandeFilter)
    search_fields = (
        'livraison__numero', 'livraison__nom_client',
        'livraison__entreprise__raison_sociale', 'commentaire',
    )
    autocomplete_fields = ('livraison',)
    list_select_related = ('livraison', 'livraison__entreprise', 'livraison__livreur__utilisateur')
    date_hierarchy = 'date'
    readonly_fields = ('id', 'date')
    ordering = ('-date',)

    fieldsets = (
        (None, {
            'fields': ('livraison', 'date')
        }),
        (_('Notes'), {
            'fields': ('note_globale', 'note_rapidite', 'note_etat_colis', 'note_livreur')
        }),
        (_('Avis'), {
            'fields': ('recommande', 'commentaire')
        }),
    )

    @admin.display(description=_('Entreprise'), ordering='livraison__entreprise__raison_sociale')
    def entreprise_display(self, obj):
        return obj.livraison.entreprise.raison_sociale if obj.livraison.entreprise else '—'

    @admin.display(description=_('Livreur'), ordering='livraison__livreur__utilisateur__nom')
    def livreur_display(self, obj):
        if obj.livraison.livreur and obj.livraison.livreur.utilisateur:
            return obj.livraison.livreur.utilisateur.nom
        return '—'

    def has_add_permission(self, request):
        # Le dépôt d'une évaluation est un acte public rattaché à une
        # livraison précise (laisser_evaluation) — un admin ne doit pas
        # pouvoir en créer une au nom d'un client.
        return False

    def has_change_permission(self, request, obj=None):
        # Avis client : lecture seule pour préserver l'intégrité du
        # retour, cohérent avec admin_detail_evaluation (déjà lecture
        # seule côté vue custom).
        return False