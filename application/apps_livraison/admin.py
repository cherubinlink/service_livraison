# ═══════════════════════════════════════════════════════════════════════
# apps_livraison/admin.py
# ═══════════════════════════════════════════════════════════════════════
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Livraison, LigneLivraison, HistoriqueStatutLivraison, LivraisonDirecte


class LigneLivraisonInline(admin.TabularInline):
    model = LigneLivraison
    extra = 0
    autocomplete_fields = ('produit', 'stock_entrepot')
    fields = (
        'produit', 'stock_entrepot', 'quantite',
        'prix_unitaire_snapshot', 'vendu_en_ligne_snapshot', 'vehicule_requis_snapshot',
    )
    readonly_fields = ('vendu_en_ligne_snapshot', 'vehicule_requis_snapshot')


class HistoriqueStatutLivraisonInline(admin.TabularInline):
    """Lecture seule : l'historique se construit uniquement via changer_statut()."""
    model = HistoriqueStatutLivraison
    extra = 0
    can_delete = False
    fields = ('statut_avant', 'statut_apres', 'commentaire', 'effectue_par', 'date')
    readonly_fields = fields
    ordering = ('-date',)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Livraison)
class LivraisonAdmin(admin.ModelAdmin):
    list_display = (
        'numero', 'entreprise', 'nom_client', 'statut',
        'statut_reception', 'gain_entreprise', 'date_creation',
    )
    list_filter = (
        'statut', 'statut_reception', 'origine_commande',
        'type_facturation', 'priorite',
    )
    search_fields = (
        'numero', 'nom_client', 'telephone_client', 'telephone_client_2',
        'entreprise__raison_sociale',
    )
    autocomplete_fields = (
        'entreprise', 'cree_par', 'valide_par', 'livreur', 'attribue_par',
        'ville_livraison', 'zone_livraison', 'quartier_livraison',
        'valide_reception_par', 'bonus_applique',
    )
    list_select_related = ('entreprise', 'zone_livraison', 'livreur')
    date_hierarchy = 'date_creation'
    readonly_fields = (
        'id', 'numero', 'date_creation', 'date_soumission', 'date_validation',
        'date_attribution', 'date_prise_en_charge', 'date_livraison_effective',
        'montant_total_produits', 'frais_livraison_base_zone', 'frais_livraison_applique',
        'commission_yopishop_montant', 'gain_entreprise', 'montant_a_encaisser',
        'vehicule_requis', 'type_facturation', 'contient_produit_en_ligne',
        'contient_produit_hors_ligne', 'code_confirmation',
    )
    inlines = [LigneLivraisonInline, HistoriqueStatutLivraisonInline]
    ordering = ('-date_creation',)

    fieldsets = (
        (None, {
            'fields': ('numero', 'origine_commande', 'statut', 'statut_reception')
        }),
        (_('Acteurs'), {
            'fields': ('entreprise', 'cree_par', 'valide_par', 'livreur', 'attribue_par')
        }),
        (_('Destination & client'), {
            'fields': (
                'ville_livraison', 'zone_livraison', 'quartier_livraison', 'adresse_exacte',
                'coordonnees_livraison_lat', 'coordonnees_livraison_lng',
                'nom_client', 'telephone_client', 'telephone_client_2', 'email_client',
            )
        }),
        (_('Paramètres de commande'), {
            'fields': ('priorite', 'mode_encaissement', 'montant_a_encaisser', 'note_livreur')
        }),
        (_('Refus / échec'), {
            'fields': ('motif_refus', 'motif_echec'),
            'classes': ('collapse',),
        }),
        (_('Réception côté entreprise'), {
            'fields': ('date_validation_reception', 'valide_reception_par')
        }),
        (_('Timeline'), {
            'fields': (
                'date_creation', 'date_soumission', 'date_validation',
                'date_attribution', 'date_prise_en_charge', 'date_livraison_effective',
                'date_souhaitee',
            ),
            'classes': ('collapse',),
        }),
        (_('Facturation (calculée automatiquement)'), {
            'fields': (
                'vehicule_requis', 'type_facturation',
                'contient_produit_en_ligne', 'contient_produit_hors_ligne',
                'montant_total_produits', 'frais_livraison_base_zone', 'frais_livraison_applique',
                'commission_yopishop_pct', 'commission_yopishop_montant',
            )
        }),
        (_('Paiement des frais par le client'), {
            'fields': (
                'frais_livraison_paye_par_client', 'frais_livraison_paye_integralement',
                'frais_livraison_signale_par', 'date_signalement_frais',
            ),
            'classes': ('collapse',),
        }),
        (_('Gain & bonus'), {
            'fields': ('gain_entreprise', 'bonus_applique', 'reduction_bonus')
        }),
        (_('Preuve de livraison'), {
            'fields': ('photo_preuve', 'signature_client_img', 'code_confirmation', 'confirmation_recu'),
            'classes': ('collapse',),
        }),
    )

    actions = ['recalculer_frais_et_gains']

    @admin.action(description=_('Recalculer les frais et le gain depuis les lignes'))
    def recalculer_frais_et_gains(self, request, queryset):
        recalculees = 0
        for livraison in queryset:
            livraison.recalculer_depuis_lignes()
            recalculees += 1
        self.message_user(request, f"{recalculees} livraison(s) recalculée(s).")


@admin.register(LivraisonDirecte)
class LivraisonDirecteAdmin(admin.ModelAdmin):
    list_display = (
        'numero', 'nom_expediteur', 'nom_destinataire', 'statut',
        'type_tarification', 'prix_total', 'date_creation',
    )
    list_filter = ('statut', 'type_tarification')
    search_fields = (
        'numero', 'nom_expediteur', 'nom_destinataire',
        'telephone_expediteur', 'telephone_destinataire', 'token_suivi',
    )
    autocomplete_fields = (
        'client', 'livraison_par_entreprise', 'ville_collecte', 'zone_collecte',
        'ville_livraison', 'zone_livraison', 'livreur',
    )
    list_select_related = ('ville_collecte', 'ville_livraison', 'livreur')
    date_hierarchy = 'date_creation'
    readonly_fields = ('id', 'numero', 'token_suivi', 'prix_total', 'date_creation')
    ordering = ('-date_creation',)

    fieldsets = (
        (None, {
            'fields': ('numero', 'statut', 'client', 'livraison_par_entreprise')
        }),
        (_('Expéditeur & colis'), {
            'fields': (
                'nom_expediteur', 'telephone_expediteur', 'description_colis',
                'poids_kg', 'valeur_declaree',
            )
        }),
        (_('Collecte'), {
            'fields': (
                'adresse_collecte', 'ville_collecte', 'zone_collecte',
                'latitude_depart', 'longitude_depart',
            )
        }),
        (_('Livraison'), {
            'fields': (
                'nom_destinataire', 'telephone_destinataire', 'adresse_livraison',
                'ville_livraison', 'zone_livraison', 'latitude_arrivee', 'longitude_arrivee',
            )
        }),
        (_('Tarification'), {
            'fields': (
                'type_tarification', 'vehicule_requis', 'distance_km',
                'tarif_par_km', 'prix_negocie', 'prix_total',
            )
        }),
        (_('Suivi'), {
            'fields': ('livreur', 'token_suivi', 'date_creation', 'date_livraison')
        }),
    )