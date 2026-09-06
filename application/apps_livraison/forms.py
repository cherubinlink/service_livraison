from django import forms
from django.core.exceptions import ValidationError

from apps_catalogue.models import Produit, StockEntrepot
from apps_livreur.models import Livreur
from apps_livraison.models import Livraison


class LivraisonCreationForm(forms.ModelForm):
    """
    Crée l'EN-TÊTE d'une commande (statut BROUILLON). Les produits sont
    ajoutés séparément via LigneLivraisonForm — une commande sans ligne
    ne peut pas être soumise (cf. views.soumettre_livraison).
    """
    class Meta:
        model = Livraison
        fields = [
            'ville_livraison', 'zone_livraison', 'quartier_livraison', 'adresse_exacte',
            'nom_client', 'telephone_client', 'telephone_client_2', 'email_client',
            'priorite', 'mode_encaissement', 'note_livreur', 'date_souhaitee',
        ]
        widgets = {
            'ville_livraison': forms.Select(attrs={'class': 'form-select'}),
            'zone_livraison': forms.Select(attrs={'class': 'form-select'}),
            'quartier_livraison': forms.Select(attrs={'class': 'form-select'}),
            'adresse_exacte': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'nom_client': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_client': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_client_2': forms.TextInput(attrs={'class': 'form-control'}),
            'email_client': forms.EmailInput(attrs={'class': 'form-control'}),
            'priorite': forms.Select(attrs={'class': 'form-select'}),
            'mode_encaissement': forms.Select(attrs={'class': 'form-select'}),
            'note_livreur': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'date_souhaitee': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class LigneLivraisonForm(forms.Form):
    """
    Ajoute une ligne produit à une commande en BROUILLON. Les querysets
    sont restreints à l'entreprise connectée (fournie par la vue) :
    uniquement ses produits VALIDÉS, et ses lignes de stock disponibles.
    """
    produit = forms.ModelChoiceField(
        label='Produit', queryset=Produit.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    stock_entrepot = forms.ModelChoiceField(
        label='Entrepôt source', queryset=StockEntrepot.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Choisissez la ligne de stock correspondant au produit sélectionné."
    )
    quantite = forms.IntegerField(
        label='Quantité', min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, entreprise=None, **kwargs):
        super().__init__(*args, **kwargs)
        if entreprise is not None:
            self.fields['produit'].queryset = Produit.objects.filter(
                entreprise=entreprise, statut=Produit.StatutProduit.VALIDE
            ).order_by('nom')
            self.fields['stock_entrepot'].queryset = StockEntrepot.objects.filter(
                produit__entreprise=entreprise, quantite_stock__gt=0
            ).select_related('produit', 'entrepot').order_by('produit__nom', 'entrepot__nom')

    def clean(self):
        cleaned = super().clean()
        produit = cleaned.get('produit')
        stock = cleaned.get('stock_entrepot')
        quantite = cleaned.get('quantite')

        if produit and stock and stock.produit_id != produit.id:
            raise ValidationError("L'entrepôt sélectionné ne correspond pas au produit choisi.")
        if stock and quantite and quantite > stock.quantite_disponible:
            raise ValidationError(f"Stock insuffisant : {stock.quantite_disponible} disponible(s) seulement.")
        return cleaned


class AttributionLivreurForm(forms.Form):
    """
    Liste les livreurs actifs pour attribution. Si une livraison est
    fournie, priorité est donnée aux livreurs déclarant travailler dans
    sa zone — sans exclure les autres livreurs actifs pour autant (au cas
    où aucun livreur "idéal" ne serait disponible).
    """
    livreur = forms.ModelChoiceField(
        label='Livreur', queryset=Livreur.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, livraison=None, **kwargs):
        super().__init__(*args, **kwargs)
        base = Livreur.objects.filter(statut=Livreur.Statut.ACTIF).select_related('utilisateur')
        queryset = base
        if livraison is not None:
            compatibles = base.filter(zones_travail=livraison.zone_livraison)
            if compatibles.exists():
                queryset = compatibles
        self.fields['livreur'].queryset = queryset.distinct().order_by('utilisateur__nom')


class MotifLivraisonForm(forms.Form):
    """Formulaire générique à un champ, réutilisé pour refuser une commande ou signaler un échec."""
    motif = forms.CharField(
        label='Motif', required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )


class SignalerPaiementFraisForm(forms.Form):
    montant_paye = forms.DecimalField(
        label='Montant payé par le client (FCFA)', min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    integralite = forms.BooleanField(
        label='Payé en intégralité (aucune déduction sur le gain entreprise)', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class ConfirmationLivraisonForm(forms.ModelForm):
    """Utilisé par le livreur pour clôturer une livraison : preuve photo + signature."""
    class Meta:
        model = Livraison
        fields = ['photo_preuve', 'signature_client_img']
        widgets = {
            'photo_preuve': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'signature_client_img': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }