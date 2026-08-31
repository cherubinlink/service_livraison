# ═══════════════════════════════════════════════════════════════════════
# apps_livreur/signals.py
#
# 1) Synchronise Livreur.latitude_actuelle / longitude_actuelle /
#    derniere_position à chaque nouvelle PositionLivreurHistorique — ce
#    modèle n'était qu'une trace GPS inerte, jamais reportée sur le
#    livreur lui-même (même défaut que RetourStockProprietaire côté
#    apps_catalogue).
# 2) Fait passer automatiquement le livreur en EN_MISSION quand une
#    Livraison lui est attribuée, puis le repasse en ACTIF (et
#    incrémente total_livraisons) quand la course se termine — les
#    champs `statut`/`total_livraisons` existent mais rien ne les
#    faisait bouger automatiquement.
# 3) Recalcule Livreur.note_moyenne à chaque nouvelle Evaluation liée à
#    l'une de ses livraisons — le champ existait mais restait figé à 0.
# 4) Notifie le livreur quand un admin le suspend ou le réactive.
#
# Doit être importé dans apps_livreur/apps.py → ready().
#
# NB : les receivers sur Livraison / Evaluation utilisent une référence
# `sender` sous forme de chaîne ('app_label.ModelName'), le mécanisme
# lazy standard de Django pour les signaux inter-apps — ça évite tout
# import circulaire avec apps_livraison (qui importe déjà Livreur).
# ═══════════════════════════════════════════════════════════════════════

import logging

from django.db.models import Avg
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps_livreur.models import Livreur, PositionLivreurHistorique

logger = logging.getLogger('apps_livreur')


# ═══════════════════════════════════════════════════════════════════════
# §1 – SYNCHRONISATION DE LA POSITION GPS COURANTE
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=PositionLivreurHistorique)
def synchroniser_position_courante_livreur(sender, instance, created, **kwargs):
    if not created:
        return
    Livreur.objects.filter(pk=instance.livreur_id).update(
        latitude_actuelle=instance.latitude,
        longitude_actuelle=instance.longitude,
        derniere_position=instance.horodatage,
    )
    logger.debug(
        "Position courante mise à jour pour %s (%.6f, %.6f)",
        instance.livreur_id, instance.latitude, instance.longitude,
    )


# ═══════════════════════════════════════════════════════════════════════
# §2 – DISPONIBILITÉ DU LIVREUR SELON LE CYCLE DE VIE D'UNE LIVRAISON
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender='apps_livraison.Livraison')
def memoriser_livreur_et_statut_livraison(sender, instance, **kwargs):
    if instance.pk:
        try:
            avant = sender.objects.only('livreur_id', 'statut').get(pk=instance.pk)
            instance._sync_livreur_id_avant = avant.livreur_id
            instance._sync_statut_avant = avant.statut
        except sender.DoesNotExist:
            instance._sync_livreur_id_avant = None
            instance._sync_statut_avant = None
    else:
        instance._sync_livreur_id_avant = None
        instance._sync_statut_avant = None


@receiver(post_save, sender='apps_livraison.Livraison')
def synchroniser_disponibilite_livreur(sender, instance, created, **kwargs):
    livreur_id_avant = getattr(instance, '_sync_livreur_id_avant', None)
    statut_avant = getattr(instance, '_sync_statut_avant', None)

    # ── Nouvelle attribution : None → un livreur ─────────────────────
    if not created and livreur_id_avant is None and instance.livreur_id is not None:
        Livreur.objects.filter(pk=instance.livreur_id, statut=Livreur.Statut.ACTIF).update(
            statut=Livreur.Statut.EN_MISSION
        )
        logger.info("Livreur %s passé EN_MISSION (livraison %s)", instance.livreur_id, instance.numero)

    # ── Fin de course : LIVREE / ECHEC / ANNULEE / REFUSEE ────────────
    if created or statut_avant == instance.statut or instance.livreur_id is None:
        return

    Statut = sender.Statut
    if instance.statut not in (Statut.LIVREE, Statut.ECHEC, Statut.ANNULEE, Statut.REFUSEE):
        return

    if instance.statut == Statut.LIVREE:
        Livreur.objects.filter(pk=instance.livreur_id).update(
            total_livraisons=instance.livreur.total_livraisons + 1
        )

    # Ne libère que s'il était bien EN_MISSION (ne touche pas à une
    # SUSPENSION ou une PAUSE décidées entre-temps par ailleurs).
    Livreur.objects.filter(pk=instance.livreur_id, statut=Livreur.Statut.EN_MISSION).update(
        statut=Livreur.Statut.ACTIF
    )
    logger.info(
        "Livreur %s repassé ACTIF après livraison %s (%s)",
        instance.livreur_id, instance.numero, instance.statut,
    )


# ═══════════════════════════════════════════════════════════════════════
# §3 – RECALCUL DE LA NOTE MOYENNE DU LIVREUR
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender='apps_evaluation.Evaluation')
def recalculer_note_moyenne_livreur(sender, instance, created, **kwargs):
    """
    note_livreur est prioritaire si renseignée, sinon on retombe sur
    note_globale (même logique que la notification du livreur côté
    apps_evaluation/signals.py).
    """
    if not created:
        return

    livreur = getattr(instance.livraison, 'livreur', None)
    if livreur is None:
        return

    moyenne = sender.objects.filter(livraison__livreur=livreur).aggregate(
        m=Avg(Coalesce('note_livreur', 'note_globale'))
    )['m'] or 0

    Livreur.objects.filter(pk=livreur.pk).update(note_moyenne=round(moyenne, 2))
    logger.info("Note moyenne recalculée pour le livreur %s : %.2f/5", livreur.pk, moyenne)


# ═══════════════════════════════════════════════════════════════════════
# §4 – NOTIFICATION SUSPENSION / RÉACTIVATION DU LIVREUR
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=Livreur)
def memoriser_statut_livreur_avant_sauvegarde(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._statut_avant = Livreur.objects.only('statut').get(pk=instance.pk).statut
        except Livreur.DoesNotExist:
            instance._statut_avant = None
    else:
        instance._statut_avant = None


@receiver(post_save, sender=Livreur)
def notifier_changement_statut_livreur(sender, instance, created, **kwargs):
    statut_avant = getattr(instance, '_statut_avant', None)
    if created or statut_avant == instance.statut:
        return
    # On ne notifie que les transitions décidées côté admin, pas les
    # allers-retours ACTIF ⇄ EN_MISSION gérés automatiquement en §2.
    if instance.statut not in (Livreur.Statut.SUSPENDU, Livreur.Statut.ACTIF):
        return
    if instance.statut == Livreur.Statut.ACTIF and statut_avant != Livreur.Statut.SUSPENDU:
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    if instance.statut == Livreur.Statut.SUSPENDU:
        message = "SwiftDrop : votre compte livreur a été suspendu. Contactez le support pour plus d'informations."
        evenement_code = 'LIVREUR_SUSPENDU'
    else:
        message = "SwiftDrop : votre compte livreur a été réactivé. Vous pouvez reprendre vos livraisons."
        evenement_code = 'LIVREUR_REACTIVE'

    try:
        evenement = getattr(Notification.Evenement, evenement_code)
    except AttributeError:
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.%s manquant — ajoutez ce choix dans apps_notification/models.py",
            evenement_code,
        )

    _dispatcher_notification(
        destinataire=instance.utilisateur, canal=Notification.Canal.SMS,
        evenement=evenement, message=message, sujet='Statut de votre compte livreur',
    )


# ═══════════════════════════════════════════════════════════════════════
# NOTE 1 — Choix à ajouter dans apps_notification/models.py > Notification.Evenement :
#
#   LIVREUR_SUSPENDU = 'LIVR_SUSPEND', _('Compte livreur suspendu')
#   LIVREUR_REACTIVE = 'LIVR_REACTIVE', _('Compte livreur réactivé')
#
# Sans ces entrées, le receiver §4 retombe sur un événement générique
# existant (avec un avertissement en log) plutôt que d'échouer.
#
# NOTE 2 — §2 suppose que Livraison.Statut contient bien REFUSEE (c'est
# le cas dans le modèle fourni) ; si ce choix est retiré un jour, retirez-
# le aussi du tuple de statuts « fin de course » ci-dessus.
#
# NOTE 3 — §2 remet le livreur à ACTIF uniquement s'il est encore
# EN_MISSION au moment du update (garde optimiste) ; si entre-temps un
# admin l'a mis PAUSE/SUSPENDU manuellement, ce choix n'est pas écrasé.
# ═══════════════════════════════════════════════════════════════════════