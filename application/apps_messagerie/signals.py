# ═══════════════════════════════════════════════════════════════════════
# apps_messagerie/signals.py
#
# 1) Maintient Conversation.date_dernier_msg à jour à chaque nouveau
#    message (indispensable : Conversation.Meta.ordering trie dessus,
#    et le champ n'est jamais mis à jour ailleurs dans models.py).
# 2) Notifie automatiquement l'AUTRE participant qu'un nouveau message
#    vient d'arriver (SMS/push), sauf pour les messages SYSTEME.
#
# Doit être importé dans apps_messagerie/apps.py → ready() pour que les
# receivers soient connectés au démarrage.
# ═══════════════════════════════════════════════════════════════════════

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps_messagerie.models import Conversation, Message

logger = logging.getLogger('apps_messagerie')


# ═══════════════════════════════════════════════════════════════════════
# §1 – VALIDATION : un même utilisateur ne peut pas discuter avec lui-même
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=Conversation)
def valider_participants_distincts(sender, instance, **kwargs):
    if instance.participant_1_id == instance.participant_2_id:
        raise ValueError(
            "Une conversation ne peut pas avoir le même utilisateur "
            "comme participant_1 et participant_2."
        )


# ═══════════════════════════════════════════════════════════════════════
# §2 – MISE À JOUR AUTO DE date_dernier_msg SUR LA CONVERSATION
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=Message)
def mettre_a_jour_date_dernier_message(sender, instance, created, **kwargs):
    """
    À chaque message créé, remonte la conversation en tête de liste
    (Conversation.Meta.ordering = ['-date_dernier_msg']).
    """
    if not created:
        return
    Conversation.objects.filter(pk=instance.conversation_id).update(
        date_dernier_msg=instance.date_envoi or timezone.now()
    )


# ═══════════════════════════════════════════════════════════════════════
# §3 – NOTIFICATION DU DESTINATAIRE À CHAQUE NOUVEAU MESSAGE
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=Message)
def notifier_nouveau_message(sender, instance, created, **kwargs):
    """
    Prévient l'autre participant de la conversation (pas l'expéditeur)
    qu'un nouveau message est arrivé — sauf messages système et messages
    sans expéditeur identifié.
    """
    if not created or instance.type_contenu == Message.TypeContenu.SYSTEME:
        return
    if instance.expediteur_id is None:
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    conversation = instance.conversation
    destinataire = conversation.get_autre_participant(instance.expediteur)
    if destinataire is None:
        return

    apercu = instance.contenu[:80] + ('…' if len(instance.contenu) > 80 else '')
    if instance.type_contenu == Message.TypeContenu.FICHIER:
        apercu = "📎 Fichier joint" + (f" — {apercu}" if apercu else "")

    message = f"SwiftDrop : nouveau message de {instance.expediteur.nom} : {apercu}"

    # Canal PUSH privilégié si l'utilisateur a un device_token enregistré,
    # sinon repli sur SMS (pas de dépendance à des préférences propres à
    # l'entreprise ici, contrairement aux notifications de livraison).
    canal = Notification.Canal.PUSH if destinataire.device_token else Notification.Canal.SMS

    try:
        _dispatcher_notification(
            destinataire=destinataire, canal=canal,
            evenement=Notification.Evenement.NOUVEAU_MESSAGE,
            message=message, sujet='Nouveau message',
        )
    except AttributeError:
        # Sécurité si Notification.Evenement.NOUVEAU_MESSAGE n'a pas encore
        # été ajouté côté apps_notification/models.py — voir note en bas
        # de fichier. On ne bloque jamais l'envoi du message pour autant.
        logger.warning(
            "Notification.Evenement.NOUVEAU_MESSAGE manquant — "
            "ajoutez ce choix dans apps_notification/models.py"
        )


# ═══════════════════════════════════════════════════════════════════════
# NOTE — Choix à ajouter dans apps_notification/models.py > Notification.Evenement :
#
#   NOUVEAU_MESSAGE = 'NOUVEAU_MSG', _('Nouveau message reçu')
#
# Sans cette entrée, notifier_nouveau_message() logue un avertissement
# et n'envoie pas la notification, mais n'empêche jamais la création
# du message lui-même.
# ═══════════════════════════════════════════════════════════════════════