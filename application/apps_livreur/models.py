import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps_core.models import Utilisateur, Zone
from apps_core.choices import TypeVehicule
from apps_core.validators import upload_path


class Livreur(models.Model):
    """
    Livreur partenaire. Son `type_vehicule` détermine automatiquement
    le coefficient de majoration appliqué aux frais de livraison
    (cf. apps_core.CoefficientVehicule) quand il est assigné à une
    livraison — le véhicule doit être compatible avec vehicule_minimum
    requis par les produits transportés (contrôlé à l'attribution).
    """

    class Statut(models.TextChoices):
        ACTIF      = 'ACTIF', _('Actif / Disponible')
        EN_MISSION = 'EN_MISSION', _('En mission')
        PAUSE       = 'PAUSE', _('En pause')
        INACTIF      = 'INACTIF', _('Inactif / Hors ligne')
        SUSPENDU      = 'SUSPENDU', _('Suspendu')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur   = models.OneToOneField(Utilisateur, on_delete=models.CASCADE, related_name='profil_livreur')
    numero_cni     = models.CharField(max_length=20, unique=True)
    type_vehicule   = models.CharField(max_length=15, choices=TypeVehicule.choices)
    immatriculation  = models.CharField(max_length=20, blank=True)
    capacite_charge_kg = models.DecimalField(
        _('Capacité de charge (kg)'), max_digits=8, decimal_places=2, null=True, blank=True
    )
    zones_travail     = models.ManyToManyField(Zone, blank=True, related_name='livreurs')
    statut              = models.CharField(max_length=15, choices=Statut.choices, default=Statut.INACTIF)
    latitude_actuelle     = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude_actuelle     = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    derniere_position        = models.DateTimeField(null=True, blank=True)
    total_livraisons           = models.PositiveIntegerField(default=0)
    note_moyenne                 = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    photo_cni     = models.ImageField(upload_to=upload_path, blank=True, null=True)
    date_inscription = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Livreur')
        verbose_name_plural = _('Livreurs')
        ordering            = ['utilisateur__nom']

    def __str__(self):
        return f"Livreur : {self.utilisateur.nom} [{self.get_statut_display()}]"

    def peut_transporter(self, vehicule_minimum_requis: str) -> bool:
        """Vérifie que le véhicule du livreur couvre le besoin du produit le plus exigeant."""
        ordre = [TypeVehicule.VELO, TypeVehicule.MOTO, TypeVehicule.TRICYCLE,
                 TypeVehicule.VOITURE, TypeVehicule.CAMIONNETTE, TypeVehicule.CAMION]
        try:
            return ordre.index(self.type_vehicule) >= ordre.index(vehicule_minimum_requis)
        except ValueError:
            return True


class PositionLivreurHistorique(models.Model):
    """Historique GPS léger — utile pour le tracking temps réel et l'audit."""
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    livreur    = models.ForeignKey(Livreur, on_delete=models.CASCADE, related_name='historique_positions')
    latitude    = models.DecimalField(max_digits=10, decimal_places=7)
    longitude    = models.DecimalField(max_digits=10, decimal_places=7)
    livraison_en_cours = models.ForeignKey('apps_livraison.Livraison', on_delete=models.SET_NULL,
                                             null=True, blank=True, related_name='traces_position')
    horodatage    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = _('Position livreur (historique)')
        verbose_name_plural = _('Positions livreurs (historique)')
        ordering            = ['-horodatage']
        indexes = [models.Index(fields=['livreur', 'horodatage'])]
