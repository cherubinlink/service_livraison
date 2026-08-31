# ═══════════════════════════════════════════════════════════════════════
# apps_core/admin.py
#
# Points spécifiques à MySQL / InnoDB traités ici :
#
# 1) `show_full_result_count = False` sur tous les ModelAdmin — par
#    défaut, l'admin Django exécute un COUNT(*) pour afficher
#    "X résultats (Y au total)". Sur InnoDB, COUNT(*) est O(n) (contrairement
#    à MyISAM), donc sur une table qui grossit (Utilisateur, Livraison plus
#    tard, etc.) cette requête devient de plus en plus lente. On désactive
#    ce comportement globalement via SwiftDropModelAdmin.
#
# 2) `autocomplete_fields` plutôt que le <select> par défaut sur toutes
#    les ForeignKey vers des tables qui peuvent grossir (Ville, Zone,
#    Utilisateur...). Le <select> par défaut charge TOUTES les lignes de
#    la table liée à chaque affichage du formulaire — sur MySQL, dès que
#    la table dépasse quelques centaines de lignes, ça ralentit nettement
#    le chargement de la page admin.
#    ⚠️ Django exige que le modèle CIBLÉ par autocomplete_fields ait lui
#    aussi un ModelAdmin enregistré avec `search_fields` défini, sinon
#    il lève `ImproperlyConfigured` — c'est pour ça que PaysAdmin,
#    VilleAdmin, ZoneAdmin ont tous un search_fields, même minimal.
#
# 3) `Utilisateur` : le modèle personnalise USERNAME_FIELD='email' et n'a
#    pas de champ `username` — impossible d'utiliser
#    django.contrib.auth.admin.UserAdmin tel quel (il référence
#    `username` un peu partout). On fournit nos propres formulaires de
#    création/modification et on réécrit entièrement fieldsets/
#    add_fieldsets.
#
# 4) TarifHistorique est une table d'audit (générée par signal, pas par
#    saisie manuelle) : on bloque l'ajout/la modification en admin pour
#    ne pas corrompre l'historique, seule la consultation reste possible.
#
# 5) ParametreSysteme.valeur est un TextField (peut contenir du JSON
#    volumineux) : on tronque son affichage dans la liste pour ne pas
#    alourdir le rendu de la page — la valeur complète reste visible/
#    éditable sur la fiche détail.
# ═══════════════════════════════════════════════════════════════════════

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from .models import (
    Utilisateur, Pays, Ville, Zone, Quartier, TarifHistorique,
    CoefficientVehicule, TarifInterVille, ParametreSysteme,
)


class SwiftDropModelAdmin(admin.ModelAdmin):
    """Base commune : désactive le COUNT(*) coûteux sur InnoDB/MySQL."""
    show_full_result_count = False
    list_per_page = 50


# ═══════════════════════════════════════════════════════════════════════
# §1 – UTILISATEUR (modèle d'authentification personnalisé)
# ═══════════════════════════════════════════════════════════════════════

class UtilisateurCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Utilisateur
        fields = ('email', 'nom')
        # UserCreationForm.Meta.fields référence 'username' par défaut —
        # on le remplace intégralement plutôt que d'y ajouter 'email'.


class UtilisateurChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Utilisateur
        fields = '__all__'


@admin.register(Utilisateur)
class UtilisateurAdmin(DjangoUserAdmin):
    add_form = UtilisateurCreationForm
    form = UtilisateurChangeForm
    model = Utilisateur

    show_full_result_count = False
    list_per_page = 50

    # USERNAME_FIELD = 'email' côté modèle → on trie et on identifie par email,
    # jamais par 'username' (qui n'existe pas sur ce modèle).
    ordering = ('-date_creation',)
    list_display = ('email', 'nom', 'role', 'est_actif', 'is_staff', 'telephone_verifie', 'date_creation')
    list_filter = ('role', 'est_actif', 'is_staff', 'email_verifie', 'telephone_verifie', 'langue')
    search_fields = ('email', 'nom', 'telephone')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Informations personnelles'), {
            'fields': ('nom', 'telephone', 'photo_profil', 'bio', 'langue')
        }),
        (_('Rôle & statut'), {
            'fields': ('role', 'est_actif', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        (_('Vérification'), {
            'fields': ('email_verifie', 'telephone_verifie')
        }),
        (_('Sécurité'), {
            'fields': ('tentatives_connexion', 'compte_bloque_jusqu_au', 'code_otp', 'code_otp_expiration')
        }),
        (_('Dates & suivi'), {
            'fields': ('last_login', 'derniere_connexion_at', 'derniere_connexion_ip', 'date_creation', 'device_token')
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nom', 'role', 'password1', 'password2'),
        }),
    )
    readonly_fields = ('date_creation', 'last_login', 'derniere_connexion_at', 'derniere_connexion_ip')
    filter_horizontal = ('groups', 'user_permissions')


# ═══════════════════════════════════════════════════════════════════════
# §2 – GÉOGRAPHIE
# ═══════════════════════════════════════════════════════════════════════

@admin.register(Pays)
class PaysAdmin(SwiftDropModelAdmin):
    list_display = ('nom', 'code_iso', 'indicatif', 'devise', 'est_actif')
    list_filter = ('est_actif', 'devise')
    search_fields = ('nom', 'code_iso')  # requis pour servir de cible à autocomplete_fields ailleurs
    ordering = ('nom',)


@admin.register(Ville)
class VilleAdmin(SwiftDropModelAdmin):
    list_display = ('nom', 'pays', 'code', 'est_active', 'date_ajout')
    list_filter = ('pays', 'est_active')
    search_fields = ('nom', 'code', 'pays__nom')
    autocomplete_fields = ('pays',)
    ordering = ('pays', 'nom')


@admin.register(Zone)
class ZoneAdmin(SwiftDropModelAdmin):
    list_display = ('nom', 'ville', 'prix_livraison', 'prix_dynamique', 'coefficient_pointe', 'est_active')
    list_filter = ('ville__pays', 'ville', 'prix_dynamique', 'est_active')
    search_fields = ('nom', 'ville__nom')
    autocomplete_fields = ('ville',)
    readonly_fields = ('date_creation', 'date_modification')
    ordering = ('ville', 'nom')


@admin.register(Quartier)
class QuartierAdmin(SwiftDropModelAdmin):
    list_display = ('nom', 'zone', 'repere', 'est_actif')
    list_filter = ('zone__ville', 'est_actif')
    search_fields = ('nom', 'zone__nom', 'repere')
    autocomplete_fields = ('zone',)
    ordering = ('zone', 'nom')


@admin.register(TarifHistorique)
class TarifHistoriqueAdmin(SwiftDropModelAdmin):
    """
    Table d'audit : consultable, mais non modifiable/créable/supprimable
    à la main pour préserver l'intégrité de l'historique de tarifs.
    """
    list_display = ('zone', 'ancien_prix', 'nouveau_prix', 'modifie_par', 'date')
    list_filter = ('date', 'zone__ville')
    search_fields = ('zone__nom', 'raison')
    autocomplete_fields = ('zone', 'modifie_par')
    readonly_fields = [f.name for f in TarifHistorique._meta.fields]
    date_hierarchy = 'date'
    ordering = ('-date',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Laisse la suppression possible pour un admin (purge manuelle),
        # à retirer aussi si l'historique doit être strictement immuable.
        return request.user.is_superuser


# ═══════════════════════════════════════════════════════════════════════
# §3 – TARIFICATION VÉHICULE & INTER-VILLES
# ═══════════════════════════════════════════════════════════════════════

@admin.register(CoefficientVehicule)
class CoefficientVehiculeAdmin(SwiftDropModelAdmin):
    """
    Petite table de référence (une ligne par TypeVehicule) : l'admin la
    modifie souvent, d'où list_editable pour ajuster vite sans ouvrir
    chaque fiche.
    """
    list_display = ('type_vehicule', 'coefficient_multiplicateur', 'frais_fixe_supplement', 'est_actif')
    list_display_links = ('type_vehicule',)
    list_editable = ('coefficient_multiplicateur', 'frais_fixe_supplement', 'est_actif')
    list_filter = ('est_actif',)
    search_fields = ('type_vehicule', 'description')
    ordering = ('coefficient_multiplicateur',)


@admin.register(TarifInterVille)
class TarifInterVilleAdmin(SwiftDropModelAdmin):
    list_display = (
        'ville_depart', 'ville_arrivee', 'prix_forfaitaire', 'tarif_par_km',
        'coefficient_vehicule_applicable', 'est_actif',
    )
    list_filter = ('est_actif', 'coefficient_vehicule_applicable')
    search_fields = ('ville_depart__nom', 'ville_arrivee__nom')
    autocomplete_fields = ('ville_depart', 'ville_arrivee')
    readonly_fields = ('date_modification',)
    ordering = ('ville_depart', 'ville_arrivee')


# ═══════════════════════════════════════════════════════════════════════
# §4 – PARAMÈTRES SYSTÈME
# ═══════════════════════════════════════════════════════════════════════

@admin.register(ParametreSysteme)
class ParametreSystemeAdmin(SwiftDropModelAdmin):
    list_display = ('cle', 'valeur_apercu', 'type_valeur', 'modifie_par', 'date_modification')
    list_filter = ('type_valeur',)
    search_fields = ('cle', 'description')
    readonly_fields = ('date_modification',)
    ordering = ('cle',)

    @admin.display(description=_('Valeur'))
    def valeur_apercu(self, obj):
        # `valeur` est un TextField pouvant contenir du JSON volumineux —
        # on tronque l'affichage en liste pour ne pas alourdir la page ;
        # la fiche détail affiche toujours la valeur complète et éditable.
        return Truncator(obj.valeur).chars(80)