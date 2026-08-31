# ═══════════════════════════════════════════════════════════════════════
# apps_evaluation/signals.py
#
# 1) Recalcule automatiquement le score de fiabilité de l'entreprise dès
#    qu'une nouvelle Evaluation est créée — Entreprise.recalculer_score()
#    existe déjà mais n'était appelé nulle part automatiquement.
# 2) Notifie le livreur de la note qu'il vient de recevoir.
# 3) Alerte l'équipe qualité (support) quand une évaluation est mauvaise
#    (note globale ≤ 2 ou "non recommandé"), pour un suivi rapproché.
#
# Doit être importé dans apps_evaluation/apps.py → ready().
# ═══════════════════════════════════════════════════════════════════════

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps_evaluation.models import Evaluation

logger = logging.getLogger('apps_evaluation')

SEUIL_NOTE_ALERTE = 2  # note globale à partir de laquelle on alerte le support


# ═══════════════════════════════════════════════════════════════════════
# §1 – RECALCUL DU SCORE DE FIABILITÉ DE L'ENTREPRISE
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=Evaluation)
def recalculer_score_entreprise_apres_evaluation(sender, instance, created, **kwargs):
    """
    Chaque nouvelle évaluation impacte le score_fiabilite de l'entreprise
    (via la moyenne des notes, cf. Entreprise.recalculer_score()). Sans ce
    receiver, le score restait figé tant qu'aucune action manuelle ne
    déclenchait le recalcul.
    """
    if not created:
        return

    entreprise = getattr(instance.livraison, 'entreprise', None)
    if entreprise is None:
        logger.warning(
            "Evaluation %s : livraison %s sans entreprise associée, score non recalculé",
            instance.pk, instance.livraison_id,
        )
        return

    entreprise.recalculer_score()
    logger.info(
        "Score de fiabilité recalculé pour %s suite à l'évaluation %s (%s/5)",
        entreprise.raison_sociale, instance.pk, instance.note_globale,
    )


# ═══════════════════════════════════════════════════════════════════════
# §2 – NOTIFICATION DU LIVREUR
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=Evaluation)
def notifier_livreur_de_sa_note(sender, instance, created, **kwargs):
    """
    Prévient le livreur de la livraison notée dès qu'il reçoit une note,
    en particulier note_livreur qui lui est spécifiquement destinée.
    """
    if not created:
        return

    livreur = getattr(instance.livraison, 'livreur', None)
    if livreur is None:
        logger.warning(
            "Evaluation %s : aucun livreur associé à la livraison %s, pas de notification",
            instance.pk, instance.livraison_id,
        )
        return

    utilisateur_livreur = getattr(livreur, 'utilisateur', livreur)

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    note_affichee = instance.note_livreur if instance.note_livreur is not None else instance.note_globale
    message = (
        f"SwiftDrop : vous avez reçu une note de {note_affichee}/5 pour la livraison "
        f"{instance.livraison.numero}."
    )
    if instance.commentaire:
        message += f" Commentaire du client : « {instance.commentaire[:120]} »"

    try:
        evenement = Notification.Evenement.EVALUATION_RECUE
    except AttributeError:
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.EVALUATION_RECUE manquant — "
            "ajoutez ce choix dans apps_notification/models.py"
        )

    _dispatcher_notification(
        destinataire=utilisateur_livreur, canal=Notification.Canal.SMS,
        evenement=evenement, message=message, sujet='Nouvelle évaluation reçue',
    )


# ═══════════════════════════════════════════════════════════════════════
# §3 – ALERTE QUALITÉ SUR ÉVALUATION BASSE
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=Evaluation)
def alerter_support_si_evaluation_basse(sender, instance, created, **kwargs):
    """
    Remonte les évaluations problématiques (note globale basse ou client
    ne recommandant pas le service) à l'équipe support/qualité, pour un
    suivi proactif plutôt que de laisser ces retours invisibles.
    """
    if not created:
        return
    if instance.note_globale > SEUIL_NOTE_ALERTE and instance.recommande:
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification
    from apps_core.models import Utilisateur

    message = (
        f"SwiftDrop [Qualité] : évaluation basse sur la livraison {instance.livraison.numero} "
        f"— note globale {instance.note_globale}/5, recommandé : {'oui' if instance.recommande else 'non'}."
    )
    if instance.commentaire:
        message += f" Commentaire : « {instance.commentaire[:200]} »"

    try:
        evenement = Notification.Evenement.EVALUATION_BASSE
    except AttributeError:
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.EVALUATION_BASSE manquant — "
            "ajoutez ce choix dans apps_notification/models.py"
        )

    for agent in Utilisateur.objects.filter(is_staff=True, est_actif=True):
        _dispatcher_notification(
            destinataire=agent, canal=Notification.Canal.EMAIL,
            evenement=evenement, message=message, sujet='Alerte qualité — évaluation basse',
        )
    logger.info(
        "Alerte qualité envoyée pour l'évaluation %s (note %s/5)",
        instance.pk, instance.note_globale,
    )


# ═══════════════════════════════════════════════════════════════════════
# NOTE 1 — Choix à ajouter dans apps_notification/models.py > Notification.Evenement :
#
#   EVALUATION_RECUE = 'EVAL_RECUE', _('Évaluation reçue par le livreur')
#   EVALUATION_BASSE = 'EVAL_BASSE', _('Alerte qualité — évaluation basse')
#
# Sans ces entrées, les receivers ci-dessus retombent sur un événement
# générique existant (avec un avertissement en log) plutôt que d'échouer.
#
# NOTE 2 — §2 et §3 supposent que Livraison possède un champ `livreur`
# (FK vers un profil Livreur ou directement vers Utilisateur) et que ce
# modèle n'a pas été fourni ici. Si le champ s'appelle différemment,
# ajustez `getattr(instance.livraison, 'livreur', None)` en conséquence.
#
# NOTE 3 — §3 suppose un champ `est_actif` sur Utilisateur pour filtrer
# les agents actifs ; adaptez le filtre à votre modèle réel si besoin.
# ═══════════════════════════════════════════════════════════════════════