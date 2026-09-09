from django import forms
from django.core.exceptions import ValidationError

from .models import Message, Conversation


class MessageForm(forms.ModelForm):
    """Formulaire d'envoi d'un message (texte et/ou fichier joint)."""

    class Meta:
        model = Message
        fields = ['contenu', 'fichier_joint']
        widgets = {
            'contenu': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Écrivez votre message...',
                'maxlength': 3000,
            }),
            'fichier_joint': forms.ClearableFileInput(attrs={
                'class': 'form-control',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        contenu = (cleaned_data.get('contenu') or '').strip()
        fichier = cleaned_data.get('fichier_joint')

        if not contenu and not fichier:
            raise ValidationError(
                "Le message doit contenir du texte ou un fichier joint."
            )
        return cleaned_data

    def save(self, commit=True, conversation=None, expediteur=None):
        message = super().save(commit=False)
        if conversation is not None:
            message.conversation = conversation
        if expediteur is not None:
            message.expediteur = expediteur

        # Détermine automatiquement le type de contenu
        if message.fichier_joint:
            message.type_contenu = Message.TypeContenu.FICHIER
        else:
            message.type_contenu = Message.TypeContenu.TEXTE

        if commit:
            message.save()
        return message


class NouvelleConversationForm(forms.Form):
    """Démarrer une conversation avec un destinataire (par email)."""

    destinataire_email = forms.EmailField(
        label="Email du destinataire",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@exemple.com',
        }),
    )
    sujet = forms.CharField(
        label="Sujet",
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    message_initial = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    def __init__(self, *args, expediteur=None, **kwargs):
        self.expediteur = expediteur
        super().__init__(*args, **kwargs)

    def clean_destinataire_email(self):
        from apps_core.models import Utilisateur

        email = self.cleaned_data['destinataire_email']
        try:
            destinataire = Utilisateur.objects.get(email=email, est_actif=True)
        except Utilisateur.DoesNotExist:
            raise ValidationError("Aucun utilisateur actif avec cet email.")

        if self.expediteur and destinataire.pk == self.expediteur.pk:
            raise ValidationError("Vous ne pouvez pas démarrer une conversation avec vous-même.")

        self.cleaned_data['destinataire'] = destinataire
        return email


class RechercheConversationForm(forms.Form):
    """Recherche/filtre dans la liste des conversations."""

    q = forms.CharField(
        label="Rechercher",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom, sujet...',
        }),
    )
    type_conv = forms.ChoiceField(
        label="Type",
        required=False,
        choices=[('', 'Tous types')] + list(Conversation.TypeConversation.choices),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    archivees = forms.BooleanField(
        label="Afficher les archivées",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )