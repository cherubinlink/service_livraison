from django.contrib import admin

from apps_entreprise.models import (
    Entreprise, FraisGardiennage, ContactEntreprise, DocumentEntreprise,
    Entrepot, AffectationEntrepot,
)


# ═══════════════════════════════════════════════════════════════════════
# §1 – ENTREPRISE + ses inlines (Contact, Document, FraisGardiennage)
# ═══════════════════════════════════════════════════════════════════════

class ContactEntrepriseInline(admin.TabularInline):
    model = ContactEntreprise
    extra = 0
    fields = ['type_contact', 'nom', 'telephone', 'email', 'est_principal']


class DocumentEntrepriseInline(admin.TabularInline):
    model = DocumentEntreprise
    extra = 0
    fields = ['type_doc', 'nom_fichier', 'fichier', 'verifie', 'verifie_par', 'date_verification']
    readonly_fields = ['date_verification']
    # raw_id_fields évite un <select> qui charge TOUS les Utilisateur en
    # mémoire à chaque affichage de la fiche entreprise — sur MySQL avec
    # une table utilisateurs qui grossit, ce <select> devient la requête
    # la plus lente de la page admin.
    raw_id_fields = ['verifie_par']


class FraisGardiennageInline(admin.TabularInline):
    model = FraisGardiennage
    extra = 0
    fields = ['montant_du', 'montant_paye', 'paye', 'raison', 'date_paiement', 'valide_par']
    readonly_fields = ['date_paiement']
    raw_id_fields = ['valide_par']


@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    list_display = [
        'raison_sociale', 'nom_commercial', 'secteur', 'statut',
        'score_fiabilite', 'ville_principale', 'cycle_paiement', 'date_creation',
    ]
    list_filter = ['statut', 'secteur', 'type_entreprise', 'cycle_paiement', 'taille']
    search_fields = ['raison_sociale', 'nom_commercial', 'numero_registre', 'numero_contribuable_niu']
    # Sur MySQL, list_select_related évite le classique N+1 : sans ça,
    # afficher ville_principale dans list_display fait une requête par
    # ligne affichée (25 lignes/page = 25 requêtes en plus de la liste).
    list_select_related = ['ville_principale', 'zone_principale', 'utilisateur']
    # id étant un UUIDField, PAS un AutoField : impossible de trier
    # dessus de façon naturelle et ça n'a aucun intérêt pour l'admin —
    # on force explicitement les colonnes cliquables via list_display_links
    # plutôt que de laisser Django deviner.
    list_display_links = ['raison_sociale']
    # raw_id_fields plutôt que des <select> : utilisateur/ville_principale/
    # zone_principale/valide_par pointent vers des tables qui grossissent —
    # un <select> classique chargerait tous les enregistrements à chaque
    # ouverture de la fiche, ce qui devient très lourd sur MySQL passé
    # quelques milliers de lignes.
    raw_id_fields = ['utilisateur', 'ville_principale', 'zone_principale', 'valide_par']
    # zones_favorites est un M2M SIMPLE (pas de through personnalisé) :
    # filter_horizontal est donc autorisé ici, contrairement à
    # Entrepot.entreprises plus bas.
    filter_horizontal = ['zones_favorites']
    readonly_fields = ['date_creation', 'date_modification', 'date_validation']
    inlines = [ContactEntrepriseInline, DocumentEntrepriseInline, FraisGardiennageInline]
    list_per_page = 50


# ContactEntreprise et DocumentEntreprise restent gérés depuis l'inline
# ci-dessus dans 99% des cas, mais un enregistrement standalone reste
# utile pour une recherche globale (ex: retrouver un document par nom de
# fichier sans ouvrir chaque entreprise une à une).

@admin.register(ContactEntreprise)
class ContactEntrepriseAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type_contact', 'entreprise', 'telephone', 'est_principal']
    list_filter = ['type_contact', 'est_principal']
    search_fields = ['nom', 'telephone', 'email', 'entreprise__raison_sociale']
    list_select_related = ['entreprise']
    raw_id_fields = ['entreprise']


@admin.register(DocumentEntreprise)
class DocumentEntrepriseAdmin(admin.ModelAdmin):
    list_display = ['nom_fichier', 'type_doc', 'entreprise', 'verifie', 'date_upload']
    list_filter = ['type_doc', 'verifie']
    search_fields = ['nom_fichier', 'entreprise__raison_sociale']
    list_select_related = ['entreprise', 'verifie_par']
    raw_id_fields = ['entreprise', 'verifie_par']
    readonly_fields = ['date_upload', 'taille_fichier']


@admin.register(FraisGardiennage)
class FraisGardiennageAdmin(admin.ModelAdmin):
    list_display = ['entreprise', 'montant_du', 'montant_paye', 'paye', 'date_creation']
    list_filter = ['paye']
    search_fields = ['entreprise__raison_sociale']
    list_select_related = ['entreprise', 'valide_par']
    raw_id_fields = ['entreprise', 'valide_par']
    readonly_fields = ['date_creation']


# ═══════════════════════════════════════════════════════════════════════
# §2 – ENTREPÔT + AffectationEntrepot
#
# ERREUR ÉVITÉE ICI (peu importe le SGBD, mais réelle dans ce modèle) :
# Entrepot.entreprises est un ManyToManyField avec through=AffectationEntrepot,
# et ce through model a des colonnes en plus des deux FK obligatoires
# (affecte_par, date_affectation, est_active). Django INTERDIT d'afficher
# un tel champ via filter_horizontal / filter_vertical / un simple
# ManyToManyField widget dans le ModelAdmin — ça lève une erreur de
# vérification au démarrage (admin.E013/E014 : "cannot be used because
# it defines a through model with additional fields"). La seule façon
# correcte de gérer cette relation dans l'admin est un TabularInline
# sur le through model lui-même, ci-dessous.
# ═══════════════════════════════════════════════════════════════════════

class AffectationEntrepotInline(admin.TabularInline):
    model = AffectationEntrepot
    extra = 0
    fields = ['entreprise', 'affecte_par', 'date_affectation', 'est_active']
    readonly_fields = ['date_affectation']
    # entreprise pointe vers Entreprise (peut devenir une table volumineuse) :
    # raw_id_fields reste indispensable ici pour la même raison que plus haut.
    raw_id_fields = ['entreprise', 'affecte_par']


@admin.register(Entrepot)
class EntrepotAdmin(admin.ModelAdmin):
    list_display = [
        'nom', 'code', 'ville', 'zone', 'responsable',
        'est_actif', 'gere_produits_froid', 'gere_produits_lourds',
    ]
    list_filter = ['ville', 'est_actif', 'gere_produits_froid', 'gere_produits_lourds']
    search_fields = ['nom', 'code']
    list_select_related = ['ville', 'zone', 'responsable']
    raw_id_fields = ['ville', 'zone', 'responsable']
    readonly_fields = ['date_creation']
    # Ne JAMAIS mettre 'entreprises' dans fields/exclude ici — ce champ
    # M2M à through n'est pas rendable par un ModelForm standard.
    # AffectationEntrepotInline (ci-dessus) est la voie d'édition.
    inlines = [AffectationEntrepotInline]
    list_per_page = 50


@admin.register(AffectationEntrepot)
class AffectationEntrepotAdmin(admin.ModelAdmin):
    """
    Enregistrement standalone en plus de l'inline : utile pour retrouver
    rapidement toutes les affectations d'UNE entreprise donnée (recherche
    transverse), ce que l'inline sur Entrepot ne permet pas facilement.
    """
    list_display = ['entreprise', 'entrepot', 'est_active', 'date_affectation', 'affecte_par']
    list_filter = ['est_active']
    search_fields = ['entreprise__raison_sociale', 'entrepot__nom', 'entrepot__code']
    list_select_related = ['entreprise', 'entrepot', 'affecte_par']
    raw_id_fields = ['entreprise', 'entrepot', 'affecte_par']
    readonly_fields = ['date_affectation']