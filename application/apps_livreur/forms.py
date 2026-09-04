from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from apps_core.models import Utilisateur, Zone
from apps_core.choices import TypeVehicule
from apps_livreur.models import Livreur


class InscriptionLivreurForm(forms.Form):
    """
    Inscription Livreur — crée à la fois le compte Utilisateur
    (role=LIVREUR) et le profil Livreur lié, sur le même principe que
    apps_entreprise.InscriptionEntrepriseForm.

    Contrairement à Entreprise, le modèle Livreur n'a pas de statut
    "EN_ATTENTE" ni de workflow de validation admin dédié : le compte est
    créé avec statut=INACTIF (valeur par défaut du modèle) — le livreur
    active lui-même sa disponibilité depuis son tableau de bord une fois
    prêt à recevoir des courses (cf. apps_livreur.views.changer_statut_livreur).
    """

    # ── Compte (Utilisateur) ────────────────────────────────────────────
    nom_contact = forms.CharField(
        label='Nom complet', max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Paul Ekwalla', 'autofocus': True})
    )
    email = forms.EmailField(
        label='Adresse email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'vous@exemple.com'})
    )
    telephone = forms.CharField(
        label='Téléphone', max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+237 6XX XXX XXX'})
    )
    mot_de_passe = forms.CharField(
        label='Mot de passe', min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '8 caractères minimum'})
    )
    mot_de_passe_confirmation = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Retapez le mot de passe'})
    )

    # ── Profil Livreur ───────────────────────────────────────────────────
    numero_cni = forms.CharField(
        label='Numéro CNI', max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : 123456789'})
    )
    type_vehicule = forms.ChoiceField(
        label='Type de véhicule', choices=TypeVehicule.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    immatriculation = forms.CharField(
        label='Immatriculation', max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optionnel (vélo par ex.)'})
    )
    capacite_charge_kg = forms.DecimalField(
        label='Capacité de charge (kg)', required=False, min_value=0, max_digits=8, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Optionnel'})
    )
    zones_travail = forms.ModelMultipleChoiceField(
        label='Zones de travail préférées', required=False,
        queryset=Zone.objects.filter(est_active=True).select_related('ville').order_by('ville__nom', 'nom'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6})
    )
    photo_cni = forms.FileField(
        label='Photo de la CNI (recto)', required=False,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if Utilisateur.objects.filter(email=email).exists():
            raise ValidationError('Un compte existe déjà avec cette adresse email.')
        return email

    def clean_numero_cni(self):
        numero = self.cleaned_data['numero_cni'].strip()
        if Livreur.objects.filter(numero_cni=numero).exists():
            raise ValidationError('Ce numéro de CNI est déjà enregistré.')
        return numero

    def clean(self):
        cleaned = super().clean()
        mdp1 = cleaned.get('mot_de_passe')
        mdp2 = cleaned.get('mot_de_passe_confirmation')
        if mdp1 and mdp2 and mdp1 != mdp2:
            raise ValidationError('Les mots de passe ne correspondent pas.')
        if mdp1:
            password_validation.validate_password(mdp1)
        return cleaned


class ModifierProfilLivreurForm(forms.ModelForm):
    """
    Édite les informations d'un livreur déjà inscrit. numero_cni n'est PAS
    modifiable ici (document d'identité — tout changement doit passer par
    l'administration, comme pour raison_sociale côté Entreprise).
    """
    class Meta:
        model = Livreur
        fields = ['type_vehicule', 'immatriculation', 'capacite_charge_kg', 'zones_travail', 'photo_cni']
        widgets = {
            'type_vehicule': forms.Select(attrs={'class': 'form-select'}),
            'immatriculation': forms.TextInput(attrs={'class': 'form-control'}),
            'capacite_charge_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'zones_travail': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
            'photo_cni': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }