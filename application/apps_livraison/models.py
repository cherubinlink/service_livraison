import uuid
import secrets
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps_core.models import Utilisateur, Ville, Zone, Quartier, ParametreSysteme, TarifInterVille
from apps_core.choices import (
    TypeVehicule, OrigineCommande, TypeFacturationLivraison, StatutReceptionLivraison
)
from apps_core.validators import tel_validator, upload_path
from apps_entreprise.models import Entreprise
from apps_catalogue.models import Produit, StockEntrepot
from apps_livreur.models import Livreur


# ═══════════════════════════════════════════════════════════════════════
# §1 – LIVRAISON B2B (multi-produits)
# ═══════════════════════════════════════════════════════════════════════

class Livraison(models.Model):
    """
    Livraison B2B — EN-TÊTE de commande, pouvant contenir PLUSIEURS
    produits (cf. LigneLivraison), comme une commande e-commerce classique.

    ┌────────────────────────────────────────────────────────────────┐
    │ CYCLE DE VIE                                                    │
    │ BROUILLON → EN_ATTENTE → VALIDEE → EN_COURS → LIVREE ✅        │
    │                       ↘ REFUSEE                  ↘ ECHEC ❌    │
    │ ANNULEE (possible avant VALIDEE)                                │
    │ Puis, côté entreprise :                                         │
    │ INFOS_ENVOYEES → RECEPTION_VALIDEE → PAIEMENT_ATTENTE →         │
    │ PAIEMENT_RECU  (cf. statut_reception, distinct du statut livraison)
    └────────────────────────────────────────────────────────────────┘

    ┌────────────────────────────────────────────────────────────────┐
    │ RÈGLES DE FACTURATION DES FRAIS DE LIVRAISON (fixées)          │
    │                                                                  │
    │ • Tous les produits de la commande sont VENDUS EN LIGNE         │
    │   (Yopishop gère la livraison) :                                │
    │     → frais de livraison GRATUITS pour le client                │
    │     → commission Yopishop (ex: 10%) déduite du montant produits │
    │                                                                  │
    │ • Tous les produits sont HORS-LIGNE :                           │
    │     → frais de livraison facturés selon la ZONE + le VÉHICULE   │
    │       requis (le plus exigeant parmi les produits de la ligne)  │
    │                                                                  │
    │ • Commande MIXTE (au moins 1 produit en ligne + 1 hors-ligne,   │
    │   quel que soit le nombre de chaque) :                          │
    │     → on facture UNIQUEMENT les frais de livraison selon la     │
    │       zone (pas de commission calculée sur la part en ligne).   │
    │       Décision volontairement simplifiée — voir consignes       │
    │       métier ; ne pas complexifier ce cas.                      │
    └────────────────────────────────────────────────────────────────┘

    ┌────────────────────────────────────────────────────────────────┐
    │ PAIEMENT DES FRAIS PAR LE CLIENT (constaté par le livreur)      │
    │                                                                  │
    │ • Rien payé      → frais entièrement déduits du gain entreprise │
    │ • Payé en totalité → aucune déduction sur le gain entreprise    │
    │ • Payé partiellement → seul le RESTANT DÛ est déduit            │
    └────────────────────────────────────────────────────────────────┘
    """

    class Statut(models.TextChoices):
        BROUILLON  = 'BROUILLON', _('Brouillon (non soumis)')
        EN_ATTENTE = 'EN_ATTENTE', _('En attente de validation admin')
        VALIDEE     = 'VALIDEE', _('Validée par admin')
        REFUSEE      = 'REFUSEE', _('Refusée par admin')
        EN_COURS      = 'EN_COURS', _('En cours de livraison')
        LIVREE          = 'LIVREE', _('Livrée avec succès ✅')
        ECHEC             = 'ECHEC', _('Échec de livraison ❌')
        ANNULEE            = 'ANNULEE', _('Annulée')

    class Priorite(models.TextChoices):
        NORMALE = 'NORMALE', _('Normale (24–48h)')
        URGENTE  = 'URGENTE', _('Urgente (4–8h) +frais')
        PREMIUM   = 'PREMIUM', _('Premium (même jour) +frais')

    class ModeEncaissement(models.TextChoices):
        PAIEMENT_LIVRAISON = 'A_LA_LIVRAISON', _('Paiement à la livraison')
        DEJA_PAYE            = 'DEJA_PAYE', _('Déjà payé par le client')
        VIREMENT               = 'VIREMENT', _('Virement / Mobile Money')

    # ── Identifiant & traçabilité ────────────────────────────────────
    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero   = models.CharField(max_length=25, unique=True, blank=True,
                                  help_text=_('Généré auto : SD-YYYYMMDD-XXXX'))

    # ── Origine de la commande (NOUVEAU) ─────────────────────────────
    origine_commande = models.CharField(
        _('Origine de la commande'), max_length=15,
        choices=OrigineCommande.choices,
        help_text=_(
            'YOPISHOP : commande passée en ligne, réceptionnée en 1er par la plateforme. '
            'ENTREPRISE : demande envoyée directement par l\'entreprise à la plateforme.'
        )
    )

    # ── Acteurs ───────────────────────────────────────────────────────
    entreprise    = models.ForeignKey(Entreprise, on_delete=models.PROTECT, related_name='livraisons')
    cree_par       = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True,
                                         related_name='livraisons_creees')
    valide_par      = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='livraisons_validees')
    livreur           = models.ForeignKey(Livreur, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='livraisons_attribuees')
    attribue_par        = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                              related_name='livraisons_attribuees_par')

    # ── Destination & client ─────────────────────────────────────────
    ville_livraison       = models.ForeignKey(Ville, on_delete=models.PROTECT)
    zone_livraison         = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name='livraisons')
    quartier_livraison       = models.ForeignKey(Quartier, on_delete=models.SET_NULL, null=True, blank=True,
                                                   related_name='livraisons')
    adresse_exacte             = models.TextField()
    coordonnees_livraison_lat    = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    coordonnees_livraison_lng    = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    nom_client         = models.CharField(max_length=150)
    telephone_client     = models.CharField(max_length=20, validators=[tel_validator])
    telephone_client_2     = models.CharField(max_length=20, blank=True, validators=[tel_validator])
    email_client              = models.EmailField(blank=True)

    priorite              = models.CharField(max_length=10, choices=Priorite.choices, default=Priorite.NORMALE)
    mode_encaissement       = models.CharField(max_length=20, choices=ModeEncaissement.choices,
                                                 default=ModeEncaissement.PAIEMENT_LIVRAISON)
    montant_a_encaisser        = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    note_livreur                  = models.TextField(blank=True)

    statut               = models.CharField(max_length=15, choices=Statut.choices,
                                              default=Statut.EN_ATTENTE, db_index=True)
    motif_refus            = models.TextField(blank=True)
    motif_echec               = models.TextField(blank=True)

    # ── NOUVEAU : workflow de réception distinct côté entreprise ──────
    statut_reception = models.CharField(
        _('Statut de réception (côté entreprise)'), max_length=20,
        choices=StatutReceptionLivraison.choices,
        default=StatutReceptionLivraison.EN_ATTENTE_LIVRAISON,
        help_text=_(
            'YOPISHOP : la plateforme réceptionne/traite la commande, l\'entreprise '
            'valide juste la réception après livraison. ENTREPRISE : l\'entreprise suit '
            'chaque étape (attribution, en cours, livrée) puis valide la réception.'
        )
    )
    date_validation_reception = models.DateTimeField(null=True, blank=True)
    valide_reception_par        = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                                       related_name='livraisons_reception_validees')

    # ── Dates & timeline ───────────────────────────────────────────────
    date_creation             = models.DateTimeField(auto_now_add=True, db_index=True)
    date_soumission             = models.DateTimeField(null=True, blank=True)
    date_validation                = models.DateTimeField(null=True, blank=True)
    date_attribution                  = models.DateTimeField(null=True, blank=True)
    date_prise_en_charge                = models.DateTimeField(null=True, blank=True)
    date_livraison_effective              = models.DateTimeField(null=True, blank=True)
    date_souhaitee                          = models.DateField(null=True, blank=True)

    # ── NOUVEAU : véhicule requis (calculé depuis les lignes) ──────────
    vehicule_requis = models.CharField(
        _('Véhicule minimum requis (auto-calculé)'), max_length=15,
        choices=TypeVehicule.choices, default=TypeVehicule.MOTO
    )

    # ── NOUVEAU : type de facturation & flags produits ─────────────────
    type_facturation      = models.CharField(
        max_length=15, choices=TypeFacturationLivraison.choices,
        default=TypeFacturationLivraison.FACTUREE_ZONE
    )
    contient_produit_en_ligne  = models.BooleanField(default=False)
    contient_produit_hors_ligne  = models.BooleanField(default=False)

    # ── Financier ────────────────────────────────────────────────────
    montant_total_produits   = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    frais_livraison_base_zone  = models.DecimalField(
        _('Frais zone (avant majoration véhicule) FCFA'),
        max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    frais_livraison_applique      = models.DecimalField(
        _('Frais de livraison finaux appliqués (FCFA)'),
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text=_('0 si type_facturation = GRATUITE_COMMISSION')
    )
    commission_yopishop_pct         = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10.00'),
        help_text=_('Pourcentage prélevé par la plateforme sur le montant produits (cas 100% en ligne)')
    )
    commission_yopishop_montant       = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # ── NOUVEAU : paiement des frais par le client (constaté livreur) ──
    frais_livraison_paye_par_client       = models.DecimalField(
        _('Montant des frais payé par le client (constaté livreur)'),
        max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    frais_livraison_paye_integralement       = models.BooleanField(default=False)
    frais_livraison_signale_par                = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='frais_livraison_signales', help_text=_('Le livreur qui a constaté le paiement')
    )
    date_signalement_frais                       = models.DateTimeField(null=True, blank=True)

    gain_entreprise          = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text=_('Montant net dû à l\'entreprise après déduction des frais/commission non couverts')
    )
    bonus_applique               = models.ForeignKey('apps_bonus.BonusEntreprise', on_delete=models.SET_NULL,
                                                        null=True, blank=True, related_name='livraisons_concernees')
    reduction_bonus                = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # ── Preuve de livraison ─────────────────────────────────────────────
    photo_preuve                = models.ImageField(upload_to=upload_path, blank=True, null=True)
    signature_client_img           = models.ImageField(upload_to=upload_path, blank=True, null=True)
    code_confirmation                 = models.CharField(max_length=4, blank=True)
    confirmation_recu                    = models.BooleanField(default=False)

    class Meta:
        verbose_name        = _('Livraison B2B')
        verbose_name_plural = _('Livraisons B2B')
        ordering            = ['-date_creation']
        indexes = [
            models.Index(fields=['statut', 'entreprise']),
            models.Index(fields=['numero']),
            models.Index(fields=['statut', 'date_creation']),
            models.Index(fields=['livreur', 'statut']),
            models.Index(fields=['origine_commande', 'statut_reception']),
        ]

    def __str__(self):
        return f"{self.numero} → {self.nom_client} [{self.get_statut_display()}]"

    # ── Génération numéro ─────────────────────────────────────────────
    def save(self, *args, **kwargs):
        if not self.numero:
            today = timezone.now().strftime('%Y%m%d')
            count = Livraison.objects.filter(numero__startswith=f'SD-{today}-').count()
            self.numero = f'SD-{today}-{str(count + 1).zfill(4)}'
        super().save(*args, **kwargs)

    # ── Construction / recalcul depuis les lignes ──────────────────────
    def recalculer_depuis_lignes(self):
        """
        À appeler après ajout/suppression de LigneLivraison.
        Détermine : montant total produits, mixité en ligne/hors-ligne,
        véhicule requis (le plus exigeant), et le type de facturation.
        """
        lignes = list(self.lignes.select_related('produit'))
        if not lignes:
            return

        self.montant_total_produits = sum(l.montant_ligne for l in lignes)
        self.contient_produit_en_ligne = any(l.vendu_en_ligne_snapshot for l in lignes)
        self.contient_produit_hors_ligne = any(not l.vendu_en_ligne_snapshot for l in lignes)

        # Véhicule requis = le plus exigeant parmi toutes les lignes
        ordre = [TypeVehicule.VELO, TypeVehicule.MOTO, TypeVehicule.TRICYCLE,
                 TypeVehicule.VOITURE, TypeVehicule.CAMIONNETTE, TypeVehicule.CAMION]
        vehicules = [l.vehicule_requis_snapshot for l in lignes]
        self.vehicule_requis = max(vehicules, key=lambda v: ordre.index(v)) if vehicules else TypeVehicule.MOTO

        # Type de facturation : voir docstring de la classe
        if self.contient_produit_en_ligne and not self.contient_produit_hors_ligne:
            self.type_facturation = TypeFacturationLivraison.GRATUITE_COMMISSION
        else:
            # 100% hors-ligne OU mixte -> facturation zone uniquement
            self.type_facturation = TypeFacturationLivraison.FACTUREE_ZONE

        self.save(update_fields=[
            'montant_total_produits', 'contient_produit_en_ligne', 'contient_produit_hors_ligne',
            'vehicule_requis', 'type_facturation'
        ])
        self.calculer_frais_et_gains()

    def calculer_frais_et_gains(self):
        """
        Calcule frais_livraison_applique, commission_yopishop_montant et
        gain_entreprise selon le type_facturation et l'état de paiement
        des frais par le client.
        """
        if self.type_facturation == TypeFacturationLivraison.GRATUITE_COMMISSION:
            self.frais_livraison_base_zone = Decimal('0.00')
            self.frais_livraison_applique = Decimal('0.00')
            pct = self.commission_yopishop_pct / Decimal('100')
            self.commission_yopishop_montant = (self.montant_total_produits * pct).quantize(Decimal('0.01'))
            self.gain_entreprise = self.montant_total_produits - self.commission_yopishop_montant
        else:
            base = self.zone_livraison.get_prix_pour_vehicule(self.vehicule_requis)
            self.frais_livraison_base_zone = base
            self.frais_livraison_applique = (base - self.reduction_bonus).quantize(Decimal('0.01'))
            self.commission_yopishop_montant = Decimal('0.00')

            # Application des règles de paiement partiel/total du client
            frais_deja_payes = self.frais_livraison_paye_par_client
            if self.frais_livraison_paye_integralement or frais_deja_payes >= self.frais_livraison_applique:
                reste_a_deduire = Decimal('0.00')
            else:
                reste_a_deduire = self.frais_livraison_applique - frais_deja_payes

            self.gain_entreprise = self.montant_total_produits - reste_a_deduire

        if self.mode_encaissement == self.ModeEncaissement.PAIEMENT_LIVRAISON:
            self.montant_a_encaisser = self.montant_total_produits

        self.save(update_fields=[
            'frais_livraison_base_zone', 'frais_livraison_applique',
            'commission_yopishop_montant', 'gain_entreprise', 'montant_a_encaisser'
        ])

    # ── NOUVEAU : signalement du paiement des frais par le livreur ─────
    def signaler_paiement_frais_client(self, livreur_utilisateur, montant_paye: Decimal, integralite: bool):
        """
        Le livreur constate sur le terrain que le client a payé tout ou
        partie des frais de livraison (en plus/au lieu du prix produit).
        """
        self.frais_livraison_paye_par_client = montant_paye
        self.frais_livraison_paye_integralement = integralite
        self.frais_livraison_signale_par = livreur_utilisateur
        self.date_signalement_frais = timezone.now()
        self.save(update_fields=[
            'frais_livraison_paye_par_client', 'frais_livraison_paye_integralement',
            'frais_livraison_signale_par', 'date_signalement_frais'
        ])
        self.calculer_frais_et_gains()

    # ── Workflow statut livraison ────────────────────────────────────
    def changer_statut(self, nouveau_statut, utilisateur, commentaire='', **kwargs):
        statut_avant = self.statut
        self.statut = nouveau_statut
        now = timezone.now()
        dates_map = {
            self.Statut.EN_ATTENTE: 'date_soumission',
            self.Statut.VALIDEE: 'date_validation',
            self.Statut.REFUSEE: 'date_validation',
            self.Statut.EN_COURS: 'date_prise_en_charge',
            self.Statut.LIVREE: 'date_livraison_effective',
            self.Statut.ECHEC: 'date_livraison_effective',
        }
        if nouveau_statut in dates_map:
            setattr(self, dates_map[nouveau_statut], now)

        if nouveau_statut == self.Statut.VALIDEE:
            self.valide_par = utilisateur
        if nouveau_statut == self.Statut.REFUSEE:
            self.valide_par = utilisateur
            self.motif_refus = kwargs.get('motif', '')
        if nouveau_statut == self.Statut.ECHEC:
            self.motif_echec = kwargs.get('motif', '')

        if nouveau_statut == self.Statut.LIVREE:
            # Décrémente le stock de chaque ligne + met à jour la réception
            for ligne in self.lignes.select_related('stock_entrepot'):
                if ligne.stock_entrepot:
                    ligne.stock_entrepot.decrementer_stock(
                        ligne.quantite, effectue_par=utilisateur, livraison=self
                    )
            self.statut_reception = StatutReceptionLivraison.LIVREE_INFOS_ENVOYEES
            self.entreprise.enregistrer_activite_livraison()

        self.save()

        HistoriqueStatutLivraison.objects.create(
            livraison=self, statut_avant=statut_avant, statut_apres=nouveau_statut,
            commentaire=commentaire, effectue_par=utilisateur,
            latitude=kwargs.get('latitude'), longitude=kwargs.get('longitude'),
        )

    # ── Workflow réception entreprise (distinct pour Yopishop/Entreprise) ─
    def valider_reception_entreprise(self, utilisateur_entreprise):
        """
        L'entreprise valide avoir bien reçu les informations de livraison
        (produit livré au client). Passe ensuite en attente de paiement
        du prochain lot (cf. apps_transaction.LotPaiementEntreprise).
        """
        if self.statut != self.Statut.LIVREE:
            raise ValueError(_('La livraison doit être au statut LIVREE avant validation de réception.'))
        self.statut_reception = StatutReceptionLivraison.RECEPTION_VALIDEE
        self.date_validation_reception = timezone.now()
        self.valide_reception_par = utilisateur_entreprise
        self.save(update_fields=['statut_reception', 'date_validation_reception', 'valide_reception_par'])

    def generer_code_confirmation(self):
        import random
        self.code_confirmation = str(random.randint(1000, 9999))
        self.save(update_fields=['code_confirmation'])
        return self.code_confirmation

    @property
    def delai_livraison_minutes(self):
        if self.date_livraison_effective and self.date_soumission:
            return int((self.date_livraison_effective - self.date_soumission).total_seconds() / 60)
        return None


class LigneLivraison(models.Model):
    """
    Ligne de commande : UN produit, UNE quantité, dans une Livraison
    pouvant en contenir plusieurs (commande multi-produits).
    Le snapshot fige le prix ET le statut "vendu en ligne" au moment
    de la commande (un produit peut changer de statut plus tard sans
    impacter les commandes déjà passées).
    """
    id                     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    livraison               = models.ForeignKey(Livraison, on_delete=models.CASCADE, related_name='lignes')
    produit                   = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name='lignes_livraison')
    stock_entrepot              = models.ForeignKey(
        StockEntrepot, on_delete=models.PROTECT, related_name='lignes_livraison',
        help_text=_('Entrepôt précis d\'où le produit est prélevé')
    )
    quantite                       = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    prix_unitaire_snapshot            = models.DecimalField(max_digits=12, decimal_places=2)
    vendu_en_ligne_snapshot              = models.BooleanField(default=False)
    vehicule_requis_snapshot                = models.CharField(max_length=15, choices=TypeVehicule.choices,
                                                                  default=TypeVehicule.MOTO)

    class Meta:
        verbose_name        = _('Ligne de livraison')
        verbose_name_plural = _('Lignes de livraison')

    def __str__(self):
        return f"{self.produit.nom} × {self.quantite} ({self.livraison.numero})"

    @property
    def montant_ligne(self):
        return self.prix_unitaire_snapshot * self.quantite

    def save(self, *args, **kwargs):
        if not self.prix_unitaire_snapshot:
            self.prix_unitaire_snapshot = self.produit.prix_unitaire
        if self.pk is None:
            self.vendu_en_ligne_snapshot = self.produit.vendu_en_ligne
            self.vehicule_requis_snapshot = self.produit.vehicule_minimum_requis
            # réservation du stock à la création de la ligne
            self.stock_entrepot.reserver(self.quantite, livraison=self.livraison)
        super().save(*args, **kwargs)


class HistoriqueStatutLivraison(models.Model):
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    livraison       = models.ForeignKey(Livraison, on_delete=models.CASCADE, related_name='historique_statuts')
    statut_avant     = models.CharField(max_length=15, blank=True)
    statut_apres       = models.CharField(max_length=15)
    commentaire           = models.TextField(blank=True)
    effectue_par             = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)
    latitude                    = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude                    = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    date                            = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = _('Historique statut livraison')
        verbose_name_plural = _('Historiques statuts livraisons')
        ordering            = ['-date']

    def __str__(self):
        avant = self.statut_avant or '—'
        return f"{self.livraison.numero} : {avant} → {self.statut_apres}"


# ═══════════════════════════════════════════════════════════════════════
# §2 – LIVRAISONS DIRECTES (particuliers / entreprises non inscrites)
# ═══════════════════════════════════════════════════════════════════════

class LivraisonDirecte(models.Model):
    """
    Livraison au km (ou négociée), intra-zone ou inter-villes.
    Une entreprise inscrite peut aussi initier une livraison directe
    (livraison_par_entreprise) sans passer par le circuit produits/stock.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', _('En attente de confirmation')
        CONFIRMEE   = 'CONFIRMEE', _('Confirmée')
        EN_COURS     = 'EN_COURS', _('En cours de livraison')
        LIVREE         = 'LIVREE', _('Livrée')
        ECHEC            = 'ECHEC', _('Échec')
        ANNULEE            = 'ANNULEE', _('Annulée')

    class TypeTarification(models.TextChoices):
        INTRA_ZONE  = 'INTRA_ZONE', _('Intra-zone (tarif zone)')
        INTER_VILLE  = 'INTER_VILLE', _('Inter-villes (table de tarifs)')
        AU_KM         = 'AU_KM', _('Calcul au kilomètre')
        NEGOCIE          = 'NEGOCIE', _('Prix négocié avec le client')

    id                    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero                  = models.CharField(max_length=25, unique=True, blank=True)
    client                     = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                                      related_name='livraisons_directes')
    livraison_par_entreprise      = models.ForeignKey(
        Entreprise, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='livraisons_directes_initiees',
        help_text=_('Renseigné si une entreprise inscrite est à l\'origine de cette livraison directe')
    )

    nom_expediteur              = models.CharField(max_length=150)
    telephone_expediteur           = models.CharField(max_length=20, validators=[tel_validator])
    description_colis                 = models.TextField()
    poids_kg                             = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    valeur_declaree                        = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    adresse_collecte    = models.TextField()
    ville_collecte        = models.ForeignKey(Ville, on_delete=models.PROTECT, related_name='departs_directs')
    zone_collecte            = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True,
                                                    related_name='departs_directs')
    latitude_depart              = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude_depart                = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    nom_destinataire                  = models.CharField(max_length=150)
    telephone_destinataire               = models.CharField(max_length=20, validators=[tel_validator])
    adresse_livraison                       = models.TextField()
    ville_livraison                            = models.ForeignKey(Ville, on_delete=models.PROTECT,
                                                                       related_name='arrivees_directes')
    zone_livraison                                = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True,
                                                                          blank=True, related_name='arrivees_directes')
    latitude_arrivee                                 = models.DecimalField(max_digits=10, decimal_places=7,
                                                                              blank=True, null=True)
    longitude_arrivee                                  = models.DecimalField(max_digits=10, decimal_places=7,
                                                                                 blank=True, null=True)

    # ── Tarification (NOUVEAU : intra-zone / inter-villes / km / négocié)
    type_tarification = models.CharField(max_length=15, choices=TypeTarification.choices,
                                           default=TypeTarification.AU_KM)
    vehicule_requis       = models.CharField(max_length=15, choices=TypeVehicule.choices, default=TypeVehicule.MOTO)
    distance_km              = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    tarif_par_km                = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('150.00'))
    prix_negocie                    = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    prix_total                          = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    statut               = models.CharField(max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE)
    livreur                 = models.ForeignKey(Livreur, on_delete=models.SET_NULL, null=True, blank=True,
                                                   related_name='livraisons_directes')
    token_suivi                 = models.CharField(max_length=64, unique=True, blank=True)
    date_creation                   = models.DateTimeField(auto_now_add=True)
    date_livraison                     = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = _('Livraison directe')
        verbose_name_plural = _('Livraisons directes')
        ordering            = ['-date_creation']

    def __str__(self):
        return f"{self.numero} | {self.nom_expediteur} → {self.nom_destinataire}"

    def save(self, *args, **kwargs):
        if not self.numero:
            today = timezone.now().strftime('%Y%m%d')
            count = LivraisonDirecte.objects.filter(numero__startswith=f'SDD-{today}-').count()
            self.numero = f'SDD-{today}-{str(count + 1).zfill(4)}'
        if not self.token_suivi:
            self.token_suivi = secrets.token_urlsafe(32)
        self._calculer_prix()
        super().save(*args, **kwargs)

    def _calculer_prix(self):
        if self.type_tarification == self.TypeTarification.NEGOCIE and self.prix_negocie:
            self.prix_total = self.prix_negocie

        elif self.type_tarification == self.TypeTarification.INTRA_ZONE and self.zone_livraison:
            self.prix_total = self.zone_livraison.get_prix_pour_vehicule(self.vehicule_requis)

        elif self.type_tarification == self.TypeTarification.INTER_VILLE and self.ville_collecte_id and self.ville_livraison_id:
            try:
                tarif = TarifInterVille.objects.get(
                    ville_depart=self.ville_collecte, ville_arrivee=self.ville_livraison
                )
                self.prix_total = tarif.calculer_prix(self.vehicule_requis, self.distance_km)
            except TarifInterVille.DoesNotExist:
                if self.distance_km:
                    self.prix_total = (self.distance_km * self.tarif_par_km).quantize(Decimal('0.01'))

        elif self.distance_km:  # AU_KM
            self.prix_total = (self.distance_km * self.tarif_par_km).quantize(Decimal('0.01'))
