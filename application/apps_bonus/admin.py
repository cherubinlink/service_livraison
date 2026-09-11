# ═══════════════════════════════════════════════════════════════════════
# apps_bonus/admin.py
# ═══════════════════════════════════════════════════════════════════════
from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import TypeBonus, BonusEntreprise


@admin.register(TypeBonus)
class TypeBonusAdmin(admin.ModelAdmin):
    list_display = ('nom', 'categorie', 'valeur', 'est_actif')
    list_filter = ('categorie', 'est_actif')
    search_fields = ('nom', 'description')
    list_editable = ('est_actif',)
    ordering = ('nom',)

    fieldsets = (
        (None, {
            'fields': ('nom', 'categorie', 'valeur', 'description')
        }),
        (_('Statut'), {
            'fields': ('est_actif',)
        }),
    )


class StatutValiditeFilter(admin.SimpleListFilter):
    """
    Filtre calculé (pas un champ en base) pour distinguer rapidement les
    bonus réellement exploitables aujourd'hui de ceux qui ne le sont
    plus (expirés par date ou quota épuisé), sans dépendre uniquement du
    champ `statut` qui peut être resté à ACTIF sans mise à jour auto.
    """
    title = _('Validité réelle')
    parameter_name = 'validite'

    def lookups(self, request, model_admin):
        return (
            ('valide', _('Valide aujourd\'hui')),
            ('expire_date', _('Expiré (date dépassée)')),
            ('quota_epuise', _('Quota épuisé')),
        )

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == 'valide':
            return queryset.filter(
                statut=BonusEntreprise.Statut.ACTIF,
                date_debut__lte=today,
                date_expiration__gte=today,
            ).exclude(
                nb_utilisations_max__gt=0,
                nb_utilisations_actuelles__gte=models.F('nb_utilisations_max'),
            )
        if self.value() == 'expire_date':
            return queryset.filter(date_expiration__lt=today)
        if self.value() == 'quota_epuise':
            return queryset.filter(
                nb_utilisations_max__gt=0,
                nb_utilisations_actuelles__gte=models.F('nb_utilisations_max'),
            )
        return queryset


@admin.register(BonusEntreprise)
class BonusEntrepriseAdmin(admin.ModelAdmin):
    list_display = (
        'entreprise', 'type_bonus', 'zone_cible', 'statut',
        'date_debut', 'date_expiration', 'usage_display', 'est_valide_badge',
    )
    list_filter = ('statut', 'type_bonus__categorie', StatutValiditeFilter)
    search_fields = (
        'entreprise__raison_sociale', 'type_bonus__nom', 'note_interne',
    )
    autocomplete_fields = ('entreprise', 'type_bonus', 'zone_cible', 'attribue_par')
    date_hierarchy = 'date_creation'
    list_select_related = ('entreprise', 'type_bonus', 'zone_cible')
    readonly_fields = ('date_creation', 'nb_utilisations_actuelles')
    ordering = ('-date_creation',)

    fieldsets = (
        (None, {
            'fields': ('entreprise', 'type_bonus', 'zone_cible', 'statut')
        }),
        (_('Période de validité'), {
            'fields': ('date_debut', 'date_expiration')
        }),
        (_('Quota d\'utilisation'), {
            'fields': ('nb_utilisations_max', 'nb_utilisations_actuelles'),
            'description': _(
                '0 dans "Nombre max" signifie une utilisation illimitée.'
            ),
        }),
        (_('Attribution'), {
            'fields': ('attribue_par', 'note_interne', 'date_creation')
        }),
    )

    actions = ['marquer_annule', 'marquer_expire']

    @admin.display(description=_('Utilisations'))
    def usage_display(self, obj):
        if obj.nb_utilisations_max == 0:
            return f"{obj.nb_utilisations_actuelles} / ∞"
        return f"{obj.nb_utilisations_actuelles} / {obj.nb_utilisations_max}"

    @admin.display(description=_('Valide aujourd\'hui'), boolean=True)
    def est_valide_badge(self, obj):
        return obj.est_valide_aujourd_hui

    @admin.action(description=_('Marquer les bonus sélectionnés comme annulés'))
    def marquer_annule(self, request, queryset):
        updated = queryset.update(statut=BonusEntreprise.Statut.ANNULE)
        self.message_user(request, f"{updated} bonus marqué(s) comme annulé(s).")

    @admin.action(description=_('Marquer les bonus sélectionnés comme expirés'))
    def marquer_expire(self, request, queryset):
        updated = queryset.update(statut=BonusEntreprise.Statut.EXPIRE)
        self.message_user(request, f"{updated} bonus marqué(s) comme expiré(s).")