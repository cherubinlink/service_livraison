# ═══════════════════════════════════════════════════════════════════════
# apps_catalogue/signals.py
#
# 1) Émet enfin apps_notification.signals.stock_alerte_declenchee quand
#    un AlerteStock est créé (StockEntrepot._verifier_alertes() créait
#    l'alerte mais n'envoyait jamais le signal).
# 2) Traite RÉELLEMENT un RetourStockProprietaire : décrémente le stock
#    de l'entrepôt concerné, journalise un MouvementStock, et notifie
#    l'entreprise — jusqu'ici ce modèle n'était qu'une trace inerte.
# 3) Notifie l'admin qui a enregistré un produit dès que l'entreprise le
#    valide ou le refuse (Produit.valider()/refuser() ne notifiaient rien).
#
# Doit être importé dans apps_catalogue/apps.py → ready().
# ═══════════════════════════════════════════════════════════════════════

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps_catalogue.models import (
    Produit, StockEntrepot, MouvementStock, AlerteStock, RetourStockProprietaire
)

logger = logging.getLogger('apps_catalogue')


# ═══════════════════════════════════════════════════════════════════════
# §1 – ÉMISSION DU SIGNAL D'ALERTE STOCK
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=AlerteStock)
def emettre_signal_alerte_stock(sender, instance, created, **kwargs):
    """
    Relaie chaque nouvelle AlerteStock vers apps_notification, dont le
    receiver notifier_alerte_stock() est déjà connecté mais n'était
    jamais déclenché faute d'émission du signal côté apps_catalogue.
    """
    if not created:
        return
    from apps_notification.signals import stock_alerte_declenchee
    stock_alerte_declenchee.send(sender=AlerteStock, alerte=instance)
    logger.info(
        "Alerte %s émise pour %s @ %s",
        instance.get_type_alerte_display(),
        instance.stock_entrepot.produit.nom,
        instance.stock_entrepot.entrepot.nom,
    )


# ═══════════════════════════════════════════════════════════════════════
# §2 – TRAITEMENT EFFECTIF D'UN RETOUR AU PROPRIÉTAIRE
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=RetourStockProprietaire)
def traiter_retour_stock_proprietaire(sender, instance, created, **kwargs):
    """
    Un RetourStockProprietaire n'était qu'une ligne d'audit : ce receiver
    lui donne un effet réel — décrémente le StockEntrepot concerné,
    journalise le mouvement, et notifie l'entreprise.
    """
    if not created:
        return

    try:
        stock = StockEntrepot.objects.get(produit=instance.produit, entrepot=instance.entrepot)
    except StockEntrepot.DoesNotExist:
        logger.warning(
            "RetourStockProprietaire %s : aucun StockEntrepot trouvé pour %s @ %s",
            instance.pk, instance.produit.nom, instance.entrepot
        )
        return

    avant = stock.quantite_stock
    stock.quantite_stock = max(0, stock.quantite_stock - instance.quantite_retournee)
    stock.save(update_fields=['quantite_stock'])

    MouvementStock.objects.create(
        stock_entrepot=stock,
        type_mouvement=MouvementStock.TypeMouvement.RETOUR_PROPRIETAIRE,
        quantite=-instance.quantite_retournee,
        stock_avant=avant,
        stock_apres=stock.quantite_stock,
        note=f"Retour propriétaire — {instance.get_motif_display()}",
    )

    _notifier_retour_stock(instance)
    logger.info(
        "Retour propriétaire traité : %d× %s rendu à %s",
        instance.quantite_retournee, instance.produit.nom, instance.entreprise.raison_sociale
    )


def _notifier_retour_stock(retour):
    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    utilisateur = retour.entreprise.utilisateur
    message = (
        f"SwiftDrop : {retour.quantite_retournee} unité(s) de '{retour.produit.nom}' "
        f"vous ont été retournées (motif : {retour.get_motif_display()}). "
        f"Merci de venir les récupérer à l'entrepôt {retour.entrepot.nom if retour.entrepot else '—'}."
    )
    try:
        evenement = Notification.Evenement.RETOUR_STOCK_PROPRIETAIRE
    except AttributeError:
        # Choix pas encore ajouté côté apps_notification/models.py — voir
        # note en bas de fichier. On envoie quand même via un canal générique.
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.RETOUR_STOCK_PROPRIETAIRE manquant — "
            "ajoutez ce choix dans apps_notification/models.py"
        )
    _dispatcher_notification(
        destinataire=utilisateur, canal=Notification.Canal.SMS,
        evenement=evenement, message=message, sujet='Retour de produits',
    )


# ═══════════════════════════════════════════════════════════════════════
# §3 – NOTIFICATION VALIDATION / REFUS D'UN PRODUIT
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=Produit)
def memoriser_statut_produit_avant_sauvegarde(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._statut_avant = Produit.objects.only('statut').get(pk=instance.pk).statut
        except Produit.DoesNotExist:
            instance._statut_avant = None
    else:
        instance._statut_avant = None


@receiver(post_save, sender=Produit)
def notifier_decision_produit(sender, instance, created, **kwargs):
    """
    Prévient l'admin qui a enregistré le produit (enregistre_par) dès que
    l'entreprise le valide ou le refuse — Produit.valider()/refuser() ne
    faisaient que changer le statut sans notifier personne.
    """
    statut_avant = getattr(instance, '_statut_avant', None)
    if statut_avant == instance.statut or instance.enregistre_par_id is None:
        return
    if instance.statut not in (Produit.StatutProduit.VALIDE, Produit.StatutProduit.REFUSE):
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    if instance.statut == Produit.StatutProduit.VALIDE:
        message = f"SwiftDrop : le produit '{instance.nom}' a été validé par {instance.entreprise.raison_sociale}."
        evenement = Notification.Evenement.PROD_VALIDE
    else:
        message = (
            f"SwiftDrop : le produit '{instance.nom}' a été refusé par "
            f"{instance.entreprise.raison_sociale}. Motif : {instance.motif_refus or 'non précisé'}."
        )
        try:
            evenement = Notification.Evenement.PROD_REFUSE
        except AttributeError:
            evenement = Notification.Evenement.PROD_VALIDE
            logger.warning(
                "Notification.Evenement.PROD_REFUSE manquant — "
                "ajoutez ce choix dans apps_notification/models.py"
            )

    _dispatcher_notification(
        destinataire=instance.enregistre_par, canal=Notification.Canal.EMAIL,
        evenement=evenement, message=message, sujet=f"Produit {instance.get_statut_display()}",
    )


# ═══════════════════════════════════════════════════════════════════════
# NOTE — Choix à ajouter dans apps_notification/models.py > Notification.Evenement :
#
#   RETOUR_STOCK_PROPRIETAIRE = 'RETOUR_STOCK', _('Produits retournés au propriétaire')
#   PROD_REFUSE               = 'PROD_REFUSE', _('Produit refusé')
#
# Sans ces entrées, les receivers ci-dessus retombent sur un événement
# générique existant (avec un avertissement en log) plutôt que d'échouer.
# ═══════════════════════════════════════════════════════════════════════