# ═══════════════════════════════════════════════════════════════════════
# apps_evaluation/forms.py — FRAGMENT
# ═══════════════════════════════════════════════════════════════════════

from django import forms

from apps_evaluation.models import Evaluation

_CHOIX_NOTE = [(i, f'{i} / 5') for i in range(1, 6)]


class EvaluationForm(forms.ModelForm):
    """
    Formulaire PUBLIC laissé par le client après livraison. `livraison`
    n'est volontairement PAS dans Meta.fields : elle est injectée par la
    vue depuis l'URL, jamais choisie par le formulaire (empêcherait un
    client d'évaluer n'importe quelle autre livraison que la sienne).
    """
    class Meta:
        model = Evaluation
        fields = ['note_globale', 'note_rapidite', 'note_etat_colis', 'note_livreur', 'commentaire', 'recommande']
        widgets = {
            'note_globale': forms.Select(choices=_CHOIX_NOTE, attrs={'class': 'form-select'}),
            'note_rapidite': forms.Select(choices=[('', 'Non noté')] + _CHOIX_NOTE, attrs={'class': 'form-select'}),
            'note_etat_colis': forms.Select(choices=[('', 'Non noté')] + _CHOIX_NOTE, attrs={'class': 'form-select'}),
            'note_livreur': forms.Select(choices=[('', 'Non noté')] + _CHOIX_NOTE, attrs={'class': 'form-select'}),
            'commentaire': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3, 'placeholder': 'Un commentaire à ajouter ? (optionnel)',
            }),
            'recommande': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        # note_rapidite/note_etat_colis/note_livreur sont blank=True côté
        # modèle : ModelForm les rend déjà required=False automatiquement,
        # rien à forcer ici.