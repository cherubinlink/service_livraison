# ═══════════════════════════════════════════════════════════════════════
# apps_transaction/forms.py — FRAGMENT
# ═══════════════════════════════════════════════════════════════════════

from django import forms
from django.core.exceptions import ValidationError

from apps_transaction.models import LotPaiementEntreprise


class LotPaiementForm(forms.ModelForm):
    """
    Création admin d'un lot — periode_debut/periode_fin définissent la
    fenêtre sur laquelle construire_depuis_livraisons_eligibles() ira
    chercher les livraisons à regrouper (appelé par la vue juste après
    l'enregistrement de ce formulaire, pas ici).
    """
    class Meta:
        model = LotPaiementEntreprise
        fields = ['entreprise', 'periode_debut', 'periode_fin', 'methode_paiement', 'numero_compte_destination']
        widgets = {
            'entreprise': forms.Select(attrs={'class': 'form-select'}),
            'periode_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'periode_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'methode_paiement': forms.Select(attrs={'class': 'form-select'}),
            'numero_compte_destination': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Numéro Mobile Money / compte bancaire',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps_entreprise.models import Entreprise
        self.fields['entreprise'].queryset = (
            Entreprise.objects.filter(statut=Entreprise.Statut.VALIDE).order_by('raison_sociale')
        )
        # Pré-rempli depuis le numéro Mobile Money déclaré par l'entreprise,
        # si un entreprise_id est déjà connu (édition) — laissé vide en
        # création, l'admin le saisit ou l'ajuste manuellement.

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('periode_debut')
        fin = cleaned.get('periode_fin')
        if debut and fin and debut > fin:
            raise ValidationError("La date de début doit précéder (ou égaler) la date de fin.")
        return cleaned


class EnvoyerLotPaiementForm(forms.Form):
    """
    Utilisé par LotPaiementEntreprise.marquer_envoye() — les deux champs
    sont optionnels côté formulaire (la preuve peut être ajoutée après
    coup), mais fortement recommandés en pratique.
    """
    reference_transaction_externe = forms.CharField(
        label='Référence transaction (Mobile Money / banque)', required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    preuve_paiement = forms.ImageField(
        label='Preuve de paiement (capture, reçu)', required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )


class SignalerLitigeLotForm(forms.Form):
    """
    Le modèle n'a pas de statut de litige dédié — cette note est
    enregistrée dans LotPaiementEntreprise.note_litige et traitée
    manuellement par l'admin, sans changement automatique de statut.
    """
    note_litige = forms.CharField(
        label='Décrivez le problème rencontré', required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
    )