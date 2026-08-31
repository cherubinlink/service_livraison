from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from decimal import Decimal
 
from apps_core.models import Utilisateur, Pays, Ville, Zone, Quartier, CoefficientVehicule, TarifInterVille, ParametreSysteme


class ContactForm(forms.Form):
    """
    Formulaire public de la page Contact. Volontairement simple (pas de
    lien avec un modèle Utilisateur) puisqu'un visiteur non connecté doit
    pouvoir l'utiliser.
    """

    SUJET_CHOICES = [
        ('', 'Choisissez un sujet…'),
        ('ENTREPRISE', 'Je suis une entreprise'),
        ('LIVREUR', 'Je veux devenir livreur'),
        ('CLIENT', "J'ai une question sur une livraison"),
        ('PARTENARIAT', 'Proposition de partenariat'),
        ('AUTRE', 'Autre demande'),
    ]

    nom = forms.CharField(
        label=_('Nom complet'), max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Votre nom et prénom',
        })
    )
    email = forms.EmailField(
        label=_('Adresse email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 'placeholder': 'vous@exemple.com',
        })
    )
    telephone = forms.CharField(
        label=_('Téléphone (optionnel)'), max_length=20, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': '+237 6XX XXX XXX',
        })
    )
    sujet = forms.ChoiceField(
        label=_('Sujet'), choices=SUJET_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    message = forms.CharField(
        label=_('Votre message'),
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 5, 'placeholder': 'Écrivez votre message ici…',
        })
    )

    def clean_sujet(self):
        sujet = self.cleaned_data.get('sujet')
        if not sujet:
            raise forms.ValidationError(_('Merci de choisir un sujet.'))
        return sujet



class InscriptionForm(forms.ModelForm):
    """
    Formulaire d'inscription générique — crée un compte Utilisateur avec
    le rôle CLIENT par défaut (auto-service, sans validation admin).

    Les inscriptions Entreprise et Livreur passent par des formulaires
    dédiés dans apps_entreprise / apps_livreur, qui créent en plus le
    profil métier lié (Entreprise, Livreur) et restent soumis à
    validation admin — ce formulaire-ci ne crée qu'un compte Utilisateur.
    """
    mot_de_passe = forms.CharField(
        label='Mot de passe', min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '8 caractères minimum'})
    )
    mot_de_passe_confirmation = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Retapez le mot de passe'})
    )

    class Meta:
        model = Utilisateur
        fields = ['nom', 'email', 'telephone']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Aïcha Mballa', 'autofocus': True}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'vous@exemple.com'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+237 6XX XXX XXX'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if Utilisateur.objects.filter(email=email).exists():
            raise ValidationError('Un compte existe déjà avec cette adresse email.')
        return email

    def clean(self):
        cleaned = super().clean()
        mdp1 = cleaned.get('mot_de_passe')
        mdp2 = cleaned.get('mot_de_passe_confirmation')
        if mdp1 and mdp2 and mdp1 != mdp2:
            raise ValidationError('Les mots de passe ne correspondent pas.')
        if mdp1:
            password_validation.validate_password(mdp1)
        return cleaned

    def save(self, role=Utilisateur.Role.CLIENT):
        return Utilisateur.objects.create_user(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['mot_de_passe'],
            nom=self.cleaned_data['nom'],
            telephone=self.cleaned_data.get('telephone', ''),
            role=role,
        )


class ConnexionForm(forms.Form):
    email = forms.EmailField(
        label='Adresse email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'vous@exemple.com', 'autofocus': True})
    )
    mot_de_passe = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Votre mot de passe'})
    )


class DemandeReinitialisationForm(forms.Form):
    email = forms.EmailField(
        label='Adresse email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'vous@exemple.com', 'autofocus': True})
    )


class NouveauMotDePasseForm(forms.Form):
    mot_de_passe = forms.CharField(
        label='Nouveau mot de passe', min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '8 caractères minimum', 'autofocus': True})
    )
    mot_de_passe_confirmation = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Retapez le mot de passe'})
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('mot_de_passe') != cleaned.get('mot_de_passe_confirmation'):
            raise ValidationError('Les mots de passe ne correspondent pas.')
        if cleaned.get('mot_de_passe'):
            password_validation.validate_password(cleaned['mot_de_passe'])
        return cleaned


class VerificationOtpForm(forms.Form):
    """Réservé pour quand l'envoi SMS/email sera opérationnel (voir views.verifier_otp)."""
    code = forms.CharField(
        label='Code de vérification', max_length=6, min_length=4,
        widget=forms.TextInput(attrs={
            'class': 'form-control sd-otp-input', 'placeholder': '••••••',
            'inputmode': 'numeric', 'autocomplete': 'one-time-code', 'autofocus': True,
        })
    )



class PaysForm(forms.ModelForm):
    class Meta:
        model = Pays
        fields = ['nom', 'code_iso', 'indicatif', 'devise', 'est_actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Cameroun'}),
            'code_iso': forms.TextInput(attrs={
                'class': 'form-control text-uppercase', 'placeholder': 'CM', 'maxlength': 2,
            }),
            'indicatif': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+237'}),
            'devise': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FCFA'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
 
 
class VilleForm(forms.ModelForm):
    class Meta:
        model = Ville
        fields = ['pays', 'nom', 'code', 'latitude', 'longitude', 'est_active']
        widgets = {
            'pays': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Douala'}),
            'code': forms.TextInput(attrs={
                'class': 'form-control text-uppercase', 'placeholder': 'DLA',
            }),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Optionnel'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Optionnel'}),
            'est_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pays'].queryset = Pays.objects.filter(est_actif=True).order_by('nom')
        self.fields['pays'].empty_label = 'Choisissez un pays…'
 
 
class ZoneForm(forms.ModelForm):
    class Meta:
        model = Zone
        fields = [
            'ville', 'nom', 'description', 'prix_livraison', 'prix_dynamique',
            'coefficient_pointe', 'heure_pointe_debut', 'heure_pointe_fin', 'est_active',
        ]
        widgets = {
            'ville': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Akwa'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'prix_livraison': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'prix_dynamique': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'zonePrixDynamique'}),
            'coefficient_pointe': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'heure_pointe_debut': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_pointe_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'est_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ville'].queryset = (
            Ville.objects.filter(est_active=True).select_related('pays').order_by('pays__nom', 'nom')
        )
        self.fields['ville'].empty_label = 'Choisissez une ville…'
        self.fields['prix_dynamique'].required = False
        self.fields['heure_pointe_debut'].required = False
        self.fields['heure_pointe_fin'].required = False
 
 
class QuartierForm(forms.ModelForm):
    class Meta:
        model = Quartier
        fields = ['zone', 'nom', 'repere', 'latitude', 'longitude', 'est_actif']
        widgets = {
            'zone': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Bonapriso'}),
            'repere': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : près du carrefour…'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Optionnel'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Optionnel'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['zone'].queryset = (
            Zone.objects.filter(est_active=True).select_related('ville').order_by('ville__nom', 'nom')
        )
        self.fields['zone'].empty_label = 'Choisissez une zone…'


# ═══════════════════════════════════════════════════════════════════════
# Tarification — formulaires utilisés par modifier_tarif_zone() et
# gerer_coefficients_vehicule()
# ═══════════════════════════════════════════════════════════════════════
 
class ZoneTarifForm(forms.Form):
    """
    Formulaire volontairement séparé de ZoneForm : changer le prix d'une
    zone doit TOUJOURS passer par modifier_tarif_zone() pour journaliser
    le changement dans TarifHistorique — ce formulaire ne connaît pas la
    zone elle-même (elle vient de l'URL), seulement le nouveau prix et la
    raison du changement.
    """
    nouveau_prix = forms.DecimalField(
        label=_('Nouveau prix — véhicule MOTO (FCFA)'),
        max_digits=10, decimal_places=2, min_value=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    raison = forms.CharField(
        label=_('Raison du changement'), required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': 'Ex : ajustement carburant, révision trimestrielle…',
        })
    )
 
 
class CoefficientVehiculeForm(forms.ModelForm):
    class Meta:
        model = CoefficientVehicule
        fields = ['type_vehicule', 'coefficient_multiplicateur', 'frais_fixe_supplement', 'description', 'est_actif']
        widgets = {
            'type_vehicule': forms.Select(attrs={'class': 'form-select'}),
            'coefficient_multiplicateur': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'frais_fixe_supplement': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    


class TarifInterVilleForm(forms.ModelForm):
    class Meta:
        model = TarifInterVille
        fields = [
            'ville_depart', 'ville_arrivee', 'prix_forfaitaire', 'tarif_par_km',
            'distance_km_reference', 'coefficient_vehicule_applicable', 'est_actif',
        ]
        widgets = {
            'ville_depart': forms.Select(attrs={'class': 'form-select'}),
            'ville_arrivee': forms.Select(attrs={'class': 'form-select'}),
            'prix_forfaitaire': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'placeholder': 'Optionnel — prioritaire si renseigné',
            }),
            'tarif_par_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Optionnel'}),
            'distance_km_reference': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Optionnel'}),
            'coefficient_vehicule_applicable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ville_depart'].queryset = Ville.objects.filter(est_active=True).order_by('nom')
        self.fields['ville_arrivee'].queryset = Ville.objects.filter(est_active=True).order_by('nom')
        self.fields['ville_depart'].empty_label = 'Ville de départ…'
        self.fields['ville_arrivee'].empty_label = 'Ville d\'arrivée…'
        self.fields['prix_forfaitaire'].required = False
        self.fields['tarif_par_km'].required = False
        self.fields['distance_km_reference'].required = False
        self.fields['coefficient_vehicule_applicable'].required = False
        self.fields['est_actif'].required = False
 
    def clean(self):
        cleaned_data = super().clean()
        prix_forfaitaire = cleaned_data.get('prix_forfaitaire')
        tarif_par_km = cleaned_data.get('tarif_par_km')
        if not prix_forfaitaire and not tarif_par_km:
            raise forms.ValidationError(
                "Renseignez au moins un prix forfaitaire ou un tarif au kilomètre."
            )
        return cleaned_data



# ═══════════════════════════════════════════════════════════════════════
# FORMULAIRE — apps_core/forms.py
# ═══════════════════════════════════════════════════════════════════════
 
class ParametreSystemeForm(forms.ModelForm):
    class Meta:
        model = ParametreSysteme
        fields = ['cle', 'valeur', 'type_valeur', 'description']
        widgets = {
            'cle': forms.TextInput(attrs={
                'class': 'form-control text-uppercase',
                'placeholder': 'Ex : COMMISSION_YOPISHOP_PCT',
            }),
            'valeur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : 10'}),
            'type_valeur': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
 
    def clean(self):
        """
        Empêche d'enregistrer une valeur incompatible avec le type choisi
        (ex : type_valeur='int' avec valeur='dix') — sans ce contrôle,
        ParametreSysteme.get_valeur_typee() échouerait silencieusement à
        la conversion et retomberait sur la chaîne brute partout où le
        paramètre est utilisé dans le code métier.
        """
        cleaned_data = super().clean()
        valeur = cleaned_data.get('valeur')
        type_valeur = cleaned_data.get('type_valeur')
        if valeur is None or not type_valeur:
            return cleaned_data
 
        import json
        try:
            if type_valeur == 'int':
                int(valeur)
            elif type_valeur == 'float':
                float(valeur)
            elif type_valeur == 'json':
                json.loads(valeur)
            # 'bool' et 'str' acceptent n'importe quelle chaîne
        except (ValueError, TypeError, json.JSONDecodeError):
            self.add_error('valeur', f"Cette valeur n'est pas compatible avec le type « {type_valeur} ».")
        return cleaned_data
 
