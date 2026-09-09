from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import TypeBonus, BonusEntreprise


class TypeBonusForm(forms.ModelForm):
    """Création / modification d'un type de bonus (catalogue)."""

    class Meta:
        model = TypeBonus
        fields = ['nom', 'categorie', 'description', 'valeur', 'est_actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'valeur': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_valeur(self):
        valeur = self.cleaned_data['valeur']
        if valeur < 0:
            raise ValidationError("La valeur du bonus ne peut pas être négative.")

        categorie = self.cleaned_data.get('categorie') or self.data.get('categorie')
        if categorie == TypeBonus.Categorie.REDUCTION_PCT and valeur > 100:
            raise ValidationError("Un pourcentage de réduction ne peut pas dépasser 100.")
        return valeur


class BonusEntrepriseForm(forms.ModelForm):
    """Attribution d'un bonus à une entreprise."""

    class Meta:
        model = BonusEntreprise
        fields = [
            'entreprise', 'type_bonus', 'zone_cible',
            'date_debut', 'date_expiration',
            'nb_utilisations_max', 'note_interne',
        ]
        widgets = {
            'entreprise': forms.Select(attrs={'class': 'form-select'}),
            'type_bonus': forms.Select(attrs={'class': 'form-select'}),
            'zone_cible': forms.Select(attrs={'class': 'form-select'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_expiration': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'nb_utilisations_max': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'note_interne': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        help_texts = {
            'nb_utilisations_max': "0 = utilisations illimitées jusqu'à expiration.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['type_bonus'].queryset = TypeBonus.objects.filter(est_actif=True)
        self.fields['zone_cible'].required = False
        self.fields['note_interne'].required = False

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_expiration = cleaned_data.get('date_expiration')
        type_bonus = cleaned_data.get('type_bonus')
        zone_cible = cleaned_data.get('zone_cible')

        if date_debut and date_expiration and date_expiration <= date_debut:
            raise ValidationError({
                'date_expiration': "La date d'expiration doit être postérieure à la date de début."
            })

        categories_zone = (TypeBonus.Categorie.REDUCTION_ZONE, TypeBonus.Categorie.REDUCTION_PCT)
        if type_bonus and type_bonus.categorie in categories_zone and not zone_cible:
            raise ValidationError({
                'zone_cible': "Une zone cible est obligatoire pour ce type de bonus."
            })

        return cleaned_data

    def save(self, commit=True, attribue_par=None):
        bonus = super().save(commit=False)
        if attribue_par is not None:
            bonus.attribue_par = attribue_par
        if commit:
            bonus.save()
        return bonus


class RechercheBonusForm(forms.Form):
    """Filtre pour la liste des bonus attribués."""

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Entreprise, type de bonus…',
        }),
    )
    statut = forms.ChoiceField(
        label="Statut",
        required=False,
        choices=[('', 'Tous les statuts')] + list(BonusEntreprise.Statut.choices),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    categorie = forms.ChoiceField(
        label="Catégorie",
        required=False,
        choices=[('', 'Toutes les catégories')] + list(TypeBonus.Categorie.choices),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )