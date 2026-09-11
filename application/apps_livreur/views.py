from decimal import Decimal, InvalidOperation
 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

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



def inscription_livreur(request):
    """
    Inscription Livreur — crée à la fois le compte Utilisateur
    (role=LIVREUR) et le profil Livreur lié, sur le même principe que
    apps_entreprise.views.inscription_entreprise().
 
    Contrairement à Entreprise, aucun statut "EN_ATTENTE" n'existe sur le
    modèle Livreur : le compte est créé avec statut=INACTIF (défaut du
    modèle). Le livreur active lui-même sa disponibilité depuis son
    tableau de bord (cf. changer_statut_livreur ci-dessous) une fois prêt
    à recevoir des courses — il n'y a pas de validation admin bloquante
    équivalente à Entreprise.valider().
 
    Même logique OTP non bloquante que les autres inscriptions (voir la
    note dans apps_core.views.inscription()).
    """
    from apps_core.models import Utilisateur
    from apps_livreur.forms import InscriptionLivreurForm
    from apps_livreur.models import Livreur
 
    if request.user.is_authenticated:
        return redirect('apps_core:accueil')
 
    if request.method == 'POST':
        form = InscriptionLivreurForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
 
            user = Utilisateur.objects.create_user(
                email=cd['email'],
                password=cd['mot_de_passe'],
                nom=cd['nom_contact'],
                telephone=cd['telephone'],
                role=Utilisateur.Role.LIVREUR,
            )
 
            livreur = Livreur.objects.create(
                utilisateur=user,
                numero_cni=cd['numero_cni'],
                type_vehicule=cd['type_vehicule'],
                immatriculation=cd.get('immatriculation', ''),
                capacite_charge_kg=cd.get('capacite_charge_kg'),
                photo_cni=cd.get('photo_cni'),
            )
            if cd.get('zones_travail'):
                livreur.zones_travail.set(cd['zones_travail'])
 
            # OTP généré mais non bloquant — voir apps_core.views.inscription()
            user.generer_otp()
 
            login(request, user)
            messages.success(
                request,
                f"Bienvenue {user.nom} ! Votre compte livreur a été créé. "
                f"Activez votre disponibilité depuis votre tableau de bord dès que vous êtes prêt à recevoir des courses."
            )
            return redirect('apps_livreur:dashboard_livreur')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = InscriptionLivreurForm()
 
    return render(request, 'apps_livreur/inscription_livreur.html', {'form': form})


 
@login_required
def modifier_profil_livreur(request):
    """
    Édite les informations modifiables d'un livreur déjà inscrit.
    numero_cni est volontairement exclu du formulaire (document
    d'identité — changement réservé à l'administration).
    """
    from apps_livreur.forms import ModifierProfilLivreurForm
 
    livreur = getattr(request.user, 'profil_livreur', None)
    if livreur is None:
        messages.error(request, "Aucun profil livreur associé à ce compte.")
        return redirect('apps_livreur:dashboard_livreur')
 
    if request.method == 'POST':
        form = ModifierProfilLivreurForm(request.POST, request.FILES, instance=livreur)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect('apps_livreur:dashboard_livreur')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ModifierProfilLivreurForm(instance=livreur)
 
    return render(request, 'apps_livreur/modifier_profil_livreur.html', {'form': form, 'livreur': livreur})
 
 
@login_required
def changer_statut_livreur(request, statut):
    """
    Change le statut de disponibilité du livreur connecté (boutons
    "Passer actif" / "Pause" / "Hors ligne" du tableau de bord).
 
    Un livreur SUSPENDU ne peut jamais se réactiver lui-même via cette
    vue — seul un admin peut lever une suspension (cf. admin_reactiver_livreur).
    EN_MISSION n'est pas non plus accessible ici : ce statut est piloté
    automatiquement par le cycle de vie d'une Livraison (attribution/prise
    en charge), pas par un choix manuel du livreur.
    """
    from apps_livreur.models import Livreur
 
    livreur = getattr(request.user, 'profil_livreur', None)
    if livreur is None:
        messages.error(request, "Aucun profil livreur associé à ce compte.")
        return redirect('apps_livreur:dashboard_livreur')
 
    if livreur.statut == Livreur.Statut.SUSPENDU:
        messages.error(request, "Votre compte est suspendu. Contactez l'administration.")
        return redirect('apps_livreur:dashboard_livreur')
 
    statuts_autorises = {Livreur.Statut.ACTIF, Livreur.Statut.PAUSE, Livreur.Statut.INACTIF}
    if statut not in statuts_autorises:
        messages.error(request, "Statut invalide.")
        return redirect('apps_livreur:dashboard_livreur')
 
    if request.method == 'POST':
        livreur.statut = statut
        livreur.save(update_fields=['statut'])
        messages.success(request, f"Statut mis à jour : {livreur.get_statut_display()}.")
    return redirect('apps_livreur:dashboard_livreur')
 
 
@login_required
def mettre_a_jour_position(request):
    """
    Endpoint JSON appelé périodiquement par le client (JS géolocalisation)
    pendant qu'un livreur est actif/en mission — met à jour sa position
    courante ET journalise un point dans PositionLivreurHistorique pour
    le suivi temps réel et l'audit d'une livraison en cours.
    """
    from apps_livreur.models import PositionLivreurHistorique
    from django.utils import timezone
 
    if request.method != 'POST':
        return JsonResponse({'erreur': 'Méthode non autorisée, POST requis.'}, status=405)
 
    livreur = getattr(request.user, 'profil_livreur', None)
    if livreur is None:
        return JsonResponse({'erreur': 'Aucun profil livreur associé à ce compte.'}, status=403)
 
    try:
        latitude = Decimal(request.POST.get('latitude', ''))
        longitude = Decimal(request.POST.get('longitude', ''))
    except (InvalidOperation, TypeError):
        return JsonResponse({'erreur': 'Coordonnées latitude/longitude invalides.'}, status=400)
 
    livreur.latitude_actuelle = latitude
    livreur.longitude_actuelle = longitude
    livreur.derniere_position = timezone.now()
    livreur.save(update_fields=['latitude_actuelle', 'longitude_actuelle', 'derniere_position'])
 
    livraison = None
    livraison_id = request.POST.get('livraison_id')
    if livraison_id:
        from apps_livraison.models import Livraison
        livraison = Livraison.objects.filter(pk=livraison_id, livreur=livreur).first()
 
    PositionLivreurHistorique.objects.create(
        livreur=livreur, latitude=latitude, longitude=longitude, livraison_en_cours=livraison,
    )
 
    return JsonResponse({'ok': True})



# ═══════════════════════════════════════════════════════════════════════
# ADMINISTRATION DES LIVREURS
# TODO : protéger chaque vue avec une vérification request.user.est_admin
# une fois les permissions par rôle branchées (actuellement seul
# @login_required est appliqué, comme dans le reste du projet).
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def admin_liste_livreurs(request):
    """Liste des livreurs pour l'admin, avec filtres par statut, véhicule et recherche texte."""
    from apps_livreur.models import Livreur
    from apps_core.choices import TypeVehicule
    from django.db.models import Q
 
    livreurs = Livreur.objects.select_related('utilisateur').order_by('utilisateur__nom')
 
    statut = request.GET.get('statut')
    if statut:
        livreurs = livreurs.filter(statut=statut)
 
    vehicule = request.GET.get('vehicule')
    if vehicule:
        livreurs = livreurs.filter(type_vehicule=vehicule)
 
    recherche = request.GET.get('q')
    if recherche:
        livreurs = livreurs.filter(
            Q(utilisateur__nom__icontains=recherche) | Q(numero_cni__icontains=recherche)
        )
 
    return render(request, 'apps_livreur/admin_liste.html', {
        'livreurs': livreurs,
        'statuts': Livreur.Statut.choices,
        'vehicules': TypeVehicule.choices,
        'filtre_statut': statut or '',
        'filtre_vehicule': vehicule or '',
        'recherche': recherche or '',
    })
 
 
@login_required
def admin_detail_livreur(request, pk):
    """Fiche complète d'un livreur pour l'admin : profil, dernières positions, livraisons récentes, actions."""
    from apps_livreur.models import Livreur
 
    livreur = get_object_or_404(Livreur, pk=pk)
    dernieres_positions = livreur.historique_positions.all()[:20]
 
    livraisons_recentes = []
    try:
        from apps_livraison.models import Livraison
        livraisons_recentes = Livraison.objects.filter(livreur=livreur).order_by('-date_creation')[:10]
    except Exception:
        pass
 
    return render(request, 'apps_livreur/admin_detail.html', {
        'livreur': livreur,
        'dernieres_positions': dernieres_positions,
        'livraisons_recentes': livraisons_recentes,
    })
 
 
@login_required
def admin_suspendre_livreur(request, pk):
    from apps_livreur.models import Livreur
 
    livreur = get_object_or_404(Livreur, pk=pk)
    if request.method == 'POST':
        livreur.statut = Livreur.Statut.SUSPENDU
        livreur.save(update_fields=['statut'])
        messages.success(request, f"Livreur « {livreur.utilisateur.nom} » suspendu.")
    return redirect('apps_livreur:admin_detail_livreur', pk=pk)
 
 
@login_required
def admin_reactiver_livreur(request, pk):
    """
    Lève une suspension. Le livreur repasse en INACTIF (hors ligne) — pas
    directement ACTIF : c'est à lui de repasser actif depuis son tableau
    de bord une fois reconnecté, cohérent avec changer_statut_livreur().
    """
    from apps_livreur.models import Livreur
 
    livreur = get_object_or_404(Livreur, pk=pk)
    if request.method == 'POST':
        livreur.statut = Livreur.Statut.INACTIF
        livreur.save(update_fields=['statut'])
        messages.success(request, f"Livreur « {livreur.utilisateur.nom} » réactivé (hors ligne).")
    return redirect('apps_livreur:admin_detail_livreur', pk=pk)


# ═══════════════════════════════════════════════════════════════════════
# apps_livreur/views.py — AJOUTS (à coller après changer_statut_livreur,
# avant la section ADMINISTRATION DES LIVREURS)
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def historique_livraisons(request):
    """
    Historique des courses TERMINÉES du livreur connecté (livrées,
    échouées, refusées).
 
    Distinct de `apps_livraison:livreur_mes_livraisons` (déjà existante
    dans le sidebar) qui affiche les courses ACTIVES/assignées — cette
    vue-ci est l'archive en lecture seule.
    """
    from apps_livraison.models import Livraison
    from django.core.paginator import Paginator
 
    livreur = getattr(request.user, 'profil_livreur', None)
    if livreur is None:
        messages.error(request, "Aucun profil livreur associé à ce compte.")
        return redirect('apps_livreur:dashboard_livreur')
 
    statuts_historique = [Livraison.Statut.LIVREE, Livraison.Statut.ECHEC, Livraison.Statut.REFUSEE]
    livraisons = Livraison.objects.filter(
        livreur=livreur, statut__in=statuts_historique
    ).order_by('-date_livraison_effective')
 
    statut = request.GET.get('statut')
    if statut and statut in [s.value for s in statuts_historique]:
        livraisons = livraisons.filter(statut=statut)
 
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    if date_debut:
        livraisons = livraisons.filter(date_livraison_effective__date__gte=date_debut)
    if date_fin:
        livraisons = livraisons.filter(date_livraison_effective__date__lte=date_fin)
 
    paginator = Paginator(livraisons, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
 
    return render(request, 'apps_livreur/historique_livraisons.html', {
        'livreur': livreur,
        'page_obj': page_obj,
        'livraisons': page_obj.object_list,
        'statuts': [(s.value, s.label) for s in statuts_historique],
        'filtre_statut': statut or '',
        'date_debut': date_debut or '',
        'date_fin': date_fin or '',
    })
 
 
@login_required
def historique_position(request):
    """
    Historique des positions GPS journalisées pour le livreur connecté
    (alimenté par `mettre_a_jour_position()` ci-dessus, table
    PositionLivreurHistorique).
 
    Filtrable par livraison (`?livraison=<uuid>`) pour rejouer le trajet
    d'une course précise.
    """
    from apps_livreur.models import PositionLivreurHistorique
    from django.core.paginator import Paginator
 
    livreur = getattr(request.user, 'profil_livreur', None)
    if livreur is None:
        messages.error(request, "Aucun profil livreur associé à ce compte.")
        return redirect('apps_livreur:dashboard_livreur')
 
    positions = PositionLivreurHistorique.objects.filter(
        livreur=livreur
    ).select_related('livraison_en_cours')
 
    livraison_id = request.GET.get('livraison')
    if livraison_id:
        positions = positions.filter(livraison_en_cours_id=livraison_id)
 
    paginator = Paginator(positions, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
 
    return render(request, 'apps_livreur/historique_position.html', {
        'livreur': livreur,
        'page_obj': page_obj,
        'positions': page_obj.object_list,
        'derniere_position': positions.first(),
        'filtre_livraison': livraison_id or '',
    })
 
 
@login_required
def mes_revenus(request):
    """
    Revenus du livreur connecté.
 
    ⚠️ apps_transaction (Transaction / LotPaiementEntreprise) ne couvre
    que les flux entreprise ↔ plateforme — il n'existe aucune Transaction
    dédiée au paiement des livreurs dans le modèle actuel. Cette vue
    calcule donc le revenu directement depuis `frais_livraison_applique`
    des courses livrées. Si un jour un vrai flux de paiement livreur est
    mis en place (virement, Mobile Money...), remplace ce calcul par une
    somme sur les enregistrements de paiement réels plutôt que par une
    estimation à partir des livraisons.
    """
    from apps_livraison.models import Livraison
    from django.core.paginator import Paginator
    from django.db.models import Sum
    from django.utils import timezone
    from decimal import Decimal
 
    livreur = getattr(request.user, 'profil_livreur', None)
    if livreur is None:
        messages.error(request, "Aucun profil livreur associé à ce compte.")
        return redirect('apps_livreur:dashboard_livreur')
 
    livraisons_livrees = Livraison.objects.filter(
        livreur=livreur, statut=Livraison.Statut.LIVREE
    ).order_by('-date_livraison_effective')
 
    aujourdhui = timezone.now().date()
    debut_semaine = aujourdhui - timezone.timedelta(days=aujourdhui.weekday())
    debut_mois = aujourdhui.replace(day=1)
 
    total_revenu = livraisons_livrees.aggregate(
        total=Sum('frais_livraison_applique')
    )['total'] or Decimal('0.00')
 
    revenu_semaine = livraisons_livrees.filter(
        date_livraison_effective__date__gte=debut_semaine
    ).aggregate(total=Sum('frais_livraison_applique'))['total'] or Decimal('0.00')
 
    revenu_mois = livraisons_livrees.filter(
        date_livraison_effective__date__gte=debut_mois
    ).aggregate(total=Sum('frais_livraison_applique'))['total'] or Decimal('0.00')
 
    paginator = Paginator(livraisons_livrees, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
 
    return render(request, 'apps_livreur/mes_revenus.html', {
        'livreur': livreur,
        'page_obj': page_obj,
        'livraisons': page_obj.object_list,
        'total_revenu': total_revenu,
        'revenu_semaine': revenu_semaine,
        'revenu_mois': revenu_mois,
        'nb_livraisons_payees': livraisons_livrees.count(),
    })
 
 
