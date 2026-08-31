import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps_core.models import Utilisateur, Ville, Zone
from apps_core.choices import TypeEntreprise, QualiteProduit, CyclePaiementEntreprise
from apps_core.validators import tel_validator, niu_validator, upload_path


# ═══════════════════════════════════════════════════════════════════════
# §1 – ENTREPRISE
# ═══════════════════════════════════════════════════════════════════════

class Entreprise(models.Model):
    """
    Entreprise cliente de SwiftDrop.

    NOUVEAUTÉS :
      - type_entreprise / qualite_produits_defaut : définis à la création,
        orientent le type d'entrepôt et de véhicule par défaut.
      - cycle_paiement : rythme auquel la plateforme règle l'entreprise
        (cf. apps_transaction.LotPaiementEntreprise).
      - Gestion de l'INACTIVITÉ 30 jours : désactivation automatique +
        retour des produits en stock au propriétaire, sauf paiement
        d'une amende de gardiennage pour réactivation.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE           = 'EN_ATTENTE', _('En attente de validation')
        VALIDE                = 'VALIDE', _('Validée')
        REFUSE                = 'REFUSE', _('Refusée')
        SUSPENDU               = 'SUSPENDU', _('Suspendue (décision admin)')
        DESACTIVE_INACTIVITE   = 'DESACTIVE_INACT', _('Désactivée pour inactivité (30j)')

    class Secteur(models.TextChoices):
        COMMERCE     = 'COMMERCE', _('Commerce / Distribution')
        RESTAURATION = 'RESTAURATION', _('Restauration / Food')
        PHARMACIE    = 'PHARMACIE', _('Pharmaceutique / Santé')
        ELECTRONIQUE = 'ELECTRONIQUE', _('Électronique / High-Tech')
        MODE          = 'MODE', _('Mode / Textile')
        COSMETIQUE    = 'COSMETIQUE', _('Cosmétique / Beauté')
        AGRICULTURE   = 'AGRICULTURE', _('Agriculture / Agro-alimentaire')
        IMPRIMERIE    = 'IMPRIMERIE', _('Imprimerie / Papeterie')
        BATIMENT      = 'BATIMENT', _('Bâtiment / Matériaux')
        INFORMATIQUE  = 'INFORMATIQUE', _('Informatique / Téléphonie')
        AUTRE          = 'AUTRE', _('Autre')

    class TailleEntreprise(models.TextChoices):
        MICRO   = 'MICRO', _('Micro (1–5 employés)')
        PETITE  = 'PETITE', _('Petite (6–20 employés)')
        MOYENNE = 'MOYENNE', _('Moyenne (21–100 employés)')
        GRANDE  = 'GRANDE', _('Grande (100+ employés)')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur  = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, related_name='entreprise')
    raison_sociale = models.CharField(_('Raison sociale'), max_length=200)
    nom_commercial  = models.CharField(_('Nom commercial'), max_length=200, blank=True)
    secteur          = models.CharField(max_length=20, choices=Secteur.choices, default=Secteur.AUTRE)
    taille            = models.CharField(max_length=10, choices=TailleEntreprise.choices, default=TailleEntreprise.MICRO)

    # ── NOUVEAU : type d'activité & qualité produit par défaut ────────
    type_entreprise = models.CharField(
        _('Type d\'entreprise'), max_length=15,
        choices=TypeEntreprise.choices, default=TypeEntreprise.VENDEUR_PHYSIQUE,
        help_text=_('Détermine si l\'entreprise vend via Yopishop, en physique, ou les deux')
    )
    qualite_produits_defaut = models.CharField(
        _('Qualité produits par défaut'), max_length=10,
        choices=QualiteProduit.choices, default=QualiteProduit.LEGER,
        help_text=_('Valeur pré-remplie à la création d\'un produit ; modifiable par produit')
    )

    numero_registre         = models.CharField(_('N° Registre de Commerce'), max_length=50, blank=True, null=True)
    numero_contribuable_niu = models.CharField(_('N° Contribuable / NIU'), max_length=50, blank=True, null=True,
                                                 validators=[niu_validator])

    adresse_siege        = models.TextField(_('Adresse du siège social'))
    ville_principale      = models.ForeignKey(Ville, on_delete=models.SET_NULL, null=True, related_name='entreprises')
    zone_principale       = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='entreprises')
    telephone_principal   = models.CharField(max_length=20, validators=[tel_validator])
    telephone_secondaire  = models.CharField(max_length=20, blank=True, validators=[tel_validator])
    telephone_whatsapp    = models.CharField(max_length=20, blank=True, validators=[tel_validator])
    email_professionnel   = models.EmailField(blank=True)
    site_web               = models.URLField(blank=True)

    logo                = models.ImageField(upload_to=upload_path, blank=True, null=True)
    couleur_principale   = models.CharField(max_length=7, blank=True)

    statut               = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE, db_index=True)
    motif_refus            = models.TextField(blank=True)
    valide_par             = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                                 related_name='entreprises_validees')
    date_validation         = models.DateTimeField(null=True, blank=True)
    note_interne_admin      = models.TextField(blank=True)

    score_fiabilite = models.DecimalField(
        _('Score de fiabilité (0–100)'), max_digits=5, decimal_places=2, default=Decimal('50.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )

    zones_favorites       = models.ManyToManyField(Zone, blank=True, related_name='entreprises_favorites')
    notification_sms       = models.BooleanField(default=True)
    notification_whatsapp   = models.BooleanField(default=True)
    notification_email       = models.BooleanField(default=False)

    # ── NOUVEAU : cycle de paiement & interface dédiée ─────────────────
    cycle_paiement = models.CharField(
        _('Cycle de règlement'), max_length=15,
        choices=CyclePaiementEntreprise.choices, default=CyclePaiementEntreprise.HEBDOMADAIRE
    )
    numero_paiement_principal = models.CharField(
        _('Numéro Mobile Money / compte principal'), max_length=30, blank=True
    )

    # ── NOUVEAU : suivi d'activité & inactivité 30 jours ────────────────
    derniere_activite_livraison = models.DateTimeField(
        _('Dernière activité de livraison'), null=True, blank=True,
        help_text=_('Mis à jour à chaque nouvelle livraison créée/livrée. Sert au calcul des 30j.')
    )
    date_desactivation_inactivite = models.DateTimeField(null=True, blank=True)
    produits_retournes_proprietaire = models.BooleanField(
        _('Produits déjà retournés au propriétaire'), default=False
    )

    date_creation      = models.DateTimeField(auto_now_add=True)
    date_modification  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Entreprise')
        verbose_name_plural = _('Entreprises')
        ordering            = ['-date_creation']
        indexes = [
            models.Index(fields=['statut', 'date_creation']),
            models.Index(fields=['secteur', 'statut']),
            models.Index(fields=['score_fiabilite']),
            models.Index(fields=['derniere_activite_livraison']),
        ]

    def __str__(self):
        return f"{self.raison_sociale} [{self.get_statut_display()}]"

    @property
    def est_validee(self):
        return self.statut == self.Statut.VALIDE

    @property
    def nom_affichage(self):
        return self.nom_commercial or self.raison_sociale

    @property
    def peut_vendre_en_ligne(self):
        return self.type_entreprise in (TypeEntreprise.VENDEUR_EN_LIGNE, TypeEntreprise.MIXTE)

    @property
    def peut_vendre_hors_ligne(self):
        return self.type_entreprise in (TypeEntreprise.VENDEUR_PHYSIQUE, TypeEntreprise.MIXTE)

    # ── Workflow validation ────────────────────────────────────────────
    def valider(self, admin_user):
        self.statut = self.Statut.VALIDE
        self.valide_par = admin_user
        self.date_validation = timezone.now()
        self.motif_refus = ''
        self.save(update_fields=['statut', 'valide_par', 'date_validation', 'motif_refus'])

    def refuser(self, admin_user, motif: str):
        if not motif.strip():
            raise ValueError(_('Le motif de refus est obligatoire.'))
        self.statut = self.Statut.REFUSE
        self.valide_par = admin_user
        self.date_validation = timezone.now()
        self.motif_refus = motif
        self.save(update_fields=['statut', 'valide_par', 'date_validation', 'motif_refus'])

    def suspendre(self, admin_user, motif: str):
        if not motif.strip():
            raise ValueError(_('Le motif de suspension est obligatoire.'))
        self.statut = self.Statut.SUSPENDU
        self.valide_par = admin_user
        self.date_validation = timezone.now()
        self.motif_refus = motif
        self.save(update_fields=['statut', 'valide_par', 'date_validation', 'motif_refus'])

    # ── NOUVEAU : gestion inactivité 30 jours ──────────────────────────
    def enregistrer_activite_livraison(self):
        """À appeler à chaque création/étape de livraison pour l'entreprise."""
        self.derniere_activite_livraison = timezone.now()
        if self.statut == self.Statut.DESACTIVE_INACTIVITE:
            return  # ne réactive pas automatiquement ; réactivation = action explicite
        self.save(update_fields=['derniere_activite_livraison'])

    @property
    def jours_depuis_derniere_activite(self):
        if not self.derniere_activite_livraison:
            return None
        return (timezone.now() - self.derniere_activite_livraison).days

    def eligible_desactivation_inactivite(self, seuil_jours=30):
        if self.statut != self.Statut.VALIDE:
            return False
        jours = self.jours_depuis_derniere_activite
        return jours is not None and jours >= seuil_jours

    def desactiver_pour_inactivite(self):
        """
        Exécutée par une tâche planifiée (Celery beat / cron quotidien).
        Désactive l'entreprise et déclenche le retour des produits en stock
        au propriétaire (cf. apps_catalogue.RetourStockProprietaire).
        """
        from apps_catalogue.models import StockEntrepot, RetourStockProprietaire

        self.statut = self.Statut.DESACTIVE_INACTIVITE
        self.date_desactivation_inactivite = timezone.now()
        self.save(update_fields=['statut', 'date_desactivation_inactivite'])

        stocks = StockEntrepot.objects.filter(
            entrepot__entreprise=self, quantite_stock__gt=0
        )
        for stock in stocks:
            RetourStockProprietaire.objects.create(
                entreprise=self,
                produit=stock.produit,
                entrepot=stock.entrepot,
                quantite_retournee=stock.quantite_disponible,
                motif=RetourStockProprietaire.Motif.INACTIVITE_30_JOURS,
            )
        self.produits_retournes_proprietaire = True
        self.save(update_fields=['produits_retournes_proprietaire'])

    def reactiver_via_gardiennage(self, admin_user, frais_paye: Decimal):
        """
        L'entreprise paye une amende de frais de gardiennage pour être
        réactivée SANS retour des produits (ou pour reprendre l'activité
        après retour, selon la politique commerciale de l'admin).
        """
        frais_dus = FraisGardiennage.objects.filter(
            entreprise=self, paye=False
        ).first()
        if frais_dus and frais_paye < frais_dus.montant_du:
            raise ValueError(_('Le montant payé est inférieur au frais de gardiennage dû.'))
        if frais_dus:
            frais_dus.paye = True
            frais_dus.date_paiement = timezone.now()
            frais_dus.montant_paye = frais_paye
            frais_dus.valide_par = admin_user
            frais_dus.save()

        self.statut = self.Statut.VALIDE
        self.derniere_activite_livraison = timezone.now()
        self.save(update_fields=['statut', 'derniere_activite_livraison'])

    def recalculer_score(self):
        from apps_livraison.models import Livraison
        from apps_evaluation.models import Evaluation
        from django.db.models import Avg

        livraisons = Livraison.objects.filter(entreprise=self, statut__in=['LIVREE', 'ECHEC'])
        total = livraisons.count()
        if total == 0:
            return
        taux_succes = livraisons.filter(statut='LIVREE').count() / total
        score_succes = taux_succes * 60

        moyenne = Evaluation.objects.filter(livraison__entreprise=self).aggregate(
            m=Avg('note_globale'))['m'] or 0
        score_eval = (moyenne / 5) * 25

        jours = (timezone.now() - self.date_creation).days
        score_anciennete = min(jours / 365 * 15, 15)

        self.score_fiabilite = round(score_succes + score_eval + score_anciennete, 2)
        self.save(update_fields=['score_fiabilite'])


class FraisGardiennage(models.Model):
    """
    Amende à payer par une entreprise désactivée pour inactivité afin
    d'éviter/annuler le retour définitif des produits, ou pour réactiver
    son compte après désactivation.
    """
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entreprise    = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name='frais_gardiennage')
    montant_du     = models.DecimalField(max_digits=10, decimal_places=2)
    montant_paye   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    paye           = models.BooleanField(default=False)
    raison          = models.TextField(blank=True)
    date_creation   = models.DateTimeField(auto_now_add=True)
    date_paiement   = models.DateTimeField(null=True, blank=True)
    valide_par      = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name        = _('Frais de gardiennage')
        verbose_name_plural = _('Frais de gardiennage')
        ordering            = ['-date_creation']

    def __str__(self):
        etat = '✓' if self.paye else '⏳'
        return f"{etat} Gardiennage {self.entreprise.raison_sociale} — {self.montant_du} FCFA"


class ContactEntreprise(models.Model):
    class TypeContact(models.TextChoices):
        GERANT      = 'GERANT', _('Gérant / Propriétaire')
        RESPONSABLE = 'RESPONSABLE', _('Responsable Livraison')
        COMPTABLE   = 'COMPTABLE', _('Comptable')
        COMMERCIAL  = 'COMMERCIAL', _('Commercial')
        AUTRE        = 'AUTRE', _('Autre')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entreprise   = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name='contacts')
    type_contact = models.CharField(max_length=15, choices=TypeContact.choices)
    nom          = models.CharField(max_length=150)
    telephone    = models.CharField(max_length=20, validators=[tel_validator])
    email         = models.EmailField(blank=True)
    est_principal = models.BooleanField(default=False)

    class Meta:
        verbose_name        = _('Contact entreprise')
        verbose_name_plural = _('Contacts entreprises')
        ordering            = ['-est_principal', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.get_type_contact_display()}) – {self.entreprise.raison_sociale}"


class DocumentEntreprise(models.Model):
    class TypeDocument(models.TextChoices):
        REGISTRE_COMMERCE    = 'REGISTRE', _('Registre de Commerce')
        CARTE_NIU              = 'NIU', _('Carte Contribuable / NIU')
        PLAN_LOCALISATION      = 'PLAN', _('Plan de localisation')
        STATUTS_SOCIETE        = 'STATUTS', _('Statuts de la société')
        ATTESTATION_DOMICILE   = 'DOMICILE', _('Attestation de domicile')
        CNI_GERANT              = 'CNI', _('CNI du Gérant')
        AUTRE                    = 'AUTRE', _('Autre document')

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entreprise    = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name='documents')
    type_doc       = models.CharField(max_length=20, choices=TypeDocument.choices)
    nom_fichier     = models.CharField(max_length=255)
    fichier          = models.FileField(upload_to=upload_path,
                                          validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])])
    taille_fichier   = models.PositiveIntegerField(default=0)
    verifie           = models.BooleanField(default=False)
    verifie_par       = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='documents_verifies')
    date_verification = models.DateTimeField(null=True, blank=True)
    date_upload        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Document entreprise')
        verbose_name_plural = _('Documents entreprises')
        ordering            = ['-date_upload']

    def __str__(self):
        v = '✓' if self.verifie else '⏳'
        return f"{v} {self.get_type_doc_display()} – {self.entreprise.raison_sociale}"


# ═══════════════════════════════════════════════════════════════════════
# §2 – ENTREPÔTS (NOUVEAU)
# ═══════════════════════════════════════════════════════════════════════

class Entrepot(models.Model):
    """
    Entrepôt physique DÉFINI PAR LA PLATEFORME (créé/géré par un admin),
    dans lequel une ou plusieurs entreprises stockent leurs produits.
    Le stock réel par produit est géré individuellement dans
    apps_catalogue.StockEntrepot (relation produit × entrepôt).
    """
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom          = models.CharField(_('Nom de l\'entrepôt'), max_length=150)
    code          = models.CharField(_('Code entrepôt'), max_length=15, unique=True)
    ville         = models.ForeignKey(Ville, on_delete=models.PROTECT, related_name='entrepots')
    zone          = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='entrepots')
    adresse        = models.TextField()
    latitude       = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude      = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    capacite_m3      = models.DecimalField(_('Capacité (m³)'), max_digits=10, decimal_places=2, blank=True, null=True)
    gere_produits_froid = models.BooleanField(_('Dispose d\'une chambre froide'), default=False)
    gere_produits_lourds = models.BooleanField(_('Adapté aux produits lourds/volumineux'), default=False)

    responsable    = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='entrepots_geres',
                                         help_text=_('Admin/agent responsable de l\'entrepôt'))
    entreprises     = models.ManyToManyField(
        Entreprise, blank=True, related_name='entrepots',
        through='AffectationEntrepot',
        help_text=_('Entreprises autorisées à stocker dans cet entrepôt (assignation plateforme)')
    )

    est_actif       = models.BooleanField(default=True)
    date_creation    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Entrepôt')
        verbose_name_plural = _('Entrepôts')
        ordering            = ['ville', 'nom']
        indexes             = [models.Index(fields=['ville', 'est_actif'])]

    def __str__(self):
        return f"{self.nom} [{self.code}] – {self.ville.nom}"


class AffectationEntrepot(models.Model):
    """
    Table de liaison Entreprise ↔ Entrepôt : c'est la PLATEFORME qui
    affecte une entreprise à un ou plusieurs entrepôts (jamais l'inverse).
    """
    entreprise   = models.ForeignKey(Entreprise, on_delete=models.CASCADE)
    entrepot      = models.ForeignKey(Entrepot, on_delete=models.CASCADE)
    affecte_par   = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True,
                                        related_name='affectations_entrepot_realisees')
    date_affectation = models.DateTimeField(auto_now_add=True)
    est_active        = models.BooleanField(default=True)

    class Meta:
        verbose_name        = _('Affectation entrepôt')
        verbose_name_plural = _('Affectations entrepôts')
        unique_together     = [['entreprise', 'entrepot']]

    def __str__(self):
        return f"{self.entreprise.nom_affichage} → {self.entrepot.nom}"
