import uuid
from datetime import date
from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps_core.models import Utilisateur, Zone
from apps_entreprise.models import Entreprise


class TypeBonus(models.Model):
    class Categorie(models.TextChoices):
        REDUCTION_ZONE       = 'RED_ZONE', _('Réduction frais zone (montant fixe)')
        REDUCTION_PCT          = 'RED_PCT', _('Réduction frais zone (pourcentage)')
        PRIORITE                  = 'PRIORITE', _('Priorité de traitement')
        LIVRAISONS_OFFERTES         = 'LIV_OFFT', _('N livraisons offertes')
        STOCKAGE_PREMIUM               = 'STOCK_PRE', _('Avantage stockage premium')

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom         = models.CharField(max_length=100)
    categorie   = models.CharField(max_length=20, choices=Categorie.choices)
    description = models.TextField()
    valeur      = models.DecimalField(max_digits=10, decimal_places=2)
    est_actif   = models.BooleanField(default=True)

    class Meta:
        verbose_name        = _('Type de bonus')
        verbose_name_plural = _('Types de bonus')

    def __str__(self):
        return f"{self.nom} ({self.valeur} – {self.get_categorie_display()})"


class BonusEntreprise(models.Model):
    class Statut(models.TextChoices):
        ACTIF   = 'ACTIF', _('Actif')
        UTILISE  = 'UTILISE', _('Entièrement utilisé')
        EXPIRE    = 'EXPIRE', _('Expiré')
        ANNULE     = 'ANNULE', _('Annulé')

    id                    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entreprise              = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name='bonus')
    type_bonus                = models.ForeignKey(TypeBonus, on_delete=models.PROTECT)
    zone_cible                   = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True)
    statut                          = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    date_debut                         = models.DateField()
    date_expiration                       = models.DateField()
    nb_utilisations_max                      = models.PositiveIntegerField(default=0)
    nb_utilisations_actuelles                   = models.PositiveIntegerField(default=0)
    attribue_par                                   = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True,
                                                                          related_name='bonus_attribues')
    note_interne                                      = models.TextField(blank=True)
    date_creation                                        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Bonus entreprise')
        verbose_name_plural = _('Bonus entreprises')
        ordering            = ['-date_creation']
        indexes = [models.Index(fields=['entreprise', 'statut'])]

    def __str__(self):
        return f"{self.type_bonus.nom} → {self.entreprise.raison_sociale} [{self.get_statut_display()}]"

    @property
    def est_valide_aujourd_hui(self):
        today = date.today()
        quota_ok = self.nb_utilisations_max == 0 or self.nb_utilisations_actuelles < self.nb_utilisations_max
        return self.statut == self.Statut.ACTIF and self.date_debut <= today <= self.date_expiration and quota_ok
