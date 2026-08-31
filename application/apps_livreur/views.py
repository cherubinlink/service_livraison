from django.shortcuts import render

# Create your views here.


def dashboard(request):
    """
    Tableau de bord du livreur connecté.
 
    TODO : protéger avec @login_required + récupérer le Livreur lié à
    request.user (request.user.profil_livreur) une fois l'authentification
    branchée.
    """
    contexte = {
        'livreur': None,
        'nb_courses_jour': 0,
        'nb_courses_total': 0,
        'note_moyenne': 0,
        'courses_assignees': [],
    }
    try:
        livreur = getattr(request.user, 'profil_livreur', None)
        if livreur is None:
            return render(request, 'apps_livreur/dashboard.html', contexte)
 
        from apps_livraison.models import Livraison
        from django.utils import timezone
 
        contexte['livreur'] = livreur
        contexte['nb_courses_total'] = livreur.total_livraisons
        contexte['note_moyenne'] = livreur.note_moyenne
 
        aujourdhui = timezone.now().date()
        contexte['nb_courses_jour'] = Livraison.objects.filter(
            livreur=livreur, date_prise_en_charge__date=aujourdhui
        ).count()
 
        contexte['courses_assignees'] = Livraison.objects.filter(
            livreur=livreur,
            statut__in=[Livraison.Statut.VALIDEE, Livraison.Statut.EN_COURS],
        ).order_by('-date_attribution')[:8]
    except Exception:
        pass
 
    return render(request, 'apps_livreur/dashboard_livreur.html', contexte)
