# ═══════════════════════════════════════════════════════════════════════
# apps_notification/signals.py
#
# Définit les SIGNAUX CUSTOM utilisés par apps_core.Utilisateur
# (otp_genere, token_mdp_genere) ainsi que les receivers qui transforment
# ces événements en Notification envoyées réellement (SMS/WhatsApp/Email).
#
# apps_core/models.py fait :
#   from apps_notification.signals import otp_genere
#   otp_genere.send(sender=self.__class__, user=self, otp_code=self.code_otp)
#
# Ce fichier doit être importé au démarrage de l'app pour que les
# receivers soient connectés — voir apps_notification/apps.py (ready()).
# ═══════════════════════════════════════════════════════════════════════

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal, receiver

logger = logging.getLogger('apps_notification')


# ═══════════════════════════════════════════════════════════════════════
# §1 – SIGNAUX CUSTOM (déclarés ici, importés depuis apps_core)
# ═══════════════════════════════════════════════════════════════════════

# Envoyé quand Utilisateur.generer_otp() crée un nouveau code OTP.
# Args attendus au .send() : sender, user, otp_code
otp_genere = Signal()

# Envoyé quand Utilisateur.generer_token_reinit_mdp() crée un token.
# Args attendus au .send() : sender, user, token
token_mdp_genere = Signal()

# Envoyé quand un lot de paiement est marqué "ENVOYE" (preuve jointe),
# pour notifier l'entreprise qu'un paiement l'attend.
lot_paiement_envoye = Signal()

# Envoyé quand une entreprise est désactivée pour inactivité (30j).
entreprise_desactivee_inactivite = Signal()

# Envoyé quand un stock passe sous son seuil d'alerte / rupture.
stock_alerte_declenchee = Signal()


# ═══════════════════════════════════════════════════════════════════════
# §2 – HELPERS D'ENVOI (à brancher sur vos providers réels)
# ═══════════════════════════════════════════════════════════════════════

def _envoyer_sms(telephone: str, message: str) -> dict:
    """
    Point d'intégration Africa's Talking (ou autre provider SMS).
    Retourne un dict {'success': bool, 'ref_externe': str, 'erreur': str}.
    Remplacer le corps par le vrai appel API en production.
    """
    try:
        # Exemple d'intégration réelle (décommenter et configurer) :
        #
        # import africastalking
        # from django.conf import settings
        # africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
        # sms = africastalking.SMS
        # response = sms.send(message, [telephone])
        # ref = response['SMSMessageData']['Recipients'][0]['messageId']
        # return {'success': True, 'ref_externe': ref, 'erreur': ''}

        logger.info("SMS [simulé] → %s : %s", telephone, message)
        return {'success': True, 'ref_externe': 'SIMULATION', 'erreur': ''}
    except Exception as exc:  # pragma: no cover
        logger.exception("Échec envoi SMS vers %s", telephone)
        return {'success': False, 'ref_externe': '', 'erreur': str(exc)}


def _envoyer_whatsapp(telephone: str, message: str) -> dict:
    """Point d'intégration WhatsApp Business API."""
    try:
        logger.info("WhatsApp [simulé] → %s : %s", telephone, message)
        return {'success': True, 'ref_externe': 'SIMULATION', 'erreur': ''}
    except Exception as exc:  # pragma: no cover
        logger.exception("Échec envoi WhatsApp vers %s", telephone)
        return {'success': False, 'ref_externe': '', 'erreur': str(exc)}


def _envoyer_email(email: str, sujet: str, message: str) -> dict:
    """Point d'intégration Email (Django email backend / provider tiers)."""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        send_mail(
            subject=sujet, message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@swiftdrop.cm'),
            recipient_list=[email], fail_silently=False,
        )
        return {'success': True, 'ref_externe': '', 'erreur': ''}
    except Exception as exc:  # pragma: no cover
        logger.exception("Échec envoi Email vers %s", email)
        return {'success': False, 'ref_externe': '', 'erreur': str(exc)}


def _dispatcher_notification(destinataire, canal, evenement, message, telephone='', sujet=''):
    """
    Crée l'entrée Notification (journal) puis tente l'envoi réel,
    et met à jour le statut/erreur en conséquence.
    """
    from apps_notification.models import Notification

    notif = Notification.objects.create(
        destinataire=destinataire,
        canal=canal,
        evenement=evenement,
        telephone=telephone or destinataire.telephone,
        sujet=sujet,
        message=message,
        statut_envoi=Notification.StatutEnvoi.EN_ATTENTE,
    )

    if canal == Notification.Canal.SMS:
        resultat = _envoyer_sms(notif.telephone, message)
    elif canal == Notification.Canal.WHATSAPP:
        resultat = _envoyer_whatsapp(notif.telephone, message)
    elif canal == Notification.Canal.EMAIL:
        resultat = _envoyer_email(destinataire.email, sujet, message)
    else:
        resultat = {'success': False, 'ref_externe': '', 'erreur': 'Canal PUSH non implémenté ici'}

    notif.nb_tentatives += 1
    if resultat['success']:
        notif.statut_envoi = Notification.StatutEnvoi.ENVOYE
        notif.ref_externe = resultat['ref_externe']
    else:
        notif.statut_envoi = Notification.StatutEnvoi.ECHEC
        notif.erreur = resultat['erreur']
    notif.save(update_fields=['nb_tentatives', 'statut_envoi', 'ref_externe', 'erreur'])
    return notif


# ═══════════════════════════════════════════════════════════════════════
# §3 – RECEIVERS : OTP & RÉINITIALISATION MOT DE PASSE
# ═══════════════════════════════════════════════════════════════════════

@receiver(otp_genere)
def envoyer_otp_par_sms(sender, user, otp_code, **kwargs):
    """
    Reçoit le signal envoyé par Utilisateur.generer_otp().
    Envoie le code par SMS (et WhatsApp si le numéro est renseigné et que
    l'utilisateur est une entreprise ayant activé cette préférence).
    """
    from apps_notification.models import Notification

    message = (
        f"SwiftDrop : votre code de vérification est {otp_code}. "
        f"Valable 10 minutes. Ne le partagez avec personne."
    )
    _dispatcher_notification(
        destinataire=user, canal=Notification.Canal.SMS,
        evenement=Notification.Evenement.OTP_ENVOYE,
        message=message, sujet='Code de vérification',
    )
    logger.info("OTP envoyé à l'utilisateur %s", user.email)


@receiver(token_mdp_genere)
def envoyer_lien_reinitialisation_mdp(sender, user, token, **kwargs):
    """
    Reçoit le signal envoyé par Utilisateur.generer_token_reinit_mdp().
    Envoie le lien de réinitialisation par email (canal privilégié pour
    la sécurité) et, en secours, par SMS si l'email n'est pas vérifié.
    """
    from django.conf import settings
    from apps_notification.models import Notification

    base_url = getattr(settings, 'FRONTEND_URL', 'https://app.swiftdrop.cm')
    lien = f"{base_url}/reinitialiser-mot-de-passe/{token}/"
    message = (
        f"Bonjour {user.nom}, cliquez sur ce lien pour réinitialiser votre "
        f"mot de passe SwiftDrop (valable 1h) : {lien}"
    )

    if user.email_verifie and user.email:
        _dispatcher_notification(
            destinataire=user, canal=Notification.Canal.EMAIL,
            evenement=Notification.Evenement.MDP_REINIT_DEMANDE,
            message=message, sujet='Réinitialisation de votre mot de passe',
        )
    else:
        _dispatcher_notification(
            destinataire=user, canal=Notification.Canal.SMS,
            evenement=Notification.Evenement.MDP_REINIT_DEMANDE,
            message=f"SwiftDrop : réinitialisez votre mot de passe ici : {lien}",
        )
    logger.info("Lien de réinitialisation envoyé à %s", user.email)


# ═══════════════════════════════════════════════════════════════════════
# §4 – RECEIVERS : ÉVÉNEMENTS PAIEMENT / INACTIVITÉ / STOCK
# (branchés sur les nouveaux signaux custom déclarés plus haut)
# ═══════════════════════════════════════════════════════════════════════

@receiver(lot_paiement_envoye)
def notifier_lot_paiement_envoye(sender, lot, **kwargs):
    """
    lot : instance de apps_transaction.LotPaiementEntreprise
    Prévient le contact principal de l'entreprise qu'un paiement a été
    envoyé avec preuve, et qu'il doit confirmer la réception.
    """
    from apps_notification.models import Notification

    utilisateur = lot.entreprise.utilisateur
    message = (
        f"SwiftDrop : un paiement de {lot.montant_net_a_payer} FCFA vient de "
        f"vous être envoyé (réf. {lot.reference}) pour la période "
        f"{lot.periode_debut} → {lot.periode_fin}. Merci de confirmer la "
        f"réception depuis votre tableau de bord entreprise."
    )
    canal = Notification.Canal.WHATSAPP if lot.entreprise.notification_whatsapp else Notification.Canal.SMS
    _dispatcher_notification(
        destinataire=utilisateur, canal=canal,
        evenement=Notification.Evenement.LOT_PAIEMENT_ENVOYE,
        message=message, sujet='Paiement envoyé',
    )


@receiver(entreprise_desactivee_inactivite)
def notifier_desactivation_inactivite(sender, entreprise, **kwargs):
    """
    entreprise : instance de apps_entreprise.Entreprise
    Prévient l'entreprise de sa désactivation et de la possibilité de
    payer des frais de gardiennage pour éviter/annuler le retour produits.
    """
    from apps_notification.models import Notification

    utilisateur = entreprise.utilisateur
    message = (
        f"SwiftDrop : votre compte {entreprise.nom_affichage} a été désactivé "
        f"après 30 jours sans activité de livraison. Vos produits en stock "
        f"seront retournés. Contactez l'administration pour régulariser via "
        f"des frais de gardiennage et réactiver votre compte."
    )
    _dispatcher_notification(
        destinataire=utilisateur, canal=Notification.Canal.SMS,
        evenement=Notification.Evenement.ENT_DESACTIVEE_INACTIVITE,
        message=message, sujet='Compte désactivé pour inactivité',
    )


@receiver(stock_alerte_declenchee)
def notifier_alerte_stock(sender, alerte, **kwargs):
    """
    alerte : instance de apps_catalogue.AlerteStock
    Prévient l'entreprise (et journalise pour l'admin) qu'un produit est
    en stock bas ou en rupture dans un entrepôt précis.
    """
    from apps_notification.models import Notification

    stock = alerte.stock_entrepot
    utilisateur = stock.produit.entreprise.utilisateur
    type_label = alerte.get_type_alerte_display()
    message = (
        f"SwiftDrop : {type_label} pour '{stock.produit.nom}' à l'entrepôt "
        f"{stock.entrepot.nom} — quantité restante : {alerte.quantite_au_moment}."
    )
    _dispatcher_notification(
        destinataire=utilisateur, canal=Notification.Canal.SMS,
        evenement=Notification.Evenement.STOCK_BAS,
        message=message, sujet=type_label,
    )