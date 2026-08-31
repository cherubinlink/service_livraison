# ═══════════════════════════════════════════════════════════════════════
# apps_bonus/signals.py
#
# 1) Notifie l'entreprise dès qu'un BonusEntreprise lui est attribué
#    (Notification.Evenement.BONUS_ATTRIB existe déjà côté
#    apps_notification, mais rien ne le déclenchait).
# 2) Consomme automatiquement le quota d'un bonus (nb_utilisations_
#    actuelles) quand une Livraison utilisant ce bonus passe au statut
#    LIVREE — et bascule le bonus en UTILISE si le quota est atteint.
#    Rien dans apps_livraison.models.Livraison ne gérait ça : le champ
#    bonus_applique / reduction_bonus était renseigné mais jamais
#    répercuté sur le compteur du bonus lui-même.
# 3) Garde-fou défensif : expire un bonus dont la date est dépassée dès
#    qu'il est resauvegardé (ne remplace pas une tâche cron dédiée pour
#    les bonus jamais retouchés, voir note en bas de fichier).
#
# Doit être importé dans apps_bonus/apps.py → ready().
# ═══════════════════════════════════════════════════════════════════════

import logging
from datetime import date

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps_bonus.models import BonusEntreprise

logger = logging.getLogger('apps_bonus')


# ═══════════════════════════════════════════════════════════════════════
# §1 – NOTIFICATION À L'ATTRIBUTION D'UN BONUS
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=BonusEntreprise)
def notifier_bonus_attribue(sender, instance, created, **kwargs):
    """Prévient l'entreprise dès qu'un bonus vient de lui être attribué."""
    if not created:
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    utilisateur = instance.entreprise.utilisateur
    zone_txt = f" (zone : {instance.zone_cible.nom})" if instance.zone_cible else ""
    message = (
        f"SwiftDrop : un bonus '{instance.type_bonus.nom}' vous a été attribué"
        f"{zone_txt}, valable du {instance.date_debut} au {instance.date_expiration}."
    )
    canal = Notification.Canal.WHATSAPP if instance.entreprise.notification_whatsapp else Notification.Canal.SMS
    _dispatcher_notification(
        destinataire=utilisateur, canal=canal,
        evenement=Notification.Evenement.BONUS_ATTRIB,
        message=message, sujet='Nouveau bonus attribué',
    )
    logger.info("Bonus %s attribué à %s", instance.type_bonus.nom, instance.entreprise.raison_sociale)


# ═══════════════════════════════════════════════════════════════════════
# §2 – EXPIRATION DÉFENSIVE À LA SAUVEGARDE
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=BonusEntreprise)
def expirer_bonus_perime(sender, instance, **kwargs):
    """
    Si le bonus est encore marqué ACTIF alors que sa date d'expiration
    est dépassée, on le bascule en EXPIRE avant l'écriture — évite qu'un
    bonus visiblement périmé reste affiché comme actif après une simple
    mise à jour d'un autre champ.
    NB : ne couvre PAS les bonus jamais resauvegardés — prévoir en plus
    une tâche planifiée quotidienne appelant BonusEntreprise.objects
    .filter(statut=ACTIF, date_expiration__lt=today).update(statut=EXPIRE).
    """
    if instance.statut == BonusEntreprise.Statut.ACTIF and instance.date_expiration < date.today():
        instance.statut = BonusEntreprise.Statut.EXPIRE
        logger.info("Bonus %s expiré automatiquement (date dépassée)", instance.pk)


# ═══════════════════════════════════════════════════════════════════════
# §3 – CONSOMMATION DU QUOTA À LA LIVRAISON
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender='apps_livraison.Livraison')
def memoriser_statut_livraison_avant_sauvegarde(sender, instance, **kwargs):
    """Capture l'ancien statut pour détecter la transition vers LIVREE."""
    if instance.pk:
        try:
            instance._statut_avant_bonus = sender.objects.only('statut').get(pk=instance.pk).statut
        except sender.DoesNotExist:
            instance._statut_avant_bonus = None
    else:
        instance._statut_avant_bonus = None


@receiver(post_save, sender='apps_livraison.Livraison')
def consommer_quota_bonus_si_livree(sender, instance, created, **kwargs):
    """
    Dès qu'une livraison passe au statut LIVREE (et pas avant, pour éviter
    de consommer le quota sur une commande finalement refusée/annulée),
    incrémente le compteur d'utilisation du bonus appliqué et bascule le
    bonus en UTILISE si son quota maximum est atteint.
    """
    if not instance.bonus_applique_id:
        return

    statut_avant = getattr(instance, '_statut_avant_bonus', None)
    if instance.statut != sender.Statut.LIVREE or statut_avant == sender.Statut.LIVREE:
        return  # pas de transition vers LIVREE, ou déjà comptabilisé

    bonus = instance.bonus_applique
    bonus.nb_utilisations_actuelles += 1
    if bonus.nb_utilisations_max and bonus.nb_utilisations_actuelles >= bonus.nb_utilisations_max:
        bonus.statut = BonusEntreprise.Statut.UTILISE
    bonus.save(update_fields=['nb_utilisations_actuelles', 'statut'])

    logger.info(
        "Bonus %s consommé par la livraison %s (%d/%s utilisations)",
        bonus.type_bonus.nom, instance.numero, bonus.nb_utilisations_actuelles,
        bonus.nb_utilisations_max or '∞'
    )


# ═══════════════════════════════════════════════════════════════════════
# NOTE — Tâche planifiée recommandée (cron/Celery beat, quotidien) :
#
#   from apps_bonus.models import BonusEntreprise
#   from datetime import date
#   BonusEntreprise.objects.filter(
#       statut=BonusEntreprise.Statut.ACTIF,
#       date_expiration__lt=date.today(),
#   ).update(statut=BonusEntreprise.Statut.EXPIRE)
#
# §2 ci-dessus ne couvre que les bonus resauvegardés pour une autre
# raison ; les bonus jamais retouchés après leur création ont besoin
# de cette purge périodique pour ne pas rester ACTIF indéfiniment.
# ═══════════════════════════════════════════════════════════════════════