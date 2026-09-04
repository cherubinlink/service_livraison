from django import forms
from django.core.exceptions import ValidationError

from apps_catalogue.models import Categorie, Produit, PhotoProduit
from apps_entreprise.models import Entrepot


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ['parent', 'nom', 'slug', 'icone', 'couleur', 'description', 'ordre', 'est_active']
        widgets = {
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: alimentation-epices'}),
            'icone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'bi-box-seam'}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control'}),
            'est_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        parent = cleaned.get('parent')
        if parent and self.instance.pk and parent.pk == self.instance.pk:
            raise ValidationError("Une catégorie ne peut pas être sa propre catégorie parente.")
        return cleaned


class ProduitCreationForm(forms.ModelForm):
    """
    Utilisée par l'ADMIN pour enregistrer un nouveau produit au nom d'une
    entreprise, avec son placement initial en entrepôt. C'est ensuite
    l'ENTREPRISE qui valide ou refuse ce produit (cf. Produit.StatutProduit
    — workflow inversé par rapport à la validation d'une Entreprise).
    """
    entrepot = forms.ModelChoiceField(
        label='Entrepôt de stockage initial',
        queryset=Entrepot.objects.filter(est_actif=True).order_by('nom'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantite_initiale = forms.IntegerField(
        label='Quantité initiale en stock', min_value=0, initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Produit
        fields = [
            'entreprise', 'categorie', 'nom', 'reference_sku', 'code_barre', 'description',
            'prix_unitaire', 'unite', 'seuil_alerte_defaut', 'seuil_rupture_defaut',
            'vendu_en_ligne', 'reference_yopishop', 'qualite_produit', 'vehicule_minimum_requis',
            'poids_kg', 'longueur_cm', 'largeur_cm', 'hauteur_cm', 'fragile', 'necessite_froid',
            'photo_principale',
        ]
        widgets = {
            'entreprise': forms.Select(attrs={'class': 'form-select'}),
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_sku': forms.TextInput(attrs={'class': 'form-control'}),
            'code_barre': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'prix_unitaire': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unite': forms.Select(attrs={'class': 'form-select'}),
            'seuil_alerte_defaut': forms.NumberInput(attrs={'class': 'form-control'}),
            'seuil_rupture_defaut': forms.NumberInput(attrs={'class': 'form-control'}),
            'vendu_en_ligne': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reference_yopishop': forms.TextInput(attrs={'class': 'form-control'}),
            'qualite_produit': forms.Select(attrs={'class': 'form-select'}),
            'vehicule_minimum_requis': forms.Select(attrs={'class': 'form-select'}),
            'poids_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'longueur_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'largeur_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hauteur_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fragile': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'necessite_froid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'photo_principale': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class ProduitEditForm(forms.ModelForm):
    """
    Utilisée par l'ENTREPRISE pour ajuster les aspects commerciaux d'un
    produit déjà enregistré. Volontairement exclus : entreprise, statut,
    seuils de stock (gérés par StockEntrepot), reference_sku/code_barre
    (identité produit fixée à l'enregistrement admin).
    """
    class Meta:
        model = Produit
        fields = [
            'categorie', 'nom', 'description', 'prix_unitaire', 'unite',
            'vendu_en_ligne', 'reference_yopishop', 'qualite_produit', 'vehicule_minimum_requis',
            'poids_kg', 'longueur_cm', 'largeur_cm', 'hauteur_cm', 'fragile', 'necessite_froid',
            'photo_principale',
        ]
        widgets = {
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'prix_unitaire': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unite': forms.Select(attrs={'class': 'form-select'}),
            'vendu_en_ligne': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reference_yopishop': forms.TextInput(attrs={'class': 'form-control'}),
            'qualite_produit': forms.Select(attrs={'class': 'form-select'}),
            'vehicule_minimum_requis': forms.Select(attrs={'class': 'form-select'}),
            'poids_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'longueur_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'largeur_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hauteur_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fragile': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'necessite_froid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'photo_principale': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class MotifRefusProduitForm(forms.Form):
    motif = forms.CharField(
        label='Motif du refus', required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )


class PhotoProduitForm(forms.ModelForm):
    class Meta:
        model = PhotoProduit
        fields = ['photo', 'legende', 'ordre']
        widgets = {
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'legende': forms.TextInput(attrs={'class': 'form-control'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control'}),
        }