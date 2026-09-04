from django.contrib import admin
from django.db.models import Sum, F

from apps_catalogue.models import (
    Categorie, Produit, PhotoProduit, StockEntrepot,
    MouvementStock, AlerteStock, RetourStockProprietaire,
)


# ═══════════════════════════════════════════════════════════════════════
# §1 – CATÉGORIES
# ═══════════════════════════════════════════════════════════════════════

@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ['nom', 'parent', 'ordre', 'est_active']
    list_filter = ['est_active']
    search_fields = ['nom', 'slug']
    prepopulated_fields = {'slug': ('nom',)}
    # parent est un FK vers le même modèle (Categorie) : raw_id_fields
    # évite qu'un <select> classique liste TOUTES les catégories (y
    # compris elle-même) à chaque édition — sans intérêt une fois le
    # catalogue de catégories un peu fourni, et ça grossit à chaque
    # requête MySQL de la page.
    raw_id_fields = ['parent']
    list_select_related = ['parent']
    ordering = ['ordre', 'nom']


# ═══════════════════════════════════════════════════════════════════════
# §2 – PRODUIT + PhotoProduit (inline)
# ═══════════════════════════════════════════════════════════════════════

class PhotoProduitInline(admin.TabularInline):
    model = PhotoProduit
    extra = 0
    fields = ['photo', 'legende', 'ordre']


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'entreprise', 'categorie', 'prix_unitaire', 'statut',
        'vendu_en_ligne', 'vehicule_minimum_requis', 'stock_disponible_annote',
    ]
    list_filter = ['statut', 'vendu_en_ligne', 'qualite_produit', 'vehicule_minimum_requis', 'fragile', 'necessite_froid']
    search_fields = ['nom', 'reference_sku', 'code_barre', 'reference_yopishop', 'entreprise__raison_sociale']
    # Sur MySQL, sans list_select_related, chaque ligne de la liste (25
    # par défaut) déclenche une requête séparée pour entreprise ET
    # categorie — soit jusqu'à 50 requêtes en plus de la liste elle-même.
    list_select_related = ['entreprise', 'categorie']
    raw_id_fields = ['entreprise', 'categorie', 'enregistre_par', 'valide_par']
    readonly_fields = ['date_creation', 'date_modification']
    inlines = [PhotoProduitInline]
    list_per_page = 50

    def get_queryset(self, request):
        """
        stock_total_disponible est une @property qui lance un .aggregate()
        SQL à chaque appel. L'afficher tel quel dans list_display
        déclencherait UNE requête d'agrégation PAR LIGNE affichée (25
        lignes = 25 requêtes MySQL supplémentaires rien que pour cette
        colonne). On annote donc la queryset UNE SEULE FOIS ici, et
        stock_disponible_annote() ci-dessous lit juste l'attribut annoté
        — aucune requête additionnelle par ligne.
        """
        qs = super().get_queryset(request)
        return qs.annotate(
            _stock_disponible=Sum(F('stocks_entrepots__quantite_stock') - F('stocks_entrepots__quantite_reservee'))
        )

    @admin.display(description='Stock disponible', ordering='_stock_disponible')
    def stock_disponible_annote(self, obj):
        return max(0, obj._stock_disponible or 0)


# ═══════════════════════════════════════════════════════════════════════
# §3 – STOCK PAR ENTREPÔT (édition manuelle autorisée : réappro, ajustements)
# ═══════════════════════════════════════════════════════════════════════

class MouvementStockInline(admin.TabularInline):
    """
    Historique en LECTURE SEULE sur la fiche StockEntrepot : chaque
    mouvement doit passer par les méthodes du modèle (reserver,
    decrementer_stock...) pour que stock_avant/stock_apres restent
    cohérents — jamais une saisie manuelle qui casserait cette cohérence.
    """
    model = MouvementStock
    extra = 0
    fields = ['type_mouvement', 'quantite', 'stock_avant', 'stock_apres', 'effectue_par', 'livraison', 'date']
    readonly_fields = fields
    can_delete = False
    raw_id_fields = ['effectue_par', 'livraison']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StockEntrepot)
class StockEntrepotAdmin(admin.ModelAdmin):
    list_display = [
        'produit', 'entrepot', 'quantite_stock', 'quantite_reservee',
        'quantite_disponible', 'stock_bas', 'en_rupture',
    ]
    list_filter = ['entrepot']
    search_fields = ['produit__nom', 'produit__reference_sku', 'entrepot__nom', 'entrepot__code']
    list_select_related = ['produit', 'entrepot']
    raw_id_fields = ['produit', 'entrepot']
    readonly_fields = ['date_creation', 'date_modification']
    inlines = [MouvementStockInline]
    list_per_page = 50


# ═══════════════════════════════════════════════════════════════════════
# §4 – MOUVEMENTS DE STOCK (standalone) — journal, lecture seule
# ═══════════════════════════════════════════════════════════════════════

@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    """
    Enregistrement standalone en plus de l'inline sur StockEntrepot :
    utile pour un audit transverse (ex: tous les PERTE/PEREMPTION du
    mois, tous les mouvements liés à une livraison précise) sans ouvrir
    chaque fiche stock une à une.

    LECTURE SEULE ici aussi, et pour la même raison que
    PositionLivreurHistorique vu précédemment : c'est potentiellement une
    table volumineuse (un mouvement par sortie de livraison, par
    entrepôt, par produit), et une modification manuelle romprait la
    cohérence stock_avant/stock_apres calculée par le code métier.
    """
    list_display = ['stock_entrepot', 'type_mouvement', 'quantite', 'stock_avant', 'stock_apres', 'date']
    list_filter = ['type_mouvement']
    # date_hierarchy s'appuie sur l'index db_index=True déjà défini sur
    # le champ dans le modèle — indispensable pour naviguer sans scanner
    # toute la table sur MySQL une fois le volume important.
    date_hierarchy = 'date'
    list_select_related = ['stock_entrepot__produit', 'stock_entrepot__entrepot', 'effectue_par', 'livraison']
    raw_id_fields = ['stock_entrepot', 'effectue_par', 'livraison']
    search_fields = ['stock_entrepot__produit__nom', 'note']
    ordering = ['-date']
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ═══════════════════════════════════════════════════════════════════════
# §5 – ALERTES STOCK — création automatique, seul le traitement est manuel
# ═══════════════════════════════════════════════════════════════════════

@admin.register(AlerteStock)
class AlerteStockAdmin(admin.ModelAdmin):
    """
    Créées automatiquement par StockEntrepot._verifier_alertes()
    (get_or_create) : pas de création manuelle possible ici. Seuls
    traitee / traitee_par / date_traitement restent modifiables, pour
    qu'un admin puisse marquer une alerte comme suivie.
    """
    list_display = ['stock_entrepot', 'type_alerte', 'quantite_au_moment', 'traitee', 'date']
    list_filter = ['type_alerte', 'traitee']
    date_hierarchy = 'date'
    list_select_related = ['stock_entrepot__produit', 'stock_entrepot__entrepot', 'traitee_par']
    raw_id_fields = ['stock_entrepot', 'traitee_par']
    readonly_fields = ['stock_entrepot', 'type_alerte', 'quantite_au_moment', 'date']
    ordering = ['-date']
    list_per_page = 50

    def has_add_permission(self, request):
        return False


# ═══════════════════════════════════════════════════════════════════════
# §6 – RETOURS DE STOCK AU PROPRIÉTAIRE — création automatique (inactivité)
# ═══════════════════════════════════════════════════════════════════════

@admin.register(RetourStockProprietaire)
class RetourStockProprietaireAdmin(admin.ModelAdmin):
    """
    Créés automatiquement par Entreprise.desactiver_pour_inactivite() —
    pas de création manuelle. Seul confirme_retire_par_entreprise reste
    modifiable, pour tracer que l'entreprise a bien récupéré ses produits.
    """
    list_display = ['entreprise', 'produit', 'entrepot', 'quantite_retournee', 'motif', 'confirme_retire_par_entreprise', 'date_creation']
    list_filter = ['motif', 'confirme_retire_par_entreprise']
    search_fields = ['entreprise__raison_sociale', 'produit__nom']
    date_hierarchy = 'date_creation'
    list_select_related = ['entreprise', 'produit', 'entrepot']
    raw_id_fields = ['entreprise', 'produit', 'entrepot']
    readonly_fields = ['entreprise', 'produit', 'entrepot', 'quantite_retournee', 'motif', 'date_creation']
    ordering = ['-date_creation']
    list_per_page = 50

    def has_add_permission(self, request):
        return False