# ═══════════════════════════════════════════════════════════════════════
# apps_entreprise/signals.py
#
# 1) Notifie l'utilisateur propriétaire dès que le STATUT de son
#    Entreprise change (validée / refusée / suspendue / désactivée pour
#    inactivité) — valider()/refuser()/suspendre()/desactiver_pour_
#    inactivite() ne faisaient que persister le nouveau statut sans
#    notifier personne.
# 2) Notifie l'entreprise dès qu'un FraisGardiennage lui est appliqué
#    (frais dû suite à désactivation pour inactivité).
# 3) Notifie l'entreprise dès que son frais de gardiennage est marqué
#    payé, pour confirmer la réactivation.
# 4) Notifie l'entreprise dès qu'un DocumentEntreprise qu'elle a fourni
#    est vérifié par un admin.
#
# Doit être importé dans apps_entreprise/apps.py → ready().
# ═══════════════════════════════════════════════════════════════════════

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps_entreprise.models import Entreprise, FraisGardiennage, DocumentEntreprise

logger = logging.getLogger('apps_entreprise')


# ═══════════════════════════════════════════════════════════════════════
# §1 – CHANGEMENT DE STATUT DE L'ENTREPRISE
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=Entreprise)
def memoriser_statut_entreprise_avant_sauvegarde(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._statut_avant = Entreprise.objects.only('statut').get(pk=instance.pk).statut
        except Entreprise.DoesNotExist:
            instance._statut_avant = None
    else:
        instance._statut_avant = None


@receiver(post_save, sender=Entreprise)
def notifier_changement_statut_entreprise(sender, instance, created, **kwargs):
    """
    Prévient l'utilisateur propriétaire de l'entreprise dès que le statut
    change réellement (et non à la création, où l'entreprise est déjà
    EN_ATTENTE par défaut et personne n'a encore de décision à recevoir).
    """
    statut_avant = getattr(instance, '_statut_avant', None)
    if created or statut_avant == instance.statut:
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    Statut = Entreprise.Statut

    if instance.statut == Statut.VALIDE:
        message = (
            f"SwiftDrop : votre entreprise '{instance.raison_sociale}' a été validée. "
            f"Vous pouvez démarrer votre activité sur la plateforme."
        )
        evenement_code, canal = 'ENTREPRISE_VALIDEE', Notification.Canal.EMAIL

    elif instance.statut == Statut.REFUSE:
        message = (
            f"SwiftDrop : votre entreprise '{instance.raison_sociale}' a été refusée. "
            f"Motif : {instance.motif_refus or 'non précisé'}."
        )
        evenement_code, canal = 'ENTREPRISE_REFUSEE', Notification.Canal.EMAIL

    elif instance.statut == Statut.SUSPENDU:
        message = (
            f"SwiftDrop : votre entreprise '{instance.raison_sociale}' a été suspendue. "
            f"Motif : {instance.motif_refus or 'non précisé'}. Contactez le support pour plus d'informations."
        )
        evenement_code, canal = 'ENTREPRISE_SUSPENDUE', Notification.Canal.SMS

    elif instance.statut == Statut.DESACTIVE_INACTIVITE:
        message = (
            f"SwiftDrop : votre entreprise '{instance.raison_sociale}' a été désactivée pour "
            f"inactivité (30 jours sans livraison). Vos produits en stock vous seront retournés. "
            f"Payez le frais de gardiennage pour réactiver votre compte sans attendre le retour."
        )
        evenement_code, canal = 'ENTREPRISE_DESACTIVEE_INACTIVITE', Notification.Canal.SMS

    else:
        # Retour à EN_ATTENTE ou autre transition non couverte : rien à notifier.
        return

    try:
        evenement = getattr(Notification.Evenement, evenement_code)
    except AttributeError:
        # Choix pas encore ajouté côté apps_notification/models.py — voir
        # note en bas de fichier. On envoie quand même via un canal générique.
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.%s manquant — ajoutez ce choix dans apps_notification/models.py",
            evenement_code,
        )

    _dispatcher_notification(
        destinataire=instance.utilisateur, canal=canal,
        evenement=evenement, message=message,
        sujet=f"Statut entreprise : {instance.get_statut_display()}",
    )
    logger.info(
        "Notification statut entreprise envoyée : %s → %s",
        instance.raison_sociale, instance.statut,
    )


# ═══════════════════════════════════════════════════════════════════════
# §2 – FRAIS DE GARDIENNAGE CRÉÉ (montant dû après désactivation)
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=FraisGardiennage)
def notifier_frais_gardiennage_du(sender, instance, created, **kwargs):
    if not created:
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    message = (
        f"SwiftDrop : un frais de gardiennage de {instance.montant_du} FCFA est dû pour "
        f"réactiver votre entreprise '{instance.entreprise.raison_sociale}'. Réglez ce montant "
        f"via votre numéro Mobile Money enregistré pour reprendre votre activité."
    )
    try:
        evenement = Notification.Evenement.FRAIS_GARDIENNAGE_DU
    except AttributeError:
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.FRAIS_GARDIENNAGE_DU manquant — "
            "ajoutez ce choix dans apps_notification/models.py"
        )

    _dispatcher_notification(
        destinataire=instance.entreprise.utilisateur, canal=Notification.Canal.SMS,
        evenement=evenement, message=message, sujet='Frais de gardiennage dû',
    )
    logger.info(
        "Frais de gardiennage notifié : %s FCFA — %s",
        instance.montant_du, instance.entreprise.raison_sociale,
    )


# ═══════════════════════════════════════════════════════════════════════
# §3 – FRAIS DE GARDIENNAGE PAYÉ → CONFIRMATION DE RÉACTIVATION
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=FraisGardiennage)
def memoriser_etat_paye_avant_sauvegarde(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._paye_avant = FraisGardiennage.objects.only('paye').get(pk=instance.pk).paye
        except FraisGardiennage.DoesNotExist:
            instance._paye_avant = None
    else:
        instance._paye_avant = None


@receiver(post_save, sender=FraisGardiennage)
def notifier_frais_gardiennage_paye(sender, instance, created, **kwargs):
    paye_avant = getattr(instance, '_paye_avant', None)
    if created or paye_avant or not instance.paye:
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    message = (
        f"SwiftDrop : votre paiement de {instance.montant_paye} FCFA pour le gardiennage a été "
        f"confirmé. Votre entreprise '{instance.entreprise.raison_sociale}' est réactivée."
    )
    try:
        evenement = Notification.Evenement.FRAIS_GARDIENNAGE_PAYE
    except AttributeError:
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.FRAIS_GARDIENNAGE_PAYE manquant — "
            "ajoutez ce choix dans apps_notification/models.py"
        )

    _dispatcher_notification(
        destinataire=instance.entreprise.utilisateur, canal=Notification.Canal.EMAIL,
        evenement=evenement, message=message, sujet='Gardiennage payé — réactivation confirmée',
    )
    logger.info("Paiement gardiennage confirmé pour %s", instance.entreprise.raison_sociale)


# ═══════════════════════════════════════════════════════════════════════
# §4 – DOCUMENT ENTREPRISE VÉRIFIÉ PAR UN ADMIN
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=DocumentEntreprise)
def memoriser_etat_verifie_avant_sauvegarde(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._verifie_avant = DocumentEntreprise.objects.only('verifie').get(pk=instance.pk).verifie
        except DocumentEntreprise.DoesNotExist:
            instance._verifie_avant = None
    else:
        instance._verifie_avant = None


@receiver(post_save, sender=DocumentEntreprise)
def notifier_document_verifie(sender, instance, created, **kwargs):
    verifie_avant = getattr(instance, '_verifie_avant', None)
    if created or verifie_avant or not instance.verifie:
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    message = (
        f"SwiftDrop : votre document '{instance.get_type_doc_display()}' a été vérifié "
        f"et validé par notre équipe."
    )
    try:
        evenement = Notification.Evenement.DOCUMENT_VERIFIE
    except AttributeError:
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.DOCUMENT_VERIFIE manquant — "
            "ajoutez ce choix dans apps_notification/models.py"
        )

    _dispatcher_notification(
        destinataire=instance.entreprise.utilisateur, canal=Notification.Canal.EMAIL,
        evenement=evenement, message=message, sujet='Document vérifié',
    )
    logger.info(
        "Document vérifié notifié : %s — %s",
        instance.get_type_doc_display(), instance.entreprise.raison_sociale,
    )


# ═══════════════════════════════════════════════════════════════════════
# NOTE — Choix à ajouter dans apps_notification/models.py > Notification.Evenement :
#
#   ENTREPRISE_VALIDEE               = 'ENT_VALIDE', _('Entreprise validée')
#   ENTREPRISE_REFUSEE               = 'ENT_REFUSE', _('Entreprise refusée')
#   ENTREPRISE_SUSPENDUE             = 'ENT_SUSPEND', _('Entreprise suspendue')
#   ENTREPRISE_DESACTIVEE_INACTIVITE = 'ENT_DESACT', _('Entreprise désactivée pour inactivité')
#   FRAIS_GARDIENNAGE_DU             = 'GARD_DU', _('Frais de gardiennage dû')
#   FRAIS_GARDIENNAGE_PAYE           = 'GARD_PAYE', _('Frais de gardiennage payé')
#   DOCUMENT_VERIFIE                 = 'DOC_VERIFIE', _('Document entreprise vérifié')
#
# Sans ces entrées, les receivers ci-dessus retombent sur un événement
# générique existant (avec un avertissement en log) plutôt que d'échouer.
# ═══════════════════════════════════════════════════════════════════════