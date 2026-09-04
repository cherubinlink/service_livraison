from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from apps_core.models import Utilisateur, Ville
from apps_core.choices import TypeEntreprise
from apps_entreprise.models import Entreprise, ContactEntreprise, DocumentEntreprise, Entrepot, AffectationEntrepot



class InscriptionEntrepriseForm(forms.Form):
    """
    Inscription Entreprise — crée À LA FOIS le compte Utilisateur
    (role=ENTREPRISE) et le profil Entreprise lié, contrairement à
    apps_core.InscriptionForm qui ne crée que des comptes CLIENT.

    Contrairement au compte Client (actif immédiatement), l'Entreprise
    créée ici reste au statut EN_ATTENTE : elle doit être validée par un
    admin (cf. Entreprise.valider()) avant de pouvoir enregistrer des
    produits ou recevoir des livraisons — voir apps_entreprise.views.
    inscription_entreprise().

    Les documents (registre de commerce, NIU) sont optionnels à ce stade
    pour ne pas bloquer l'inscription : ils peuvent aussi être ajoutés
    plus tard depuis le tableau de bord, avant la validation admin.
    """

    # ── Compte (Utilisateur) ────────────────────────────────────────────
    nom_contact = forms.CharField(
        label='Nom du responsable', max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Jean Mballa', 'autofocus': True})
    )
    email = forms.EmailField(
        label='Adresse email professionnelle',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@entreprise.cm'})
    )
    telephone = forms.CharField(
        label='Téléphone du responsable', max_length=20,
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

    # ── Entreprise ───────────────────────────────────────────────────────
    raison_sociale = forms.CharField(
        label='Raison sociale', max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : SARL Mboa Distribution'})
    )
    nom_commercial = forms.CharField(
        label='Nom commercial (si différent)', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optionnel'})
    )
    secteur = forms.ChoiceField(
        label="Secteur d'activité", choices=Entreprise.Secteur.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    taille = forms.ChoiceField(
        label="Taille de l'entreprise", choices=Entreprise.TailleEntreprise.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    type_entreprise = forms.ChoiceField(
        label="Type d'activité", choices=TypeEntreprise.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Détermine si vous vendez via Yopishop, en physique, ou les deux."
    )
    numero_registre = forms.CharField(
        label='N° Registre de Commerce', max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Optionnel à l'inscription"})
    )
    numero_contribuable_niu = forms.CharField(
        label='N° Contribuable (NIU)', max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Optionnel à l'inscription"})
    )
    adresse_siege = forms.CharField(
        label='Adresse du siège social',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )
    ville_principale = forms.ModelChoiceField(
        label='Ville principale', queryset=Ville.objects.filter(est_active=True).order_by('nom'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    telephone_principal = forms.CharField(
        label='Téléphone professionnel principal', max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+237 6XX XXX XXX'})
    )

    # ── Documents (optionnels à l'inscription) ────────────────────────────
    document_registre = forms.FileField(
        label='Registre de Commerce (PDF/image)', required=False,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    document_niu = forms.FileField(
        label='Carte Contribuable / NIU (PDF/image)', required=False,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )

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


class ProfilEntrepriseForm(forms.ModelForm):
    """
    Édite les informations NON critiques d'une entreprise déjà créée.
    Volontairement exclu : raison_sociale, statut, numero_registre,
    numero_contribuable_niu, type_entreprise — ces champs engagent la
    validation admin et ne doivent pas être modifiables librement après
    inscription (contacter l'administration pour les changer).
    """
    class Meta:
        model = Entreprise
        fields = [
            'nom_commercial', 'secteur', 'taille', 'telephone_secondaire',
            'telephone_whatsapp', 'email_professionnel', 'site_web', 'logo',
            'couleur_principale', 'cycle_paiement', 'numero_paiement_principal',
            'notification_sms', 'notification_whatsapp', 'notification_email',
        ]
        widgets = {
            'nom_commercial': forms.TextInput(attrs={'class': 'form-control'}),
            'secteur': forms.Select(attrs={'class': 'form-select'}),
            'taille': forms.Select(attrs={'class': 'form-select'}),
            'telephone_secondaire': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_whatsapp': forms.TextInput(attrs={'class': 'form-control'}),
            'email_professionnel': forms.EmailInput(attrs={'class': 'form-control'}),
            'site_web': forms.URLInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'couleur_principale': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'cycle_paiement': forms.Select(attrs={'class': 'form-select'}),
            'numero_paiement_principal': forms.TextInput(attrs={'class': 'form-control'}),
            'notification_sms': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notification_whatsapp': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notification_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ContactEntrepriseForm(forms.ModelForm):
    class Meta:
        model = ContactEntreprise
        fields = ['type_contact', 'nom', 'telephone', 'email', 'est_principal']
        widgets = {
            'type_contact': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'est_principal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DocumentEntrepriseForm(forms.ModelForm):
    class Meta:
        model = DocumentEntreprise
        fields = ['type_doc', 'fichier']
        widgets = {
            'type_doc': forms.Select(attrs={'class': 'form-select'}),
            'fichier': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class MotifForm(forms.Form):
    """Formulaire générique à un seul champ, réutilisé pour refuser/suspendre (motif obligatoire)."""
    motif = forms.CharField(
        label='Motif', required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )


class FraisGardiennageForm(forms.Form):
    montant_du = forms.DecimalField(
        label='Montant dû (FCFA)', min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    raison = forms.CharField(
        label='Raison', required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )


class ConfirmerPaiementGardiennageForm(forms.Form):
    montant_paye = forms.DecimalField(
        label='Montant reçu (FCFA)', min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )


# ═══════════════════════════════════════════════════════════════════════
#
# À fusionner avec ton fichier réel (ProfilEntrepriseForm, ContactEntrepriseForm,
# DocumentEntrepriseForm, MotifForm, FraisGardiennageForm,
# ConfirmerPaiementGardiennageForm déjà existants).
# ═══════════════════════════════════════════════════════════════════════
 
class EntrepotForm(forms.ModelForm):
    """
    Formulaire de création/édition d'un Entrepôt — usage ADMIN uniquement
    (c'est la plateforme qui définit ses entrepôts, jamais une entreprise).
    """
    class Meta:
        model = Entrepot
        fields = [
            'nom', 'code', 'ville', 'zone', 'adresse', 'latitude', 'longitude',
            'capacite_m3', 'gere_produits_froid', 'gere_produits_lourds',
            'responsable', 'est_actif',
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Entrepôt Bonabéri'}),
            'code': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'Ex : DLA-01'}),
            'ville': forms.Select(attrs={'class': 'form-select'}),
            'zone': forms.Select(attrs={'class': 'form-select'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Optionnel'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Optionnel'}),
            'capacite_m3': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Optionnel'}),
            'gere_produits_froid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'gere_produits_lourds': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'responsable': forms.Select(attrs={'class': 'form-select'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps_core.models import Ville, Zone, Utilisateur
 
        self.fields['ville'].queryset = Ville.objects.filter(est_active=True).order_by('nom')
 
        self.fields['zone'].queryset = (
            Zone.objects.filter(est_active=True).select_related('ville').order_by('ville__nom', 'nom')
        )
        self.fields['zone'].required = False
        self.fields['zone'].empty_label = 'Aucune zone spécifique'
 
        self.fields['responsable'].queryset = (
            Utilisateur.objects.filter(role=Utilisateur.Role.ADMIN, est_actif=True).order_by('nom')
        )
        self.fields['responsable'].required = False
        self.fields['responsable'].empty_label = 'Non assigné pour le moment'
 
 
class AffectationEntrepotForm(forms.ModelForm):
    """
    Affecte une entreprise (déjà validée) à un entrepôt donné. Le champ
    `entrepot` n'est PAS dans ce formulaire : il vient de l'URL (on est
    toujours sur la fiche d'un entrepôt précis) et est renseigné par la
    vue via `save(commit=False)`.
 
    `entrepot=` (kwarg supplémentaire, pas un champ du modèle) permet
    d'exclure les entreprises déjà affectées à CET entrepôt précis —
    unique_together = [['entreprise', 'entrepot']] les rejetterait de
    toute façon à la validation, mais les exclure de la liste évite à
    l'admin de les sélectionner pour rien.
    """
    class Meta:
        model = AffectationEntrepot
        fields = ['entreprise']
        widgets = {
            'entreprise': forms.Select(attrs={'class': 'form-select'}),
        }
 
    def __init__(self, *args, entrepot=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps_entreprise.models import Entreprise
 
        queryset = Entreprise.objects.filter(statut=Entreprise.Statut.VALIDE).order_by('raison_sociale')
        if entrepot is not None:
            deja_affectees = AffectationEntrepot.objects.filter(entrepot=entrepot).values_list('entreprise_id', flat=True)
            queryset = queryset.exclude(pk__in=deja_affectees)
 
        self.fields['entreprise'].queryset = queryset
        self.fields['entreprise'].empty_label = 'Choisissez une entreprise…'
 