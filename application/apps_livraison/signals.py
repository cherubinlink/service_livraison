# ═══════════════════════════════════════════════════════════════════════
# apps_livraison/signals.py
#
# 1) Notifie le livreur (et fixe enfin `date_attribution`, jamais posé
#    nulle part dans le code existant) dès qu'une Livraison B2B lui est
#    attribuée.
# 2) Notifie l'entreprise à chaque changement de statut significatif
#    d'une Livraison B2B (validée / refusée / en cours / livrée / échec)
#    — changer_statut() gère déjà la timeline et l'historique, mais ne
#    prévient personne.
# 3) Libère la réservation de stock des lignes d'une Livraison qui finit
#    REFUSEE / ECHEC / ANNULEE — LigneLivraison.save() réserve le stock
#    à la création (stock_entrepot.reserver()) mais rien ne le libérait
#    si la commande n'aboutit finalement pas.
# 4) Libère la réservation de stock d'une LigneLivraison supprimée avant
#    livraison effective (même logique que §3, au niveau de la ligne).
# 5) Notifie le livreur dès qu'une LivraisonDirecte lui est attribuée, et
#    notifie le client/l'entreprise à l'origine de la course à l'arrivée
#    ou en cas d'échec.
#
# Doit être importé dans apps_livraison/apps.py → ready().
# ═══════════════════════════════════════════════════════════════════════

import logging

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from apps_livraison.models import Livraison, LigneLivraison, LivraisonDirecte

logger = logging.getLogger('apps_livraison')

# Noms de méthode possibles pour libérer une réservation de stock, dans
# l'ordre de préférence. Voir NOTE en bas de fichier — StockEntrepot n'a
# pas été fourni, donc on reste défensif plutôt que de deviner un nom
# qui n'existerait pas et ferait planter le receiver.
METHODES_LIBERATION_STOCK = ('liberer_reservation', 'annuler_reservation', 'liberer')


def _liberer_stock_ligne(ligne, raison=''):
    stock = ligne.stock_entrepot
    if stock is None:
        return
    for nom_methode in METHODES_LIBERATION_STOCK:
        methode = getattr(stock, nom_methode, None)
        if callable(methode):
            methode(ligne.quantite)
            logger.info(
                "Stock réservé libéré (%s) pour %s × %d — %s",
                nom_methode, ligne.produit.nom, ligne.quantite, raison,
            )
            return
    logger.warning(
        "Aucune méthode de libération de stock trouvée sur StockEntrepot (%s) — "
        "réservation de %s × %d non libérée. Ajoutez une de ces méthodes : %s",
        stock.pk, ligne.produit.nom, ligne.quantite, METHODES_LIBERATION_STOCK,
    )


# ═══════════════════════════════════════════════════════════════════════
# §1 – ATTRIBUTION D'UN LIVREUR À UNE LIVRAISON B2B
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=Livraison)
def memoriser_livreur_et_statut_avant_sauvegarde(sender, instance, **kwargs):
    if instance.pk:
        try:
            avant = Livraison.objects.only('livreur_id', 'statut').get(pk=instance.pk)
            instance._livreur_id_avant = avant.livreur_id
            instance._statut_avant = avant.statut
        except Livraison.DoesNotExist:
            instance._livreur_id_avant = None
            instance._statut_avant = None
    else:
        instance._livreur_id_avant = None
        instance._statut_avant = None


@receiver(post_save, sender=Livraison)
def notifier_attribution_livreur(sender, instance, created, **kwargs):
    """
    Le champ `date_attribution` existe mais n'était posé nulle part, et
    le livreur n'était jamais averti qu'une course lui était attribuée.
    """
    livreur_avant = getattr(instance, '_livreur_id_avant', None)
    if created or livreur_avant is not None or instance.livreur_id is None:
        return  # pas une nouvelle attribution (None → livreur)

    # Renseigne date_attribution sans redéclencher ce signal (queryset.update
    # ne passe pas par save()).
    Livraison.objects.filter(pk=instance.pk).update(date_attribution=timezone.now())

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    utilisateur_livreur = getattr(instance.livreur, 'utilisateur', instance.livreur)
    message = (
        f"SwiftDrop : une nouvelle livraison ({instance.numero}) vous a été attribuée. "
        f"Client : {instance.nom_client} — {instance.get_priorite_display()}."
    )
    try:
        evenement = Notification.Evenement.LIVREUR_ATTRIBUE
    except AttributeError:
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.LIVREUR_ATTRIBUE manquant — "
            "ajoutez ce choix dans apps_notification/models.py"
        )

    _dispatcher_notification(
        destinataire=utilisateur_livreur, canal=Notification.Canal.SMS,
        evenement=evenement, message=message, sujet='Nouvelle livraison attribuée',
    )
    logger.info("Livraison %s attribuée et notifiée au livreur", instance.numero)


# ═══════════════════════════════════════════════════════════════════════
# §2 – NOTIFICATION ENTREPRISE SUR CHANGEMENT DE STATUT
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=Livraison)
def notifier_entreprise_changement_statut_livraison(sender, instance, created, **kwargs):
    statut_avant = getattr(instance, '_statut_avant', None)
    if created or statut_avant == instance.statut:
        return

    Statut = Livraison.Statut
    config = {
        Statut.VALIDEE: (
            'LIVRAISON_VALIDEE',
            f"SwiftDrop : votre livraison {instance.numero} a été validée et va être attribuée à un livreur.",
        ),
        Statut.REFUSEE: (
            'LIVRAISON_REFUSEE',
            f"SwiftDrop : votre livraison {instance.numero} a été refusée. "
            f"Motif : {instance.motif_refus or 'non précisé'}.",
        ),
        Statut.EN_COURS: (
            'LIVRAISON_EN_COURS',
            f"SwiftDrop : votre livraison {instance.numero} est en cours de livraison.",
        ),
        Statut.LIVREE: (
            'LIVRAISON_LIVREE',
            f"SwiftDrop : votre livraison {instance.numero} a été livrée avec succès. "
            f"Gain net : {instance.gain_entreprise} FCFA.",
        ),
        Statut.ECHEC: (
            'LIVRAISON_ECHEC',
            f"SwiftDrop : votre livraison {instance.numero} a échoué. "
            f"Motif : {instance.motif_echec or 'non précisé'}.",
        ),
    }
    if instance.statut not in config:
        return

    evenement_code, message = config[instance.statut]

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    try:
        evenement = getattr(Notification.Evenement, evenement_code)
    except AttributeError:
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.%s manquant — ajoutez ce choix dans apps_notification/models.py",
            evenement_code,
        )

    _dispatcher_notification(
        destinataire=instance.entreprise.utilisateur, canal=Notification.Canal.SMS,
        evenement=evenement, message=message, sujet=f"Livraison {instance.get_statut_display()}",
    )


# ═══════════════════════════════════════════════════════════════════════
# §3 – LIBÉRATION DU STOCK RÉSERVÉ SI LA LIVRAISON N'ABOUTIT PAS
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_save, sender=Livraison)
def liberer_stock_si_livraison_annulee_refusee_ou_echouee(sender, instance, created, **kwargs):
    statut_avant = getattr(instance, '_statut_avant', None)
    if created or statut_avant == instance.statut:
        return
    if instance.statut not in (Livraison.Statut.REFUSEE, Livraison.Statut.ECHEC, Livraison.Statut.ANNULEE):
        return

    for ligne in instance.lignes.select_related('stock_entrepot', 'produit'):
        _liberer_stock_ligne(ligne, raison=f"livraison {instance.numero} → {instance.statut}")


# ═══════════════════════════════════════════════════════════════════════
# §4 – LIBÉRATION DU STOCK SI UNE LIGNE EST SUPPRIMÉE AVANT LIVRAISON
# ═══════════════════════════════════════════════════════════════════════

@receiver(post_delete, sender=LigneLivraison)
def liberer_stock_ligne_supprimee(sender, instance, **kwargs):
    """
    Si une ligne est retirée d'une commande (avant que le stock ne soit
    réellement décrémenté au passage en LIVREE), la réservation posée à
    la création de la ligne doit être rendue.
    """
    livraison = instance.livraison
    if livraison is None or livraison.statut == Livraison.Statut.LIVREE:
        # Le stock a déjà été décrémenté définitivement à la livraison ;
        # ce n'est plus une "réservation" à libérer.
        return
    _liberer_stock_ligne(instance, raison=f"ligne supprimée de {livraison.numero}")


# ═══════════════════════════════════════════════════════════════════════
# §5 – LIVRAISON DIRECTE : ATTRIBUTION LIVREUR & NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════

@receiver(pre_save, sender=LivraisonDirecte)
def memoriser_livreur_et_statut_directe_avant_sauvegarde(sender, instance, **kwargs):
    if instance.pk:
        try:
            avant = LivraisonDirecte.objects.only('livreur_id', 'statut').get(pk=instance.pk)
            instance._livreur_id_avant = avant.livreur_id
            instance._statut_avant = avant.statut
        except LivraisonDirecte.DoesNotExist:
            instance._livreur_id_avant = None
            instance._statut_avant = None
    else:
        instance._livreur_id_avant = None
        instance._statut_avant = None


@receiver(post_save, sender=LivraisonDirecte)
def notifier_attribution_livreur_directe(sender, instance, created, **kwargs):
    livreur_avant = getattr(instance, '_livreur_id_avant', None)
    if created or livreur_avant is not None or instance.livreur_id is None:
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    utilisateur_livreur = getattr(instance.livreur, 'utilisateur', instance.livreur)
    message = (
        f"SwiftDrop : une course directe ({instance.numero}) vous a été attribuée. "
        f"Collecte : {instance.adresse_collecte[:60]} → {instance.nom_destinataire}."
    )
    try:
        evenement = Notification.Evenement.LIVREUR_ATTRIBUE
    except AttributeError:
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.LIVREUR_ATTRIBUE manquant — "
            "ajoutez ce choix dans apps_notification/models.py"
        )

    _dispatcher_notification(
        destinataire=utilisateur_livreur, canal=Notification.Canal.SMS,
        evenement=evenement, message=message, sujet='Nouvelle course attribuée',
    )


@receiver(post_save, sender=LivraisonDirecte)
def notifier_client_ou_entreprise_statut_directe(sender, instance, created, **kwargs):
    """
    Notifie le client inscrit (`client`, s'il existe) et/ou l'entreprise
    à l'origine de la course (`livraison_par_entreprise`) à la livraison
    ou en cas d'échec. NB : `nom_destinataire`/`telephone_destinataire`
    sont de simples champs texte (pas de compte Utilisateur) — voir NOTE
    en bas de fichier pour le suivi public via `token_suivi`.
    """
    statut_avant = getattr(instance, '_statut_avant', None)
    if created or statut_avant == instance.statut:
        return
    if instance.statut not in (LivraisonDirecte.Statut.LIVREE, LivraisonDirecte.Statut.ECHEC):
        return

    destinataires = []
    if instance.client_id:
        destinataires.append(instance.client)
    if instance.livraison_par_entreprise_id:
        destinataires.append(instance.livraison_par_entreprise.utilisateur)
    if not destinataires:
        return

    from apps_notification.signals import _dispatcher_notification
    from apps_notification.models import Notification

    if instance.statut == LivraisonDirecte.Statut.LIVREE:
        message = f"SwiftDrop : la course {instance.numero} a été livrée avec succès à {instance.nom_destinataire}."
        evenement_code = 'LIVRAISON_DIRECTE_LIVREE'
    else:
        message = f"SwiftDrop : la course {instance.numero} a échoué."
        evenement_code = 'LIVRAISON_DIRECTE_ECHEC'

    try:
        evenement = getattr(Notification.Evenement, evenement_code)
    except AttributeError:
        evenement = Notification.Evenement.STOCK_BAS
        logger.warning(
            "Notification.Evenement.%s manquant — ajoutez ce choix dans apps_notification/models.py",
            evenement_code,
        )

    for destinataire in destinataires:
        _dispatcher_notification(
            destinataire=destinataire, canal=Notification.Canal.SMS,
            evenement=evenement, message=message, sujet=f"Course {instance.get_statut_display()}",
        )


# ═══════════════════════════════════════════════════════════════════════
# NOTE 1 — Choix à ajouter dans apps_notification/models.py > Notification.Evenement :
#
#   LIVREUR_ATTRIBUE            = 'LIV_ATTRIBUE', _('Livraison attribuée au livreur')
#   LIVRAISON_VALIDEE            = 'LIV_VALIDEE', _('Livraison validée')
#   LIVRAISON_REFUSEE             = 'LIV_REFUSEE', _('Livraison refusée')
#   LIVRAISON_EN_COURS              = 'LIV_ENCOURS', _('Livraison en cours')
#   LIVRAISON_LIVREE                  = 'LIV_LIVREE', _('Livraison livrée')
#   LIVRAISON_ECHEC                     = 'LIV_ECHEC', _('Livraison en échec')
#   LIVRAISON_DIRECTE_LIVREE               = 'LIVD_LIVREE', _('Course directe livrée')
#   LIVRAISON_DIRECTE_ECHEC                   = 'LIVD_ECHEC', _('Course directe en échec')
#
# Sans ces entrées, les receivers ci-dessus retombent sur un événement
# générique existant (avec un avertissement en log) plutôt que d'échouer.
#
# NOTE 2 — §3/§4 supposent que StockEntrepot expose une méthode de
# libération de réservation ('liberer_reservation', 'annuler_reservation'
# ou 'liberer'), symétrique à `reserver()` déjà appelée dans
# LigneLivraison.save(). Ce modèle n'a pas été fourni ici : si son API
# réelle diffère, ajustez METHODES_LIBERATION_STOCK en tête de fichier.
#
# NOTE 3 — nom_destinataire / telephone_destinataire (et l'expéditeur)
# sur LivraisonDirecte ne sont pas forcément liés à un compte Utilisateur
# ; _dispatcher_notification() attend un Utilisateur. Pour prévenir ces
# personnes par SMS direct au numéro (sans compte), il faudra un canal
# dédié — ou exploiter la page de suivi publique via `token_suivi`.
# ═══════════════════════════════════════════════════════════════════════