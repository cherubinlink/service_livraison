from django import forms
from django.core.exceptions import ValidationError

from apps_catalogue.models import Produit, StockEntrepot
from apps_livreur.models import Livreur
from apps_livraison.models import Livraison, LivraisonDirecte


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



class LivraisonDirecteForm(forms.ModelForm):
    """
    Formulaire PUBLIC — aucun compte requis (cf. FAQ « Puis-je envoyer un
    colis sans créer de compte ? »). Le tarif NÉGOCIÉ est volontairement
    absent des choix proposés ici : une négociation se met en place via
    l'admin après contact, jamais en libre-service depuis ce formulaire.
    `prix_negocie` n'est donc pas non plus dans Meta.fields.
    """
    class Meta:
        model = LivraisonDirecte
        fields = [
            'nom_expediteur', 'telephone_expediteur', 'description_colis', 'poids_kg', 'valeur_declaree',
            'adresse_collecte', 'ville_collecte', 'zone_collecte',
            'nom_destinataire', 'telephone_destinataire', 'adresse_livraison', 'ville_livraison', 'zone_livraison',
            'type_tarification', 'vehicule_requis', 'distance_km',
        ]
        widgets = {
            'nom_expediteur': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_expediteur': forms.TextInput(attrs={'class': 'form-control'}),
            'description_colis': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'poids_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Optionnel'}),
            'valeur_declaree': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Optionnel'}),
            'adresse_collecte': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'ville_collecte': forms.Select(attrs={'class': 'form-select'}),
            'zone_collecte': forms.Select(attrs={'class': 'form-select'}),
            'nom_destinataire': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_destinataire': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse_livraison': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'ville_livraison': forms.Select(attrs={'class': 'form-select'}),
            'zone_livraison': forms.Select(attrs={'class': 'form-select'}),
            'type_tarification': forms.Select(attrs={'class': 'form-select'}),
            'vehicule_requis': forms.Select(attrs={'class': 'form-select'}),
            'distance_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Optionnel'}),
        }
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps_core.models import Ville, Zone
 
        villes_actives = Ville.objects.filter(est_active=True).order_by('nom')
        self.fields['ville_collecte'].queryset = villes_actives
        self.fields['ville_livraison'].queryset = villes_actives
 
        zones_actives = Zone.objects.filter(est_active=True).select_related('ville').order_by('ville__nom', 'nom')
        self.fields['zone_collecte'].queryset = zones_actives
        self.fields['zone_collecte'].required = False
        self.fields['zone_collecte'].empty_label = 'Zone inconnue / à préciser'
        self.fields['zone_livraison'].queryset = zones_actives
        self.fields['zone_livraison'].required = False
        self.fields['zone_livraison'].empty_label = 'Zone inconnue / à préciser'
 
        # Exclut NEGOCIE des choix publics (voir docstring de la classe)
        self.fields['type_tarification'].choices = [
            choix for choix in LivraisonDirecte.TypeTarification.choices
            if choix[0] != LivraisonDirecte.TypeTarification.NEGOCIE
        ]
 
    def clean(self):
        cleaned = super().clean()
        type_tarif = cleaned.get('type_tarification')
 
        if type_tarif == LivraisonDirecte.TypeTarification.INTRA_ZONE and not cleaned.get('zone_livraison'):
            raise ValidationError("Merci de choisir la zone de livraison pour une tarification intra-zone.")
        if type_tarif == LivraisonDirecte.TypeTarification.AU_KM and not cleaned.get('distance_km'):
            raise ValidationError("Merci d'indiquer une distance estimée pour un calcul au kilomètre.")
        if (type_tarif == LivraisonDirecte.TypeTarification.INTER_VILLE
                and cleaned.get('ville_collecte') == cleaned.get('ville_livraison')):
            raise ValidationError("Les villes de collecte et de livraison doivent être différentes pour une tarification inter-villes.")
        return cleaned
 
 
class LivraisonDirecteAdminForm(LivraisonDirecteForm):
    """
    Variante ADMIN du formulaire ci-dessus : autorise en plus le tarif
    NÉGOCIÉ et son montant, ainsi que le rattachement à une entreprise
    inscrite (cf. `livraison_par_entreprise`, renseigné quand une
    entreprise initie une course directe sans passer par le circuit
    produits/stock).
    """
    class Meta(LivraisonDirecteForm.Meta):
        fields = LivraisonDirecteForm.Meta.fields + ['prix_negocie', 'tarif_par_km', 'livraison_par_entreprise']
        widgets = {
            **LivraisonDirecteForm.Meta.widgets,
            'prix_negocie': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tarif_par_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'livraison_par_entreprise': forms.Select(attrs={'class': 'form-select'}),
        }
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps_entreprise.models import Entreprise
 
        # L'admin a accès au tarif NÉGOCIÉ, contrairement au formulaire public
        self.fields['type_tarification'].choices = LivraisonDirecte.TypeTarification.choices
        self.fields['prix_negocie'].required = False
        self.fields['livraison_par_entreprise'].queryset = (
            Entreprise.objects.filter(statut=Entreprise.Statut.VALIDE).order_by('raison_sociale')
        )
        self.fields['livraison_par_entreprise'].required = False
        self.fields['livraison_par_entreprise'].empty_label = 'Aucune (particulier)'
 
    def clean(self):
        # On saute la validation stricte de LivraisonDirecteForm.clean() sur
        # INTRA_ZONE/AU_KM/INTER_VILLE si le type choisi est NEGOCIE.
        cleaned = forms.ModelForm.clean(self)
        type_tarif = cleaned.get('type_tarification')
 
        if type_tarif == LivraisonDirecte.TypeTarification.NEGOCIE and not cleaned.get('prix_negocie'):
            raise ValidationError("Merci d'indiquer le prix négocié avec le client.")
        if type_tarif == LivraisonDirecte.TypeTarification.INTRA_ZONE and not cleaned.get('zone_livraison'):
            raise ValidationError("Merci de choisir la zone de livraison pour une tarification intra-zone.")
        if type_tarif == LivraisonDirecte.TypeTarification.AU_KM and not cleaned.get('distance_km'):
            raise ValidationError("Merci d'indiquer une distance estimée pour un calcul au kilomètre.")
        return cleaned
 
 
class AttributionLivreurDirecteForm(forms.Form):
    """
    Même principe que AttributionLivreurForm (apps_livraison, Livraison
    B2B) : priorité aux livreurs travaillant dans la zone de collecte,
    sans exclure les autres livreurs actifs si aucun n'est disponible.
    """
    livreur = forms.ModelChoiceField(
        label='Livreur', queryset=Livreur.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
 
    def __init__(self, *args, livraison_directe=None, **kwargs):
        super().__init__(*args, **kwargs)
        base = Livreur.objects.filter(statut=Livreur.Statut.ACTIF).select_related('utilisateur')
        queryset = base
        if livraison_directe is not None and livraison_directe.zone_collecte_id:
            compatibles = base.filter(zones_travail=livraison_directe.zone_collecte)
            if compatibles.exists():
                queryset = compatibles
        self.fields['livreur'].queryset = queryset.distinct().order_by('utilisateur__nom')
