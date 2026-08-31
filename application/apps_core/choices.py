# ═══════════════════════════════════════════════════════════════════════
# apps_core/choices.py
# Choix (TextChoices) PARTAGÉS entre toutes les apps SwiftDrop.
# Centraliser ici évite les imports circulaires entre apps_catalogue,
# apps_livraison, apps_livreur, apps_entreprise, etc.
# ═══════════════════════════════════════════════════════════════════════
from django.db import models
from django.utils.translation import gettext_lazy as _


class TypeVehicule(models.TextChoices):
    """
    Référentiel unique des véhicules. Utilisé par :
      - Livreur.type_vehicule (véhicule réellement possédé)
      - Produit.vehicule_minimum_requis (contrainte poids/volume)
      - CoefficientVehicule (majoration tarifaire par véhicule)
    """
    VELO        = 'VELO',        _('Vélo')
    MOTO        = 'MOTO',        _('Moto')
    TRICYCLE    = 'TRICYCLE',    _('Tricycle motorisé')
    VOITURE     = 'VOITURE',     _('Voiture')
    CAMIONNETTE = 'CAMIONNETTE', _('Camionnette')
    CAMION      = 'CAMION',      _('Camion (gros volume)')


class QualiteProduit(models.TextChoices):
    """
    Nature du produit défini à l'enregistrement — détermine le véhicule
    minimum requis pour le transport (utilisé pour calculer les frais).
    """
    LEGER  = 'LEGER',  _('Léger (moto compatible)')
    LOURD  = 'LOURD',  _('Lourd / volumineux (véhicule requis)')
    MIXTE  = 'MIXTE',  _('Mixte (dépend du produit précis)')


class TypeEntreprise(models.TextChoices):
    """
    Type d'activité de l'entreprise vis-à-vis de la vente en ligne.
    Une entreprise MIXTE peut stocker à la fois des produits Yopishop
    (vendus en ligne) et des produits hors-ligne dans les mêmes entrepôts.
    """
    VENDEUR_EN_LIGNE  = 'VENDEUR_LIGNE', _('Vendeur en ligne uniquement (Yopishop)')
    VENDEUR_PHYSIQUE  = 'VENDEUR_PHYS',  _('Vendeur physique uniquement (hors-ligne)')
    MIXTE             = 'MIXTE',         _('Mixte (en ligne + hors-ligne)')


class OrigineCommande(models.TextChoices):
    """
    Qui a initié la livraison :
      - YOPISHOP  : commande passée par un client final sur Yopishop.
        C'est la PLATEFORME (admin) qui réceptionne la commande en 1er.
      - ENTREPRISE: l'entreprise elle-même envoie la demande de livraison
        à la plateforme (produit non vendu en ligne).
    """
    YOPISHOP   = 'YOPISHOP',   _('Commande en ligne (Yopishop)')
    ENTREPRISE = 'ENTREPRISE', _('Demande manuelle de l\'entreprise')


class TypeFacturationLivraison(models.TextChoices):
    """
    Détermine comment les frais de livraison d'une Livraison sont traités.
    Règles métier (fixées, ne pas sur-optimiser) :
      - Livraison 100% Yopishop      -> GRATUITE (commission 10% prélevée)
      - Livraison 100% hors-ligne    -> FACTUREE_ZONE (frais zone/véhicule)
      - Livraison MIXTE (les 2)      -> FACTUREE_ZONE (frais zone uniquement,
        pas de commission calculée sur la part en ligne — décision produit
        volontairement simplifiée, cf. consignes métier)
    """
    GRATUITE_COMMISSION = 'GRATUITE_COM', _('Gratuite pour le client (commission Yopishop 10%)')
    FACTUREE_ZONE        = 'FACTUREE_ZONE', _('Facturée selon la zone / véhicule')


class CyclePaiementEntreprise(models.TextChoices):
    QUOTIDIEN    = 'QUOTIDIEN',    _('Quotidien')
    HEBDOMADAIRE = 'HEBDOMADAIRE', _('Hebdomadaire')
    MENSUEL      = 'MENSUEL',      _('Mensuel')


class MethodePaiementSortant(models.TextChoices):
    """Moyens par lesquels la plateforme paie une entreprise."""
    MTN_MOMO    = 'MTN_MOMO',    _('MTN Mobile Money')
    ORANGE_MONEY = 'ORANGE_MONEY', _('Orange Money')
    VIREMENT_BANCAIRE = 'VIREMENT', _('Virement bancaire')
    ESPECES     = 'ESPECES',     _('Espèces (retrait agence)')


class StatutLotPaiement(models.TextChoices):
    EN_PREPARATION      = 'PREPARATION', _('En préparation')
    PRET_A_ENVOYER      = 'PRET',        _('Prêt à envoyer')
    ENVOYE               = 'ENVOYE',      _('Envoyé (preuve jointe)')
    CONFIRME_ENTREPRISE  = 'CONFIRME',    _('Confirmé par l\'entreprise')
    LITIGE                = 'LITIGE',     _('En litige')


class StatutReceptionLivraison(models.TextChoices):
    """
    Étapes de réception/validation côté entreprise, distinctes selon
    l'origine de la commande (Yopishop vs Entreprise).
    """
    EN_ATTENTE_LIVRAISON = 'ATTENTE_LIV', _('En attente de livraison au client')
    LIVREE_INFOS_ENVOYEES = 'INFOS_ENVOYEES', _('Livrée — infos envoyées à l\'entreprise')
    RECEPTION_VALIDEE     = 'VALIDEE', _('Réception validée par l\'entreprise')
    PAIEMENT_ATTENTE      = 'PAIEMENT_ATTENTE', _('En attente du paiement du lot')
    PAIEMENT_RECU         = 'PAIEMENT_RECU', _('Paiement reçu et confirmé')


class TypeLivraisonDistance(models.TextChoices):
    """Pour LivraisonDirecte : comment le prix est déterminé."""
    INTRA_ZONE   = 'INTRA_ZONE',  _('Intra-zone (tarif zone)')
    INTER_VILLE  = 'INTER_VILLE', _('Inter-villes (tarif table)')
    AU_KM        = 'AU_KM',       _('Calcul au kilomètre')
    NEGOCIE       = 'NEGOCIE',     _('Prix négocié avec le client')
