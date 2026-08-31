import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps_core.models import Utilisateur
from apps_livraison.models import Livraison


class Notification(models.Model):
    class Canal(models.TextChoices):
        SMS      = 'SMS', _('SMS (Africa\'s Talking)')
        WHATSAPP = 'WHATSAPP', _('WhatsApp Business API')
        EMAIL     = 'EMAIL', _('Email')
        PUSH        = 'PUSH', _('Push mobile (FCM)')

    class Evenement(models.TextChoices):
        LIV_CREEE            = 'LIV_CREEE', _('Livraison créée')
        LIV_VALIDEE            = 'LIV_VALIDEE', _('Livraison validée')
        LIV_REFUSEE               = 'LIV_REFUSEE', _('Livraison refusée')
        LIV_EN_COURS                 = 'LIV_EN_COURS', _('Livraison en cours')
        LIV_LIVREE                     = 'LIV_LIVREE', _('Livraison effectuée')
        LIV_ECHEC                        = 'LIV_ECHEC', _('Échec livraison')
        RECEPTION_A_VALIDER                 = 'RECEP_VALID', _('Réception à valider par l\'entreprise')
        RECAP_GAIN                             = 'RECAP_GAIN', _('Récapitulatif gain livraison')
        LOT_PAIEMENT_ENVOYE                       = 'LOT_ENVOYE', _('Lot de paiement envoyé (preuve jointe)')
        ENT_VALIDEE                                  = 'ENT_VALIDEE', _('Entreprise validée')
        ENT_REFUSEE                                     = 'ENT_REFUSEE', _('Entreprise refusée')
        ENT_DESACTIVEE_INACTIVITE                          = 'ENT_INACTIF', _('Entreprise désactivée pour inactivité')
        PROD_VALIDE                                            = 'PROD_VALIDE', _('Produit validé')
        STOCK_BAS                                                 = 'STOCK_BAS', _('Alerte stock bas')
        BONUS_ATTRIB                                                 = 'BONUS', _('Bonus attribué')

    class StatutEnvoi(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', _('En file d\'attente')
        ENVOYE       = 'ENVOYE', _('Envoyé')
        LIVRE          = 'LIVRE', _('Livré (accusé réception)')
        ECHEC             = 'ECHEC', _('Échec d\'envoi')

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    destinataire        = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='notifications')
    canal                  = models.CharField(max_length=10, choices=Canal.choices)
    evenement                 = models.CharField(max_length=20, choices=Evenement.choices)
    telephone                    = models.CharField(max_length=20, blank=True)
    sujet                           = models.CharField(max_length=200, blank=True)
    message                            = models.TextField()
    statut_envoi                          = models.CharField(max_length=15, choices=StatutEnvoi.choices,
                                                                default=StatutEnvoi.EN_ATTENTE)
    ref_externe                              = models.CharField(max_length=100, blank=True)
    erreur                                      = models.TextField(blank=True)
    livraison                                      = models.ForeignKey(Livraison, on_delete=models.SET_NULL, null=True,
                                                                          blank=True, related_name='notifications')
    nb_tentatives                                     = models.PositiveSmallIntegerField(default=0)
    date_envoi                                           = models.DateTimeField(auto_now_add=True)
    date_livraison_notif                                    = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering            = ['-date_envoi']
        indexes = [
            models.Index(fields=['statut_envoi', 'canal']),
            models.Index(fields=['destinataire', 'date_envoi']),
        ]

    def __str__(self):
        return f"[{self.get_canal_display()}] {self.get_evenement_display()} → {self.destinataire.nom} [{self.get_statut_envoi_display()}]"
