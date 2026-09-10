from django import forms
from django.core.exceptions import ValidationError

from .models import Notification


class NotificationManuelleForm(forms.ModelForm):
    """
    Envoi manuel d'une notification par un administrateur
    (ex: annonce, relance, information ponctuelle hors événement système).
    """

    class Meta:
        model = Notification
        fields = ['destinataire', 'canal', 'evenement', 'sujet', 'message', 'livraison']
        widgets = {
            'destinataire': forms.Select(attrs={'class': 'form-select'}),
            'canal': forms.Select(attrs={'class': 'form-select'}),
            'evenement': forms.Select(attrs={'class': 'form-select'}),
            'sujet': forms.TextInput(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'livraison': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['livraison'].required = False
        self.fields['sujet'].required = False

    def clean(self):
        cleaned_data = super().clean()
        canal = cleaned_data.get('canal')
        destinataire = cleaned_data.get('destinataire')
        message = (cleaned_data.get('message') or '').strip()

        if not message:
            raise ValidationError({'message': "Le message ne peut pas être vide."})

        if canal in (Notification.Canal.SMS, Notification.Canal.WHATSAPP) and destinataire:
            if not destinataire.telephone:
                raise ValidationError({
                    'destinataire': "Ce destinataire n'a pas de numéro de téléphone renseigné, "
                                    "impossible d'envoyer par SMS/WhatsApp."
                })
            cleaned_data['telephone'] = destinataire.telephone

        return cleaned_data

    def save(self, commit=True):
        notification = super().save(commit=False)
        notification.telephone = self.cleaned_data.get('telephone', '')
        if commit:
            notification.save()
        return notification


class RechercheNotificationForm(forms.Form):
    """Filtre pour la liste (admin) des notifications envoyées."""

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Destinataire, sujet, message…',
        }),
    )
    canal = forms.ChoiceField(
        label="Canal",
        required=False,
        choices=[('', 'Tous les canaux')] + list(Notification.Canal.choices),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    evenement = forms.ChoiceField(
        label="Événement",
        required=False,
        choices=[('', 'Tous les événements')] + list(Notification.Evenement.choices),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    statut_envoi = forms.ChoiceField(
        label="Statut",
        required=False,
        choices=[('', 'Tous les statuts')] + list(Notification.StatutEnvoi.choices),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )