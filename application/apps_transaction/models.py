import uuid
import secrets
from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps_core.models import Utilisateur
from apps_core.choices import MethodePaiementSortant, StatutLotPaiement
from apps_core.validators import upload_path
from apps_entreprise.models import Entreprise
from apps_livraison.models import Livraison, LivraisonDirecte


class Transaction(models.Model):
    """Enregistrement comptable unitaire de chaque flux financier."""

    class Type(models.TextChoices):
        GAIN_ENTREPRISE  = 'GAIN_ENT', _('Gain entreprise')
        FRAIS_LIVRAISON   = 'FRAIS_LIV', _('Frais livraison (plateforme)')
        COMMISSION_YOPISHOP = 'COM_YOPI', _('Commission Yopishop (10%)')
        REMBOURSEMENT         = 'REMBOURST', _('Remboursement')
        BONUS_APPLIQUE           = 'BONUS', _('Réduction bonus appliquée')
        FRAIS_DIRECT               = 'FRAIS_DIR', _('Frais livraison directe')
        FRAIS_GARDIENNAGE             = 'GARDIENNAGE', _('Frais de gardiennage (inactivité)')

    class StatutPaiement(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', _('En attente')
        CONFIRME    = 'CONFIRME', _('Confirmé')
        ANNULE       = 'ANNULE', _('Annulé')

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference             = models.CharField(max_length=50, unique=True, blank=True)
    entreprise              = models.ForeignKey(Entreprise, on_delete=models.PROTECT, null=True, blank=True,
                                                   related_name='transactions')
    livraison                 = models.ForeignKey(Livraison, on_delete=models.PROTECT, null=True, blank=True,
                                                      related_name='transactions')
    livraison_directe            = models.ForeignKey(LivraisonDirecte, on_delete=models.PROTECT, null=True, blank=True,
                                                         related_name='transactions')
    type_transaction                 = models.CharField(max_length=15, choices=Type.choices)
    montant                             = models.DecimalField(max_digits=12, decimal_places=2)
    statut_paiement                        = models.CharField(max_length=15, choices=StatutPaiement.choices,
                                                                  default=StatutPaiement.EN_ATTENTE)
    note                                      = models.TextField(blank=True)
    date                                         = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = _('Transaction')
        verbose_name_plural = _('Transactions')
        ordering            = ['-date']
        indexes = [
            models.Index(fields=['entreprise', 'date']),
            models.Index(fields=['type_transaction', 'statut_paiement']),
        ]

    def __str__(self):
        ent = self.entreprise.raison_sociale if self.entreprise else 'Plateforme'
        return f"[{self.reference}] {self.get_type_transaction_display()} – {self.montant} FCFA – {ent}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f'TXN-{secrets.token_hex(6).upper()}'
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════════
# PAIEMENT PAR LOTS AUX ENTREPRISES (NOUVEAU)
# ═══════════════════════════════════════════════════════════════════════

class LotPaiementEntreprise(models.Model):
    """
    Regroupement de toutes les livraisons "réception validée / en attente
    de paiement" d'une entreprise sur une PÉRIODE (selon son cycle_paiement :
    quotidien / hebdomadaire / mensuel), pour un règlement unique.

    La plateforme prélève ses frais de livraison (par zone) + commission
    Yopishop sur toutes les livraisons du lot, puis envoie le NET à
    l'entreprise via Mobile Money / virement, AVEC PREUVE jointe.
    L'entreprise confirme ensuite la réception du paiement depuis SON
    interface dédiée (distincte de celle de l'admin).
    """
    id                          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference                     = models.CharField(max_length=30, unique=True, blank=True)
    entreprise                       = models.ForeignKey(Entreprise, on_delete=models.PROTECT, related_name='lots_paiement')
    livraisons                          = models.ManyToManyField(Livraison, related_name='lots_paiement', blank=True)

    periode_debut                          = models.DateField()
    periode_fin                               = models.DateField()

    montant_brut_produits                        = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    montant_frais_livraison_deduits                 = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    montant_commission_yopishop_deduite                = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    montant_net_a_payer                                   = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    methode_paiement              = models.CharField(max_length=15, choices=MethodePaiementSortant.choices,
                                                        default=MethodePaiementSortant.MTN_MOMO)
    numero_compte_destination        = models.CharField(max_length=30, blank=True)
    reference_transaction_externe       = models.CharField(_('Réf. transaction Mobile Money/banque'), max_length=100, blank=True)
    preuve_paiement                        = models.ImageField(upload_to=upload_path, blank=True, null=True)

    statut                    = models.CharField(max_length=15, choices=StatutLotPaiement.choices,
                                                    default=StatutLotPaiement.EN_PREPARATION, db_index=True)
    note_litige                  = models.TextField(blank=True)

    envoye_par                      = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                                            related_name='lots_paiement_envoyes')
    date_envoi                         = models.DateTimeField(null=True, blank=True)
    confirme_par                          = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                                                  related_name='lots_paiement_confirmes')
    date_confirmation_entreprise             = models.DateTimeField(null=True, blank=True)
    date_creation                               = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Lot de paiement entreprise')
        verbose_name_plural = _('Lots de paiement entreprises')
        ordering            = ['-date_creation']
        indexes = [models.Index(fields=['entreprise', 'statut'])]

    def __str__(self):
        return f"{self.reference} – {self.entreprise.raison_sociale} – {self.montant_net_a_payer} FCFA [{self.get_statut_display()}]"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f'LOT-{secrets.token_hex(5).upper()}'
        super().save(*args, **kwargs)

    def construire_depuis_livraisons_eligibles(self):
        """
        Récupère toutes les livraisons de l'entreprise dont la réception
        est validée mais pas encore payées, sur la période demandée.
        """
        from apps_core.choices import StatutReceptionLivraison
        livraisons = Livraison.objects.filter(
            entreprise=self.entreprise,
            statut_reception=StatutReceptionLivraison.RECEPTION_VALIDEE,
            date_livraison_effective__date__gte=self.periode_debut,
            date_livraison_effective__date__lte=self.periode_fin,
        )
        self.livraisons.set(livraisons)

        self.montant_brut_produits = sum((l.montant_total_produits for l in livraisons), Decimal('0.00'))
        self.montant_frais_livraison_deduits = sum(
            (l.frais_livraison_applique - l.frais_livraison_paye_par_client if not l.frais_livraison_paye_integralement
             else Decimal('0.00') for l in livraisons), Decimal('0.00')
        )
        self.montant_commission_yopishop_deduite = sum((l.commission_yopishop_montant for l in livraisons), Decimal('0.00'))
        self.montant_net_a_payer = (
            self.montant_brut_produits - self.montant_frais_livraison_deduits - self.montant_commission_yopishop_deduite
        )
        self.statut = StatutLotPaiement.PRET_A_ENVOYER
        self.save()

        for livraison in livraisons:
            livraison.statut_reception = StatutReceptionLivraison.PAIEMENT_ATTENTE
            livraison.save(update_fields=['statut_reception'])

    def marquer_envoye(self, admin_user, reference_externe='', preuve=None):
        from apps_core.choices import StatutLotPaiement as SL
        self.statut = SL.ENVOYE
        self.envoye_par = admin_user
        self.date_envoi = timezone.now()
        self.reference_transaction_externe = reference_externe
        if preuve:
            self.preuve_paiement = preuve
        self.save()

    def confirmer_reception_entreprise(self, utilisateur_entreprise):
        from apps_core.choices import StatutLotPaiement as SL, StatutReceptionLivraison
        self.statut = SL.CONFIRME_ENTREPRISE
        self.confirme_par = utilisateur_entreprise
        self.date_confirmation_entreprise = timezone.now()
        self.save()
        self.livraisons.update(statut_reception=StatutReceptionLivraison.PAIEMENT_RECU)

        for livraison in self.livraisons.all():
            Transaction.objects.create(
                entreprise=self.entreprise, livraison=livraison,
                type_transaction=Transaction.Type.GAIN_ENTREPRISE,
                montant=livraison.gain_entreprise,
                statut_paiement=Transaction.StatutPaiement.CONFIRME,
                note=f'Payé via lot {self.reference}',
            )
