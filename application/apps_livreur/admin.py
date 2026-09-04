from django.contrib import admin

from apps_livreur.models import Livreur, PositionLivreurHistorique


@admin.register(Livreur)
class LivreurAdmin(admin.ModelAdmin):
    list_display = [
        'utilisateur', 'numero_cni', 'type_vehicule', 'statut',
        'total_livraisons', 'note_moyenne', 'date_inscription',
    ]
    list_filter = ['statut', 'type_vehicule']
    search_fields = ['numero_cni', 'immatriculation', 'utilisateur__nom', 'utilisateur__email']
    # Évite le N+1 MySQL : utilisateur est affiché dans list_display,
    # donc chaque ligne ferait sinon une requête séparée.
    list_select_related = ['utilisateur']
    list_display_links = ['utilisateur']
    # utilisateur (OneToOne) : table qui grossit avec chaque inscription
    # (entreprises + clients + livreurs confondus) → raw_id_fields
    # plutôt qu'un <select> qui chargerait tout le monde.
    raw_id_fields = ['utilisateur']
    # zones_travail est un M2M SIMPLE (pas de through personnalisé,
    # contrairement à Entrepot.entreprises vu précédemment) :
    # filter_horizontal est donc parfaitement valide ici.
    filter_horizontal = ['zones_travail']
    readonly_fields = ['date_inscription', 'total_livraisons', 'note_moyenne']
    list_per_page = 50


@admin.register(PositionLivreurHistorique)
class PositionLivreurHistoriqueAdmin(admin.ModelAdmin):
    """
    Table d'audit GPS pure — alimentée automatiquement par l'app (tracking
    temps réel), jamais par un admin humain. On la rend volontairement
    LECTURE SEULE dans l'admin (pas d'ajout ni de modification manuelle),
    et on limite fortement ce qui est affiché/filtrable : c'est
    potentiellement la table la plus volumineuse de tout le projet
    (une ligne par livreur toutes les quelques secondes), donc chaque
    choix ici a un impact direct sur la charge MySQL de la page admin.
    """
    list_display = ['livreur', 'horodatage', 'livraison_en_cours', 'latitude', 'longitude']
    # date_hierarchy sur horodatage (déjà db_index=True côté modèle) permet
    # de naviguer par jour/mois sans jamais scanner toute la table par
    # défaut — indispensable ici, pas juste un confort.
    date_hierarchy = 'horodatage'
    list_select_related = ['livreur', 'livraison_en_cours']
    raw_id_fields = ['livreur', 'livraison_en_cours']
    # AUCUN search_fields ni list_filter texte libre ici : sur une table
    # de plusieurs millions de lignes, un filtre MySQL sans index dédié
    # (ex: recherche sur latitude/longitude) provoquerait un scan complet.
    ordering = ['-horodatage']
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False