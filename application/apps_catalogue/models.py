import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps_core.models import Utilisateur
from apps_core.choices import TypeVehicule, QualiteProduit
from apps_core.validators import upload_path
from apps_entreprise.models import Entreprise, Entrepot


class Categorie(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent      = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='sous_categories')
    nom         = models.CharField(max_length=100)
    slug        = models.SlugField(max_length=120, unique=True)
    icone       = models.CharField(max_length=60, blank=True)
    couleur     = models.CharField(max_length=7, blank=True)
    description = models.TextField(blank=True)
    ordre       = models.PositiveSmallIntegerField(default=0)
    est_active  = models.BooleanField(default=True)

    class Meta:
        verbose_name        = _('Catégorie')
        verbose_name_plural = _('Catégories')
        ordering            = ['ordre', 'nom']

    def __str__(self):
        return f"{self.parent.nom} › {self.nom}" if self.parent else self.nom


class Produit(models.Model):
    """
    Produit stocké par une entreprise.

    NOUVEAUTÉS CLÉS :
      - vendu_en_ligne : True si Yopishop gère effectivement la vente ET
        la livraison de ce produit (sinon, c'est un produit hors-ligne,
        même si l'entreprise vend aussi en ligne par ailleurs).
      - qualite_produit / vehicule_minimum_requis : déterminent la
        majoration des frais de livraison (moto / voiture / camionnette…).
      - Le STOCK N'EST PLUS SUR CE MODÈLE : il est réparti individuellement
        par entrepôt via StockEntrepot (un produit peut être stocké dans
        plusieurs entrepôts, chacun avec sa propre quantité).
    """

    class StatutProduit(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', _('En attente de validation entreprise')
        VALIDE      = 'VALIDE', _('Validé')
        REFUSE       = 'REFUSE', _('Refusé par l\'entreprise')
        EPUISE        = 'EPUISE', _('Stock épuisé (tous entrepôts)')
        ARCHIVE        = 'ARCHIVE', _('Archivé')

    class Unite(models.TextChoices):
        PIECE = 'PIECE', _('Pièce(s)')
        KG    = 'KG', _('Kilogramme(s)')
        GRAMME = 'GRAMME', _('Gramme(s)')
        LITRE = 'LITRE', _('Litre(s)')
        ML    = 'ML', _('Millilitre(s)')
        CARTON = 'CARTON', _('Carton(s)')
        SACHET = 'SACHET', _('Sachet(s)')
        BOUTEILLE = 'BOUTEILLE', _('Bouteille(s)')
        BOITE = 'BOITE', _('Boîte(s)')
        PALETTE = 'PALETTE', _('Palette(s)')
        METRE = 'METRE', _('Mètre(s)')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entreprise    = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name='produits')
    categorie      = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True, blank=True, related_name='produits')
    nom             = models.CharField(max_length=200)
    reference_sku    = models.CharField(max_length=60, blank=True)
    code_barre        = models.CharField(max_length=50, blank=True)
    description        = models.TextField(blank=True)

    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2,
                                          validators=[MinValueValidator(Decimal('0.00'))])
    unite          = models.CharField(max_length=15, choices=Unite.choices, default=Unite.PIECE)
    seuil_alerte_defaut  = models.PositiveIntegerField(_('Seuil d\'alerte par défaut (par entrepôt)'), default=5)
    seuil_rupture_defaut = models.PositiveIntegerField(_('Seuil de rupture par défaut (par entrepôt)'), default=0)

    # ── NOUVEAU : vente en ligne Yopishop ──────────────────────────────
    vendu_en_ligne = models.BooleanField(
        _('Vendu en ligne (Yopishop gère la vente ET la livraison)'), default=False,
        help_text=_(
            'Cocher UNIQUEMENT si Yopishop gère la livraison de ce produit. '
            'Sinon, même si l\'entreprise vend par ailleurs en ligne, '
            'le produit reste "hors-ligne" pour le calcul des frais.'
        )
    )
    reference_yopishop = models.CharField(
        _('Référence produit Yopishop'), max_length=100, blank=True,
        help_text=_('ID/SKU utilisé pour la synchronisation avec Yopishop')
    )

    # ── NOUVEAU : qualité & véhicule requis (impacte les frais) ────────
    qualite_produit = models.CharField(
        _('Qualité du produit'), max_length=10,
        choices=QualiteProduit.choices, default=QualiteProduit.LEGER,
        help_text=_('LEGER = transportable en moto ; LOURD = véhicule requis')
    )
    vehicule_minimum_requis = models.CharField(
        _('Véhicule minimum requis'), max_length=15,
        choices=TypeVehicule.choices, default=TypeVehicule.MOTO,
        help_text=_('Utilisé pour calculer la majoration des frais de livraison')
    )

    poids_kg     = models.DecimalField(max_digits=8, decimal_places=3, blank=True, null=True)
    longueur_cm  = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    largeur_cm   = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    hauteur_cm   = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    fragile       = models.BooleanField(default=False)
    necessite_froid = models.BooleanField(default=False)

    photo_principale = models.ImageField(upload_to=upload_path, blank=True, null=True)

    statut         = models.CharField(max_length=15, choices=StatutProduit.choices,
                                        default=StatutProduit.EN_ATTENTE, db_index=True)
    motif_refus     = models.TextField(blank=True)
    enregistre_par   = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True,
                                           related_name='produits_enregistres')
    valide_par        = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='produits_valides')
    date_validation    = models.DateTimeField(null=True, blank=True)
    date_creation       = models.DateTimeField(auto_now_add=True)
    date_modification    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Produit')
        verbose_name_plural = _('Produits')
        ordering            = ['entreprise', 'nom']
        indexes = [
            models.Index(fields=['statut', 'entreprise']),
            models.Index(fields=['vendu_en_ligne', 'statut']),
            models.Index(fields=['reference_sku']),
        ]

    def __str__(self):
        tag = 'EN LIGNE' if self.vendu_en_ligne else 'HORS-LIGNE'
        return f"{self.nom} | {self.entreprise.raison_sociale} | [{tag}] | Stock total: {self.stock_total_disponible}"

    # ── Agrégats sur tous les entrepôts ─────────────────────────────────
    @property
    def stock_total_disponible(self):
        agg = self.stocks_entrepots.aggregate(
            total=models.Sum(models.F('quantite_stock') - models.F('quantite_reservee'))
        )
        return max(0, agg['total'] or 0)

    @property
    def en_rupture_globale(self):
        return self.stock_total_disponible <= self.seuil_rupture_defaut

    @property
    def valeur_stock_total(self):
        agg = self.stocks_entrepots.aggregate(total=models.Sum('quantite_stock'))
        return (agg['total'] or 0) * self.prix_unitaire

    def valider(self, utilisateur):
        self.statut = self.StatutProduit.VALIDE
        self.valide_par = utilisateur
        self.date_validation = timezone.now()
        self.motif_refus = ''
        self.save(update_fields=['statut', 'valide_par', 'date_validation', 'motif_refus'])

    def refuser(self, utilisateur, motif: str):
        if not motif.strip():
            raise ValueError(_('Le motif de refus est obligatoire.'))
        self.statut = self.StatutProduit.REFUSE
        self.valide_par = utilisateur
        self.date_validation = timezone.now()
        self.motif_refus = motif
        self.save(update_fields=['statut', 'valide_par', 'date_validation', 'motif_refus'])


class PhotoProduit(models.Model):
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    produit  = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='photos')
    photo     = models.ImageField(upload_to=upload_path)
    legende    = models.CharField(max_length=200, blank=True)
    ordre       = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = _('Photo produit')
        verbose_name_plural = _('Photos produits')
        ordering            = ['ordre']

    def __str__(self):
        return f"Photo {self.ordre} – {self.produit.nom}"


# ═══════════════════════════════════════════════════════════════════════
# STOCK PAR ENTREPÔT (NOUVEAU — remplace le stock unique sur Produit)
# ═══════════════════════════════════════════════════════════════════════

class StockEntrepot(models.Model):
    """
    Quantité d'un PRODUIT donné dans UN ENTREPÔT donné.
    Un même produit peut avoir des lignes différentes dans plusieurs
    entrepôts — chaque ligne est gérée individuellement (son propre
    seuil d'alerte, ses propres réservations, son propre historique).
    """
    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    produit            = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='stocks_entrepots')
    entrepot            = models.ForeignKey(Entrepot, on_delete=models.PROTECT, related_name='stocks_produits')
    quantite_stock       = models.PositiveIntegerField(default=0)
    quantite_reservee     = models.PositiveIntegerField(default=0)
    seuil_alerte           = models.PositiveIntegerField(default=5)
    seuil_rupture           = models.PositiveIntegerField(default=0)
    emplacement_precis       = models.CharField(_('Emplacement (allée/rayon)'), max_length=50, blank=True)
    date_creation             = models.DateTimeField(auto_now_add=True)
    date_modification          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Stock par entrepôt')
        verbose_name_plural = _('Stocks par entrepôt')
        unique_together     = [['produit', 'entrepot']]
        indexes = [
            models.Index(fields=['entrepot', 'produit']),
            models.Index(fields=['quantite_stock', 'seuil_alerte']),
        ]

    def __str__(self):
        return f"{self.produit.nom} @ {self.entrepot.nom} : {self.quantite_disponible} dispo"

    @property
    def quantite_disponible(self):
        return max(0, self.quantite_stock - self.quantite_reservee)

    @property
    def stock_bas(self):
        return 0 < self.quantite_disponible <= self.seuil_alerte

    @property
    def en_rupture(self):
        return self.quantite_disponible <= self.seuil_rupture

    def reserver(self, quantite: int, effectue_par=None, livraison=None):
        if quantite > self.quantite_disponible:
            raise ValueError(_(f'Stock insuffisant dans {self.entrepot.nom}. Disponible : {self.quantite_disponible}'))
        self.quantite_reservee += quantite
        self.save(update_fields=['quantite_reservee'])

    def liberer_reservation(self, quantite: int):
        self.quantite_reservee = max(0, self.quantite_reservee - quantite)
        self.save(update_fields=['quantite_reservee'])

    def decrementer_stock(self, quantite: int, effectue_par=None, livraison=None, note=''):
        """Sortie définitive du stock après livraison effectuée."""
        avant = self.quantite_stock
        self.quantite_stock = max(0, self.quantite_stock - quantite)
        self.quantite_reservee = max(0, self.quantite_reservee - quantite)
        self.save(update_fields=['quantite_stock', 'quantite_reservee'])

        MouvementStock.objects.create(
            stock_entrepot=self,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE_LIVRAISON,
            quantite=-quantite,
            stock_avant=avant,
            stock_apres=self.quantite_stock,
            effectue_par=effectue_par,
            livraison=livraison,
            note=note,
        )
        self._verifier_alertes()
        if self.produit.stock_total_disponible <= self.produit.seuil_rupture_defaut:
            self.produit.statut = Produit.StatutProduit.EPUISE
            self.produit.save(update_fields=['statut'])

    def _verifier_alertes(self):
        if self.en_rupture:
            AlerteStock.objects.get_or_create(
                stock_entrepot=self, type_alerte=AlerteStock.TypeAlerte.RUPTURE, traitee=False,
                defaults={'quantite_au_moment': self.quantite_disponible}
            )
        elif self.stock_bas:
            AlerteStock.objects.get_or_create(
                stock_entrepot=self, type_alerte=AlerteStock.TypeAlerte.STOCK_BAS, traitee=False,
                defaults={'quantite_au_moment': self.quantite_disponible}
            )


class MouvementStock(models.Model):
    class TypeMouvement(models.TextChoices):
        ENTREE_INITIAL   = 'ENTREE_INIT', _('Entrée initiale (enregistrement)')
        ENTREE_REAPPRO   = 'ENTREE_REAPP', _('Réapprovisionnement')
        TRANSFERT_ENTREPOT = 'TRANSFERT', _('Transfert entre entrepôts')
        SORTIE_LIVRAISON  = 'SORTIE_LIV', _('Sortie pour livraison')
        RETOUR_LIVRAISON  = 'RETOUR_LIV', _('Retour de livraison (échec)')
        RETOUR_PROPRIETAIRE = 'RETOUR_PROP', _('Retour au propriétaire (inactivité)')
        AJUSTEMENT_PLUS   = 'AJUST_PLUS', _('Ajustement positif (inventaire)')
        AJUSTEMENT_MOINS  = 'AJUST_MOINS', _('Ajustement négatif (inventaire)')
        PERTE              = 'PERTE', _('Perte / Casse / Vol')
        PEREMPTION          = 'PEREMPTION', _('Péremption / Retrait')

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_entrepot     = models.ForeignKey(StockEntrepot, on_delete=models.CASCADE, related_name='mouvements')
    type_mouvement       = models.CharField(max_length=20, choices=TypeMouvement.choices, db_index=True)
    quantite               = models.IntegerField(help_text=_('Positif = entrée, Négatif = sortie'))
    stock_avant              = models.PositiveIntegerField()
    stock_apres               = models.PositiveIntegerField()
    cout_unitaire               = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    note                          = models.TextField(blank=True)
    effectue_par                   = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True,
                                                          related_name='mouvements_stock')
    livraison                       = models.ForeignKey('apps_livraison.Livraison', on_delete=models.SET_NULL,
                                                           null=True, blank=True, related_name='mouvements_stock')
    date                              = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = _('Mouvement de stock')
        verbose_name_plural = _('Mouvements de stock')
        ordering            = ['-date']
        indexes = [
            models.Index(fields=['stock_entrepot', 'date']),
            models.Index(fields=['type_mouvement', 'date']),
        ]

    def __str__(self):
        signe = '+' if self.quantite > 0 else ''
        return (f"[{self.get_type_mouvement_display()}] {self.stock_entrepot.produit.nom} : "
                f"{signe}{self.quantite} ({self.stock_avant}→{self.stock_apres})")


class AlerteStock(models.Model):
    class TypeAlerte(models.TextChoices):
        STOCK_BAS = 'BAS', _('Stock bas (seuil alerte atteint)')
        RUPTURE    = 'RUPTURE', _('Rupture de stock')

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_entrepot     = models.ForeignKey(StockEntrepot, on_delete=models.CASCADE, related_name='alertes')
    type_alerte           = models.CharField(max_length=10, choices=TypeAlerte.choices)
    quantite_au_moment      = models.PositiveIntegerField()
    traitee                   = models.BooleanField(default=False)
    traitee_par                = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True)
    date                         = models.DateTimeField(auto_now_add=True)
    date_traitement                = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = _('Alerte stock')
        verbose_name_plural = _('Alertes stock')
        ordering            = ['-date']

    def __str__(self):
        return f"[{self.get_type_alerte_display()}] {self.stock_entrepot.produit.nom} @ {self.stock_entrepot.entrepot.nom}"


class RetourStockProprietaire(models.Model):
    """
    Trace un retour de produits au propriétaire (entreprise) suite à une
    désactivation pour inactivité (30 jours sans activité de livraison).
    """
    class Motif(models.TextChoices):
        INACTIVITE_30_JOURS = 'INACTIVITE', _('Inactivité 30 jours')
        DEMANDE_ENTREPRISE   = 'DEMANDE', _('Demande de l\'entreprise')
        FERMETURE_ENTREPOT    = 'FERMETURE', _('Fermeture de l\'entrepôt')

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entreprise           = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name='retours_stock')
    produit               = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='retours_stock')
    entrepot                = models.ForeignKey(Entrepot, on_delete=models.SET_NULL, null=True)
    quantite_retournee        = models.PositiveIntegerField()
    motif                       = models.CharField(max_length=15, choices=Motif.choices)
    confirme_retire_par_entreprise = models.BooleanField(default=False)
    date_creation                    = models.DateTimeField(auto_now_add=True)
    date_confirmation                  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = _('Retour de stock au propriétaire')
        verbose_name_plural = _('Retours de stock aux propriétaires')
        ordering            = ['-date_creation']

    def __str__(self):
        return f"Retour {self.quantite_retournee}× {self.produit.nom} → {self.entreprise.raison_sociale}"
