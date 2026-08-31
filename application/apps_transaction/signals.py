# ═══════════════════════════════════════════════════════════════════════
# apps_transaction/signals.py
#
# 1) Détecte quand un LotPaiementEntreprise passe au statut ENVOYE et
#    déclenche apps_notification.signals.lot_paiement_envoye — ce signal
#    existe déjà côté apps_notification (receiver notifier_lot_paiement_
#    envoye) mais rien ne l'émettait : LotPaiementEntreprise.marquer_envoye()
#    change juste le champ `statut` sans notifier personne.
# 2) Notifie la plateforme (admins) quand l'entreprise confirme la
#    réception d'un paiement — utile pour le suivi comptable/litiges.
# 3) Garde-fous de cohérence sur Transaction (entreprise ↔ livraison).
#
# Doit être importé dans apps_transaction/apps.py → ready().
# ═══════════════════════════════════════════════════════════════════════

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps_core.choices import StatutLotPaiement
from apps_transaction.models import LotPaiementEntreprise, Transaction

logger = logging.getLogger('apps_transaction')


# ═══════════════════════════════════════════════════════════════════════
# §1 – SUIVI DES TRANSITIONS DE STATUT SUR LotPaiementEntreprise
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=LotPaiementEntreprise)
def memoriser_statut_avant_sauvegarde(sender, instance, **kwargs):
    """
    Capture l'ancien statut en base AVANT la sauvegarde, pour pouvoir
    détecter une transition dans le post_save (Django ne fournit pas
    nativement l'état précédent d'une instance).
    """
    if instance.pk:
        try:
            instance._statut_avant = (
                LotPaiementEntreprise.objects.only('statut').get(pk=instance.pk).statut
            )
        except LotPaiementEntreprise.DoesNotExist:
            instance._statut_avant = None
    else:
        instance._statut_avant = None


@receiver(post_save, sender=LotPaiementEntreprise)
def notifier_transition_statut_lot(sender, instance, created, **kwargs):
    """
    Émet les signaux de notification appropriés quand le lot change de
    statut : ENVOYE → prévenir l'entreprise (preuve jointe) ;
    CONFIRME_ENTREPRISE → prévenir l'équipe plateforme.
    """
    statut_avant = getattr(instance, '_statut_avant', None)
    if statut_avant == instance.statut:
        return  # pas de changement de statut, rien à notifier

    if instance.statut == StatutLotPaiement.ENVOYE:
        from apps_notification.signals import lot_paiement_envoye
        lot_paiement_envoye.send(sender=LotPaiementEntreprise, lot=instance)
        logger.info("Lot %s marqué ENVOYE — notification entreprise déclenchée", instance.reference)

    elif instance.statut == StatutLotPaiement.CONFIRME_ENTREPRISE:
        _notifier_plateforme_confirmation_lot(instance)
        logger.info("Lot %s confirmé par l'entreprise", instance.reference)

    elif instance.statut == StatutLotPaiement.LITIGE:
        _notifier_plateforme_litige_lot(instance)
        logger.warning("Lot %s signalé en LITIGE", instance.reference)


def _notifier_plateforme_confirmation_lot(lot):
    """Prévient tous les admins actifs que l'entreprise a confirmé la réception."""
    from apps_core.models import Utilisateur
    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    message = (
        f"SwiftDrop : {lot.entreprise.raison_sociale} a confirmé la réception "
        f"du paiement {lot.reference} ({lot.montant_net_a_payer} FCFA)."
    )
    for admin in Utilisateur.objects.admins():
        _dispatcher_notification(
            destinataire=admin, canal=Notification.Canal.EMAIL,
            evenement=Notification.Evenement.LOT_PAIEMENT_ENVOYE,
            message=message, sujet=f'Paiement confirmé — {lot.reference}',
        )


def _notifier_plateforme_litige_lot(lot):
    """Alerte les admins en cas de litige déclaré sur un lot de paiement."""
    from apps_core.models import Utilisateur
    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    message = (
        f"⚠️ SwiftDrop : litige signalé sur le lot {lot.reference} "
        f"({lot.entreprise.raison_sociale}) — {lot.note_litige or 'sans motif précisé'}."
    )
    for admin in Utilisateur.objects.admins():
        _dispatcher_notification(
            destinataire=admin, canal=Notification.Canal.EMAIL,
            evenement=Notification.Evenement.LOT_PAIEMENT_ENVOYE,
            message=message, sujet=f'⚠️ Litige — {lot.reference}',
        )


# ═══════════════════════════════════════════════════════════════════════
# §2 – GARDE-FOUS DE COHÉRENCE SUR Transaction
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=Transaction)
def valider_coherence_transaction(sender, instance, **kwargs):
    """
    Empêche l'enregistrement d'une transaction dont l'entreprise ne
    correspond pas à celle de la livraison liée (erreur de saisie/bug
    silencieux sinon, difficile à détecter après coup).
    """
    if instance.livraison_id and instance.entreprise_id:
        if instance.livraison.entreprise_id != instance.entreprise_id:
            raise ValueError(
                f"Incohérence Transaction : l'entreprise ({instance.entreprise_id}) "
                f"ne correspond pas à celle de la livraison {instance.livraison.numero} "
                f"({instance.livraison.entreprise_id})."
            )

    if instance.montant is not None and instance.montant < 0 and instance.type_transaction not in (
        Transaction.Type.REMBOURSEMENT, Transaction.Type.BONUS_APPLIQUE
    ):
        logger.warning(
            "Transaction %s de type %s créée avec un montant négatif (%s) — vérifier la logique appelante.",
            instance.reference or '(sans réf.)', instance.type_transaction, instance.montant
        )