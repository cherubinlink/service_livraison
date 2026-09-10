# ═══════════════════════════════════════════════════════════════════════
# apps_evaluation/views.py
# ═══════════════════════════════════════════════════════════════════════

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required


# ═══════════════════════════════════════════════════════════════════════
# DÉPÔT PUBLIC — le client laisse son avis après une livraison LIVREE
# ═══════════════════════════════════════════════════════════════════════

def laisser_evaluation(request, livraison_pk):
    """
    Formulaire PUBLIC (pas de compte client requis, cohérent avec le
    reste du parcours livraison). livraison est injectée depuis l'URL,
    jamais choisie dans le formulaire — cf. docstring EvaluationForm.

    Deux garde-fous avant d'autoriser le dépôt :
      - la livraison doit être au statut LIVREE (on ne note pas une
        course encore en cours ou refusée) ;
      - Evaluation est en OneToOneField sur Livraison : une évaluation
        déjà existante redirige vers une page de remerciement plutôt que
        de lever une IntegrityError au .save().
    """
    from apps_livraison.models import Livraison
    from apps_evaluation.models import Evaluation
    from apps_evaluation.forms import EvaluationForm

    livraison = get_object_or_404(Livraison, pk=livraison_pk)

    evaluation_existante = Evaluation.objects.filter(livraison=livraison).first()
    if evaluation_existante:
        return render(request, 'apps_evaluation/evaluation_deja_envoyee.html', {
            'livraison': livraison, 'evaluation': evaluation_existante,
        })

    if livraison.statut != Livraison.Statut.LIVREE:
        messages.error(request, "Cette livraison n'est pas encore terminée — l'évaluation n'est pas disponible.")
        return redirect('apps_livraison:suivre_livraison_directe', token=getattr(livraison, 'token_suivi', ''))

    if request.method == 'POST':
        form = EvaluationForm(request.POST)
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.livraison = livraison
            evaluation.save()

            # Le score de fiabilité de l'entreprise intègre la moyenne des
            # évaluations (cf. Entreprise.recalculer_score()) : on le
            # recalcule immédiatement pour que ce nouvel avis compte tout
            # de suite, sans attendre une tâche planifiée.
            if livraison.entreprise_id:
                livraison.entreprise.recalculer_score()

            messages.success(request, "Merci pour votre avis !")
            return render(request, 'apps_evaluation/evaluation_merci.html', {'livraison': livraison})
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = EvaluationForm()

    return render(request, 'apps_evaluation/laisser_evaluation.html', {'form': form, 'livraison': livraison})


# ═══════════════════════════════════════════════════════════════════════
# ADMINISTRATION — consultation de toutes les évaluations
# ═══════════════════════════════════════════════════════════════════════

@login_required
def admin_liste_evaluations(request):
    """
    Toutes les évaluations, avec filtre sur la note globale et sur la
    recommandation — utile pour repérer rapidement les avis négatifs
    (note basse ou recommande=False) à traiter en priorité.
    """
    from apps_evaluation.models import Evaluation

    evaluations = Evaluation.objects.select_related(
        'livraison', 'livraison__entreprise', 'livraison__livreur__utilisateur'
    ).order_by('-date')

    note = request.GET.get('note')
    if note:
        evaluations = evaluations.filter(note_globale=note)

    non_recommande = request.GET.get('non_recommande')
    if non_recommande == '1':
        evaluations = evaluations.filter(recommande=False)

    return render(request, 'apps_evaluation/admin_liste_evaluations.html', {
        'evaluations': evaluations,
        'filtre_note': note or '',
        'filtre_non_recommande': non_recommande or '',
    })


@login_required
def admin_detail_evaluation(request, pk):
    """Fiche complète d'une évaluation — lecture seule, aucune modification admin sur un avis client."""
    from apps_evaluation.models import Evaluation

    evaluation = get_object_or_404(
        Evaluation.objects.select_related(
            'livraison', 'livraison__entreprise', 'livraison__livreur__utilisateur'
        ), pk=pk
    )
    return render(request, 'apps_evaluation/admin_detail_evaluation.html', {'evaluation': evaluation})


# ═══════════════════════════════════════════════════════════════════════
# ESPACE LIVREUR — évaluations reçues sur ses propres livraisons
# ═══════════════════════════════════════════════════════════════════════

@login_required
def livreur_mes_evaluations(request):
    from apps_evaluation.models import Evaluation

    livreur = getattr(request.user, 'profil_livreur', None)
    if livreur is None:
        messages.error(request, "Aucun profil livreur associé à ce compte.")
        return redirect('apps_core:accueil')

    evaluations = Evaluation.objects.filter(
        livraison__livreur=livreur
    ).select_related('livraison').order_by('-date')

    return render(request, 'apps_evaluation/livreur_mes_evaluations.html', {'evaluations': evaluations})


# ═══════════════════════════════════════════════════════════════════════
# ESPACE ENTREPRISE — évaluations reçues sur ses propres livraisons
# ═══════════════════════════════════════════════════════════════════════

@login_required
def entreprise_mes_evaluations(request):
    from apps_evaluation.models import Evaluation

    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')

    evaluations = Evaluation.objects.filter(
        livraison__entreprise=entreprise
    ).select_related('livraison', 'livraison__livreur__utilisateur').order_by('-date')

    return render(request, 'apps_evaluation/entreprise_mes_evaluations.html', {'evaluations': evaluations})