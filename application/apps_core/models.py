from django.db import models

# Create your models here.
import uuid
import secrets
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps_core.choices import TypeVehicule
from apps_core.validators import tel_validator, niu_validator, upload_path  


# ═══════════════════════════════════════════════════════════════════════
# §1 – AUTHENTIFICATION & UTILISATEURS
# ═══════════════════════════════════════════════════════════════════════

class UtilisateurManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('L\'adresse email est obligatoire.'))
        email = self.normalize_email(email)
        extra_fields.setdefault('est_actif', True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', Utilisateur.Role.ADMIN)
        extra_fields.setdefault('est_actif', True)
        if not extra_fields.get('is_staff'):
            raise ValueError(_('Le superuser doit avoir is_staff=True.'))
        if not extra_fields.get('is_superuser'):
            raise ValueError(_('Le superuser doit avoir is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)

    def admins(self):
        return self.filter(role=Utilisateur.Role.ADMIN, est_actif=True)

    def entreprises(self):
        return self.filter(role=Utilisateur.Role.ENTREPRISE, est_actif=True)

    def livreurs(self):
        return self.filter(role=Utilisateur.Role.LIVREUR, est_actif=True)

    def clients(self):
        return self.filter(role=Utilisateur.Role.CLIENT, est_actif=True)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """Modèle utilisateur central SwiftDrop (RBAC)."""

    class Role(models.TextChoices):
        ADMIN      = 'ADMIN',      _('Administrateur')
        ENTREPRISE = 'ENTREPRISE', _('Entreprise')
        LIVREUR    = 'LIVREUR',    _('Livreur')
        CLIENT     = 'CLIENT',     _('Client Direct')

    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email     = models.EmailField(_('Adresse email'), unique=True, db_index=True)
    nom       = models.CharField(_('Nom complet'), max_length=150)
    telephone = models.CharField(_('Téléphone'), max_length=20, blank=True, validators=[tel_validator])
    role      = models.CharField(_('Rôle'), max_length=20, choices=Role.choices, default=Role.CLIENT, db_index=True)

    photo_profil = models.ImageField(_('Photo de profil'), upload_to=upload_path, blank=True, null=True)
    bio          = models.TextField(_('Bio / Description'), blank=True)
    langue       = models.CharField(_('Langue préférée'), max_length=10,
                                     choices=[('fr', 'Français'), ('en', 'English')], default='fr')

    est_actif           = models.BooleanField(_('Compte actif'), default=True)
    is_staff             = models.BooleanField(_('Accès admin Django'), default=False)
    email_verifie         = models.BooleanField(_('Email vérifié'), default=False)
    telephone_verifie     = models.BooleanField(_('Téléphone vérifié (OTP)'), default=False)
    code_otp               = models.CharField(_('Code OTP en cours'), max_length=6, blank=True)
    code_otp_expiration     = models.DateTimeField(_('Expiration OTP'), null=True, blank=True)
    token_reinit_mdp        = models.CharField(_('Token réinitialisation MDP'), max_length=64, blank=True)
    token_reinit_expiration = models.DateTimeField(_('Expiration token MDP'), null=True, blank=True)
    tentatives_connexion     = models.PositiveSmallIntegerField(_('Tentatives échouées'), default=0)
    compte_bloque_jusqu_au   = models.DateTimeField(_('Compte bloqué jusqu\'au'), null=True, blank=True)

    date_creation         = models.DateTimeField(_('Date de création'), default=timezone.now)
    derniere_connexion_at = models.DateTimeField(_('Dernière connexion'), null=True, blank=True)
    derniere_connexion_ip = models.GenericIPAddressField(_('IP dernière connexion'), blank=True, null=True)
    device_token           = models.CharField(_('Token appareil mobile (push)'), max_length=255, blank=True,
                                                help_text=_('FCM token pour les notifications push'))

    objects = UtilisateurManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['nom']

    class Meta:
        verbose_name        = _('Utilisateur')
        verbose_name_plural = _('Utilisateurs')
        ordering            = ['-date_creation']
        indexes = [
            models.Index(fields=['email', 'role']),
            models.Index(fields=['role', 'est_actif']),
        ]

    def __str__(self):
        return f"{self.nom} <{self.email}> [{self.get_role_display()}]"

    @property
    def est_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def est_entreprise_user(self):
        return self.role == self.Role.ENTREPRISE

    @property
    def est_livreur_user(self):
        return self.role == self.Role.LIVREUR

    @property
    def est_client(self):
        return self.role == self.Role.CLIENT

    def generer_otp(self):
        import random
        from apps_notification.signals import otp_genere
        self.code_otp = str(random.randint(100000, 999999))
        self.code_otp_expiration = timezone.now() + timezone.timedelta(minutes=10)
        self.save(update_fields=['code_otp', 'code_otp_expiration'])
        otp_genere.send(sender=self.__class__, user=self, otp_code=self.code_otp)
        return self.code_otp

    def otp_valide(self, code):
        return (
            self.code_otp == code and
            self.code_otp_expiration and
            timezone.now() < self.code_otp_expiration
        )

    def generer_token_reinit_mdp(self):
        from apps_notification.signals import token_mdp_genere
        self.token_reinit_mdp = secrets.token_urlsafe(48)
        self.token_reinit_expiration = timezone.now() + timezone.timedelta(hours=1)
        self.save(update_fields=['token_reinit_mdp', 'token_reinit_expiration'])
        token_mdp_genere.send(sender=self.__class__, user=self, token=self.token_reinit_mdp)
        return self.token_reinit_mdp

    def enregistrer_connexion(self, ip=None):
        self.derniere_connexion_at = timezone.now()
        self.derniere_connexion_ip = ip
        self.tentatives_connexion = 0
        self.save(update_fields=['derniere_connexion_at', 'derniere_connexion_ip', 'tentatives_connexion'])

    @property
    def compte_bloque(self):
        if self.compte_bloque_jusqu_au:
            return timezone.now() < self.compte_bloque_jusqu_au
        return False
    
    @property
    def is_active(self):
        """
        Django (admin, ModelBackend...) attend un attribut `is_active` sur
        le modèle utilisateur — on le fait pointer vers `est_actif` plutôt
        que de dupliquer un second champ en base.
        """
        return self.est_actif


# ═══════════════════════════════════════════════════════════════════════
# §2 – GÉOGRAPHIE
# ═══════════════════════════════════════════════════════════════════════

class Pays(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom       = models.CharField(_('Nom'), max_length=100, unique=True)
    code_iso  = models.CharField(_('Code ISO 3166-1 alpha-2'), max_length=2, unique=True)
    indicatif = models.CharField(_('Indicatif téléphonique'), max_length=6)
    devise    = models.CharField(_('Devise'), max_length=10, default='FCFA')
    est_actif = models.BooleanField(_('Actif'), default=True)

    class Meta:
        verbose_name        = _('Pays')
        verbose_name_plural = _('Pays')
        ordering            = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.code_iso})"


class Ville(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pays      = models.ForeignKey(Pays, on_delete=models.PROTECT, related_name='villes')
    nom       = models.CharField(_('Nom de la ville'), max_length=100)
    code      = models.CharField(_('Code ville'), max_length=10, unique=True,
                                  help_text=_('Ex: DLA pour Douala'))
    latitude  = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    est_active = models.BooleanField(_('Ville active'), default=True)
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Ville')
        verbose_name_plural = _('Villes')
        ordering            = ['pays', 'nom']
        unique_together     = [['pays', 'nom']]

    def __str__(self):
        return f"{self.nom} – {self.pays.nom}"


class Zone(models.Model):
    """Zone de livraison. Prix de RÉFÉRENCE = tarif moto (véhicule de base)."""
    id     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ville  = models.ForeignKey(Ville, on_delete=models.CASCADE, related_name='zones')
    nom    = models.CharField(_('Nom de la zone'), max_length=100)
    description = models.TextField(_('Description'), blank=True)

    prix_livraison = models.DecimalField(
        _('Prix livraison de référence — véhicule MOTO (FCFA)'),
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    prix_dynamique      = models.BooleanField(_('Tarification dynamique (heure pointe)'), default=False)
    coefficient_pointe  = models.DecimalField(
        _('Coefficient heure de pointe'), max_digits=4, decimal_places=2, default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('1.00')), MaxValueValidator(Decimal('3.00'))]
    )
    heure_pointe_debut = models.TimeField(null=True, blank=True)
    heure_pointe_fin   = models.TimeField(null=True, blank=True)

    latitude_centre  = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude_centre = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    rayon_km         = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    est_active        = models.BooleanField(_('Zone active'), default=True)
    date_creation      = models.DateTimeField(auto_now_add=True)
    date_modification  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Zone')
        verbose_name_plural = _('Zones')
        ordering            = ['ville', 'nom']
        unique_together     = [['ville', 'nom']]
        indexes             = [models.Index(fields=['ville', 'est_active'])]

    def __str__(self):
        return f"{self.nom} ({self.ville.nom}) – {self.prix_livraison} FCFA"

    def get_prix_reference_actuel(self):
        """Prix de base (véhicule MOTO) selon l'heure — AVANT majoration véhicule."""
        if not self.prix_dynamique:
            return self.prix_livraison
        now = timezone.localtime().time()
        if (self.heure_pointe_debut and self.heure_pointe_fin and
                self.heure_pointe_debut <= now <= self.heure_pointe_fin):
            return (self.prix_livraison * self.coefficient_pointe).quantize(Decimal('0.01'))
        return self.prix_livraison

    def get_prix_pour_vehicule(self, type_vehicule):
        """
        Prix final de livraison dans cette zone POUR UN VÉHICULE DONNÉ.
        = prix_reference (avec pointe éventuelle) x coefficient véhicule + supplément fixe.
        """
        base = self.get_prix_reference_actuel()
        try:
            coef = CoefficientVehicule.objects.get(type_vehicule=type_vehicule)
        except CoefficientVehicule.DoesNotExist:
            return base
        return (base * coef.coefficient_multiplicateur + coef.frais_fixe_supplement).quantize(Decimal('0.01'))


class Quartier(models.Model):
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone     = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='quartiers')
    nom      = models.CharField(_('Nom du quartier'), max_length=100)
    latitude  = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    repere    = models.CharField(_('Point de repère connu'), max_length=200, blank=True)
    est_actif = models.BooleanField(_('Actif'), default=True)

    class Meta:
        verbose_name        = _('Quartier')
        verbose_name_plural = _('Quartiers')
        ordering            = ['zone', 'nom']
        unique_together     = [['zone', 'nom']]

    def __str__(self):
        return f"{self.nom} → {self.zone.nom} ({self.zone.ville.nom})"


class TarifHistorique(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone         = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='historique_tarifs')
    ancien_prix  = models.DecimalField(max_digits=10, decimal_places=2)
    nouveau_prix = models.DecimalField(max_digits=10, decimal_places=2)
    raison       = models.TextField(blank=True)
    modifie_par  = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)
    date         = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Historique tarif')
        verbose_name_plural = _('Historiques tarifs')
        ordering            = ['-date']

    def __str__(self):
        return f"{self.zone} : {self.ancien_prix} → {self.nouveau_prix} FCFA"


# ═══════════════════════════════════════════════════════════════════════
# §3 – TARIFICATION VÉHICULE (NOUVEAU) & INTER-VILLES (NOUVEAU)
# ═══════════════════════════════════════════════════════════════════════

class CoefficientVehicule(models.Model):
    """
    Majoration appliquée au prix de référence (moto) selon le véhicule
    réellement nécessaire pour transporter le(s) produit(s).
    Un seul enregistrement par type de véhicule (référentiel global).
    """
    type_vehicule = models.CharField(
        _('Type de véhicule'), max_length=15,
        choices=TypeVehicule.choices, unique=True
    )
    coefficient_multiplicateur = models.DecimalField(
        _('Coefficient multiplicateur'), max_digits=4, decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text=_('Ex: 1.00 = moto (référence), 1.50 = voiture (+50%)')
    )
    frais_fixe_supplement = models.DecimalField(
        _('Supplément fixe (FCFA)'), max_digits=10, decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Montant fixe ajouté après application du coefficient')
    )
    description = models.TextField(blank=True)
    est_actif   = models.BooleanField(default=True)

    class Meta:
        verbose_name        = _('Coefficient véhicule')
        verbose_name_plural = _('Coefficients véhicules')
        ordering            = ['coefficient_multiplicateur']

    def __str__(self):
        return f"{self.get_type_vehicule_display()} × {self.coefficient_multiplicateur} (+{self.frais_fixe_supplement} FCFA)"


class TarifInterVille(models.Model):
    """
    Tarif de livraison entre deux villes différentes — utilisé principalement
    par LivraisonDirecte (clients particuliers) quand collecte et livraison
    ne sont pas dans la même ville.
    """
    ville_depart   = models.ForeignKey(Ville, on_delete=models.CASCADE, related_name='tarifs_depart')
    ville_arrivee  = models.ForeignKey(Ville, on_delete=models.CASCADE, related_name='tarifs_arrivee')
    prix_forfaitaire = models.DecimalField(
        _('Prix forfaitaire (FCFA)'), max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text=_('Si renseigné, prioritaire sur le calcul au km')
    )
    tarif_par_km = models.DecimalField(
        _('Tarif au km (FCFA)'), max_digits=8, decimal_places=2,
        null=True, blank=True
    )
    distance_km_reference = models.DecimalField(
        _('Distance de référence (km)'), max_digits=8, decimal_places=2,
        null=True, blank=True
    )
    coefficient_vehicule_applicable = models.BooleanField(
        _('Appliquer aussi la majoration véhicule'), default=True
    )
    est_actif = models.BooleanField(default=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Tarif inter-villes')
        verbose_name_plural = _('Tarifs inter-villes')
        unique_together     = [['ville_depart', 'ville_arrivee']]

    def __str__(self):
        return f"{self.ville_depart.nom} → {self.ville_arrivee.nom}"

    def calculer_prix(self, type_vehicule=TypeVehicule.MOTO, distance_km=None):
        if self.prix_forfaitaire:
            prix = self.prix_forfaitaire
        else:
            km = distance_km or self.distance_km_reference or Decimal('0')
            prix = (self.tarif_par_km or Decimal('0')) * Decimal(str(km))

        if self.coefficient_vehicule_applicable:
            try:
                coef = CoefficientVehicule.objects.get(type_vehicule=type_vehicule)
                prix = prix * coef.coefficient_multiplicateur + coef.frais_fixe_supplement
            except CoefficientVehicule.DoesNotExist:
                pass
        return Decimal(prix).quantize(Decimal('0.01'))


# ═══════════════════════════════════════════════════════════════════════
# §4 – PARAMÈTRES SYSTÈME
# ═══════════════════════════════════════════════════════════════════════

class ParametreSysteme(models.Model):
    """
    Configuration dynamique. Clés notables ajoutées pour ce module :
        COMMISSION_YOPISHOP_PCT     -> 10
        DELAI_INACTIVITE_JOURS      -> 30
        FRAIS_GARDIENNAGE_DEFAUT    -> montant FCFA
        TARIF_KM_DEFAUT_DIRECT      -> 150
    """
    cle   = models.CharField(_('Clé'), max_length=100, unique=True)
    valeur = models.TextField(_('Valeur'))
    type_valeur = models.CharField(
        _('Type'), max_length=10,
        choices=[('str', 'Texte'), ('int', 'Entier'), ('float', 'Décimal'),
                 ('bool', 'Booléen'), ('json', 'JSON')],
        default='str'
    )
    description = models.TextField(blank=True)
    modifie_par = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Paramètre système')
        verbose_name_plural = _('Paramètres système')
        ordering            = ['cle']

    def __str__(self):
        return f"{self.cle} = {self.valeur[:60]}"

    def get_valeur_typee(self):
        import json
        convertisseurs = {
            'int': int, 'float': float,
            'bool': lambda v: v.lower() in ('true', '1', 'oui', 'yes'),
            'json': json.loads, 'str': str,
        }
        try:
            return convertisseurs.get(self.type_valeur, str)(self.valeur)
        except (ValueError, TypeError):
            return self.valeur

    @classmethod
    def get(cls, cle, defaut=None):
        try:
            return cls.objects.get(cle=cle).get_valeur_typee()
        except cls.DoesNotExist:
            return defaut
