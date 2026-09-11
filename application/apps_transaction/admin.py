from django.contrib import admin

from apps_transaction.models import Transaction, LotPaiementEntreprise


# ═══════════════════════════════════════════════════════════════════════
# §1 – TRANSACTION — journal comptable, LECTURE SEULE
#
# Chaque Transaction est créée par le code métier (ex :
# LotPaiementEntreprise.confirmer_reception_entreprise() pour
# GAIN_ENTREPRISE), jamais saisie à la main : `reference` est
# auto-générée dans save(), et le lien entreprise/livraison/montant doit
# rester cohérent avec l'opération qui l'a produite. On verrouille donc
# la création ET la modification, comme pour MouvementStock vu plus tôt.
# ═══════════════════════════════════════════════════════════════════════

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'type_transaction', 'entreprise', 'montant',
        'statut_paiement', 'date',
    ]
    list_filter = ['type_transaction', 'statut_paiement']
    search_fields = ['reference', 'entreprise__raison_sociale', 'note']
    # date_hierarchy s'appuie sur le db_index=True déjà posé côté modèle :
    # indispensable dès que cette table grossit (une ligne par livraison
    # payée, par frais prélevé, par commission...).
    date_hierarchy = 'date'
    # Sur MySQL, sans list_select_related, chaque ligne affichée
    # déclenche une requête séparée pour entreprise (et livraison/
    # livraison_directe si tu les ajoutes un jour à list_display).
    list_select_related = ['entreprise', 'livraison', 'livraison_directe']
    raw_id_fields = ['entreprise', 'livraison', 'livraison_directe']
    readonly_fields = [
        'reference', 'entreprise', 'livraison', 'livraison_directe',
        'type_transaction', 'montant', 'statut_paiement', 'note', 'date',
    ]
    ordering = ['-date']
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ═══════════════════════════════════════════════════════════════════════
# §2 – LOT DE PAIEMENT ENTREPRISE
#
# La création réelle passe par admin_creer_lot_paiement() qui appelle
# ensuite construire_depuis_livraisons_eligibles() — sans cet appel, un
# lot créé directement depuis l'admin Django resterait à 0 FCFA, sans
# aucune livraison rattachée. On désactive donc l'ajout ici pour forcer
# le passage par la vue dédiée, et on verrouille en lecture seule tous
# les champs calculés/pilotés par le code métier (montants, statut,
# traçabilité d'envoi et de confirmation) pour qu'une modification
# manuelle depuis l'admin ne puisse jamais les faire diverger du calcul
# réel.
# ═══════════════════════════════════════════════════════════════════════

@admin.register(LotPaiementEntreprise)
class LotPaiementEntrepriseAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'entreprise', 'periode_debut', 'periode_fin',
        'montant_net_a_payer', 'statut', 'date_creation',
    ]
    list_filter = ['statut', 'methode_paiement']
    search_fields = ['reference', 'entreprise__raison_sociale', 'reference_transaction_externe']
    date_hierarchy = 'date_creation'
    list_select_related = ['entreprise', 'envoye_par', 'confirme_par']
    raw_id_fields = ['entreprise', 'envoye_par', 'confirme_par']
    # livraisons est un ManyToManyField SIMPLE (pas de through model avec
    # colonnes en plus, contrairement à Entrepot.entreprises vu
    # précédemment) : filter_horizontal est donc valide ici. On le garde
    # malgré tout en lecture seule ci-dessous — voir readonly_fields.
    filter_horizontal = ['livraisons']

    readonly_fields = [
        'reference', 'livraisons',
        'montant_brut_produits', 'montant_frais_livraison_deduits',
        'montant_commission_yopishop_deduite', 'montant_net_a_payer',
        'statut', 'envoye_par', 'date_envoi', 'confirme_par',
        'date_confirmation_entreprise', 'date_creation',
    ]
    list_per_page = 50

    def has_add_permission(self, request):
        return False