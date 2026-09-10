# ═══════════════════════════════════════════════════════════════════════
# apps_livraison/views.py — FRAGMENT à fusionner dans ton fichier réel.
# Utilise LivraisonCreationForm, LigneLivraisonForm, AttributionLivreurForm,
# MotifLivraisonForm, SignalerPaiementFraisForm, ConfirmationLivraisonForm
# (déjà dans apps_livraison/forms.py).
# ═══════════════════════════════════════════════════════════════════════
 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required



#  ═══════════════════════════════════════════════════════════════════════
# ESPACE ENTREPRISE — création et suivi de ses propres commandes
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def mes_livraisons(request):
    """Liste des livraisons de l'entreprise connectée, avec filtre par statut."""
    from apps_livraison.models import Livraison
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    livraisons = Livraison.objects.filter(entreprise=entreprise).order_by('-date_creation')
 
    statut = request.GET.get('statut')
    if statut:
        livraisons = livraisons.filter(statut=statut)
 
    return render(request, 'apps_livraison/mes_livraisons.html', {
        'livraisons': livraisons, 'statuts': Livraison.Statut.choices, 'filtre_statut': statut or '',
    })
 
 
@login_required
def creer_livraison(request):
    """
    Crée l'en-tête d'une commande (statut BROUILLON). Les lignes produit
    s'ajoutent ensuite depuis detail_livraison() — impossible d'en créer
    avant que l'en-tête n'existe, puisqu'elles portent sa FK.
    """
    from apps_core.choices import OrigineCommande
    from apps_livraison.forms import LivraisonCreationForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    if request.method == 'POST':
        form = LivraisonCreationForm(request.POST)
        if form.is_valid():
            livraison = form.save(commit=False)
            livraison.entreprise = entreprise
            livraison.cree_par = request.user
            livraison.origine_commande = OrigineCommande.ENTREPRISE
            livraison.statut = livraison.Statut.BROUILLON
            livraison.save()
            messages.success(
                request,
                f"Brouillon {livraison.numero} créé — ajoutez vos produits puis soumettez la commande."
            )
            return redirect('apps_livraison:detail_livraison', pk=livraison.pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = LivraisonCreationForm()
 
    return render(request, 'apps_livraison/creer_livraison.html', {'form': form})
 
 
@login_required
def detail_livraison(request, pk):
    """
    Fiche complète côté entreprise : lignes de la commande, formulaire
    d'ajout de ligne si encore BROUILLON, actions (soumettre / annuler /
    valider la réception) proposées par le template selon le statut.
    """
    from apps_livraison.models import Livraison
    from apps_livraison.forms import LigneLivraisonForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    livraison = get_object_or_404(Livraison, pk=pk, entreprise=entreprise)
    lignes = livraison.lignes.select_related('produit', 'stock_entrepot__entrepot')
    historique = livraison.historique_statuts.select_related('effectue_par')
 
    ligne_form = LigneLivraisonForm(entreprise=entreprise) if livraison.statut == Livraison.Statut.BROUILLON else None
 
    return render(request, 'apps_livraison/detail_livraison.html', {
        'livraison': livraison, 'lignes': lignes, 'historique': historique, 'ligne_form': ligne_form,
    })
 
 
@login_required
def ajouter_ligne_livraison(request, pk):
    """Ajoute un produit à une commande encore en BROUILLON."""
    from apps_livraison.models import Livraison, LigneLivraison
    from apps_livraison.forms import LigneLivraisonForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    livraison = get_object_or_404(Livraison, pk=pk, entreprise=entreprise)
 
    if livraison.statut != Livraison.Statut.BROUILLON:
        messages.error(request, "Impossible d'ajouter un produit : cette commande n'est plus en brouillon.")
        return redirect('apps_livraison:detail_livraison', pk=pk)
 
    if request.method == 'POST':
        form = LigneLivraisonForm(request.POST, entreprise=entreprise)
        if form.is_valid():
            LigneLivraison.objects.create(
                livraison=livraison,
                produit=form.cleaned_data['produit'],
                stock_entrepot=form.cleaned_data['stock_entrepot'],
                quantite=form.cleaned_data['quantite'],
            )
            livraison.recalculer_depuis_lignes()
            messages.success(request, "Produit ajouté à la commande.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire.")
    return redirect('apps_livraison:detail_livraison', pk=pk)
 
 
@login_required
def supprimer_ligne_livraison(request, ligne_pk):
    """
    Retire une ligne d'une commande encore en BROUILLON. La libération de
    la réservation de stock est gérée automatiquement par le signal
    post_delete sur LigneLivraison (apps_livraison/signals.py) — rien à
    dupliquer ici côté stock.
    """
    from apps_livraison.models import Livraison, LigneLivraison
 
    entreprise = getattr(request.user, 'entreprise', None)
    ligne = get_object_or_404(LigneLivraison, pk=ligne_pk, livraison__entreprise=entreprise)
    livraison_pk = ligne.livraison_id
 
    if ligne.livraison.statut != Livraison.Statut.BROUILLON:
        messages.error(request, "Impossible de retirer ce produit : la commande n'est plus en brouillon.")
        return redirect('apps_livraison:detail_livraison', pk=livraison_pk)
 
    if request.method == 'POST':
        livraison = ligne.livraison
        ligne.delete()
        livraison.recalculer_depuis_lignes()
        messages.success(request, "Produit retiré de la commande.")
    return redirect('apps_livraison:detail_livraison', pk=livraison_pk)
 
 
@login_required
def soumettre_livraison(request, pk):
    """BROUILLON → EN_ATTENTE. Refusé si la commande n'a encore aucune ligne."""
    from apps_livraison.models import Livraison
 
    entreprise = getattr(request.user, 'entreprise', None)
    livraison = get_object_or_404(Livraison, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        if livraison.statut != Livraison.Statut.BROUILLON:
            messages.error(request, "Cette commande a déjà été soumise.")
        elif not livraison.lignes.exists():
            messages.error(request, "Ajoutez au moins un produit avant de soumettre la commande.")
        else:
            livraison.changer_statut(Livraison.Statut.EN_ATTENTE, request.user)
            messages.success(request, f"Commande {livraison.numero} soumise pour validation.")
    return redirect('apps_livraison:detail_livraison', pk=pk)
 
 
@login_required
def annuler_livraison(request, pk):
    """L'entreprise annule sa propre commande, uniquement avant validation admin."""
    from apps_livraison.models import Livraison
 
    entreprise = getattr(request.user, 'entreprise', None)
    livraison = get_object_or_404(Livraison, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        if livraison.statut not in (Livraison.Statut.BROUILLON, Livraison.Statut.EN_ATTENTE):
            messages.error(request, "Cette commande ne peut plus être annulée à ce stade.")
        else:
            livraison.changer_statut(Livraison.Statut.ANNULEE, request.user)
            messages.success(request, f"Commande {livraison.numero} annulée.")
    return redirect('apps_livraison:detail_livraison', pk=pk)
 
 
@login_required
def valider_reception_livraison(request, pk):
    """L'entreprise confirme avoir reçu les informations de livraison (produit livré au client)."""
    from apps_livraison.models import Livraison
 
    entreprise = getattr(request.user, 'entreprise', None)
    livraison = get_object_or_404(Livraison, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        try:
            livraison.valider_reception_entreprise(request.user)
            messages.success(request, "Réception validée — cette livraison entrera dans votre prochain lot de paiement.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect('apps_livraison:detail_livraison', pk=pk)


# ═══════════════════════════════════════════════════════════════════════
# ADMINISTRATION DES LIVRAISONS
# TODO : protéger avec request.user.est_admin une fois les permissions
# par rôle branchées, comme dans le reste du projet.
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def admin_liste_livraisons(request):
    from apps_livraison.models import Livraison
 
    livraisons = Livraison.objects.select_related('entreprise', 'livreur__utilisateur').order_by('-date_creation')
 
    statut = request.GET.get('statut')
    if statut:
        livraisons = livraisons.filter(statut=statut)
 
    return render(request, 'apps_livraison/admin_liste_livraisons.html', {
        'livraisons': livraisons, 'statuts': Livraison.Statut.choices, 'filtre_statut': statut or '',
    })
 
 
@login_required
def admin_detail_livraison(request, pk):
    from apps_livraison.models import Livraison
    from apps_livraison.forms import AttributionLivreurForm
 
    livraison = get_object_or_404(
        Livraison.objects.select_related('entreprise', 'livreur__utilisateur'), pk=pk
    )
    lignes = livraison.lignes.select_related('produit', 'stock_entrepot__entrepot')
    historique = livraison.historique_statuts.select_related('effectue_par')
 
    return render(request, 'apps_livraison/admin_detail_livraison.html', {
        'livraison': livraison, 'lignes': lignes, 'historique': historique,
        'attribution_form': AttributionLivreurForm(livraison=livraison),
    })
 
 
@login_required
def admin_valider_livraison(request, pk):
    from apps_livraison.models import Livraison
 
    livraison = get_object_or_404(Livraison, pk=pk)
    if request.method == 'POST':
        if livraison.statut != Livraison.Statut.EN_ATTENTE:
            messages.error(request, "Cette commande n'est pas en attente de validation.")
        else:
            livraison.changer_statut(Livraison.Statut.VALIDEE, request.user)
            messages.success(request, f"Commande {livraison.numero} validée.")
    return redirect('apps_livraison:admin_detail_livraison', pk=pk)
 
 
@login_required
def admin_refuser_livraison(request, pk):
    from apps_livraison.models import Livraison
    from apps_livraison.forms import MotifLivraisonForm
 
    livraison = get_object_or_404(Livraison, pk=pk)
    if request.method == 'POST':
        form = MotifLivraisonForm(request.POST)
        if form.is_valid():
            livraison.changer_statut(Livraison.Statut.REFUSEE, request.user, motif=form.cleaned_data['motif'])
            messages.success(request, f"Commande {livraison.numero} refusée.")
        else:
            messages.error(request, "Le motif de refus est obligatoire.")
    return redirect('apps_livraison:admin_detail_livraison', pk=pk)
 
 
@login_required
def admin_attribuer_livreur(request, pk):
    """
    Attribue un livreur à une commande VALIDÉE. Ne touche QUE le champ
    `livreur` (+ `attribue_par`) : le passage du livreur en EN_MISSION, la
    date d'attribution et sa notification sont gérés automatiquement par
    le signal apps_livraison.signals.notifier_attribution_livreur() dès
    que ce save() détecte `livreur` passant de None à une valeur — pas de
    logique à dupliquer ici.
    """
    from apps_livraison.models import Livraison
    from apps_livraison.forms import AttributionLivreurForm
 
    livraison = get_object_or_404(Livraison, pk=pk)
    if request.method == 'POST':
        form = AttributionLivreurForm(request.POST, livraison=livraison)
        if form.is_valid():
            livraison.livreur = form.cleaned_data['livreur']
            livraison.attribue_par = request.user
            livraison.save(update_fields=['livreur', 'attribue_par'])
            messages.success(request, f"{livraison.livreur.utilisateur.nom} attribué à la commande {livraison.numero}.")
        else:
            messages.error(request, "Merci de choisir un livreur.")
    return redirect('apps_livraison:admin_detail_livraison', pk=pk)
 
 
@login_required
def generer_code_confirmation(request, pk):
    """Génère (ou régénère) le code à 4 chiffres que le client communique au livreur à la livraison."""
    from apps_livraison.models import Livraison
 
    livraison = get_object_or_404(Livraison, pk=pk)
    if request.method == 'POST':
        code = livraison.generer_code_confirmation()
        messages.success(request, f"Code de confirmation généré : {code}")
    return redirect('apps_livraison:admin_detail_livraison', pk=pk)
 
 
# ═══════════════════════════════════════════════════════════════════════
# ESPACE LIVREUR — courses attribuées
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def livreur_mes_livraisons(request):
    from apps_livraison.models import Livraison
 
    livreur = getattr(request.user, 'profil_livreur', None)
    if livreur is None:
        messages.error(request, "Aucun profil livreur associé à ce compte.")
        return redirect('apps_core:accueil')
 
    livraisons = Livraison.objects.filter(livreur=livreur).exclude(
        statut__in=[Livraison.Statut.BROUILLON, Livraison.Statut.EN_ATTENTE]
    ).select_related('entreprise').order_by('-date_attribution')
 
    return render(request, 'apps_livraison/livreur_mes_livraisons.html', {'livraisons': livraisons})
 
 
@login_required
def livreur_detail_livraison(request, pk):
    from apps_livraison.models import Livraison
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(Livraison, pk=pk, livreur=livreur)
    lignes = livraison.lignes.select_related('produit')
 
    return render(request, 'apps_livraison/livreur_detail_livraison.html', {
        'livraison': livraison, 'lignes': lignes,
    })
 
 
@login_required
def livreur_prendre_en_charge(request, pk):
    """VALIDEE → EN_COURS : le livreur démarre effectivement la course."""
    from apps_livraison.models import Livraison
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(Livraison, pk=pk, livreur=livreur)
 
    if request.method == 'POST':
        if livraison.statut != Livraison.Statut.VALIDEE:
            messages.error(request, "Cette commande n'est pas prête à être prise en charge.")
        else:
            livraison.changer_statut(Livraison.Statut.EN_COURS, request.user)
            messages.success(request, f"Commande {livraison.numero} prise en charge.")
    return redirect('apps_livraison:livreur_detail_livraison', pk=pk)
 
 
@login_required
def livreur_signaler_paiement_frais(request, pk):
    from apps_livraison.models import Livraison
    from apps_livraison.forms import SignalerPaiementFraisForm
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(Livraison, pk=pk, livreur=livreur)
 
    if request.method == 'POST':
        form = SignalerPaiementFraisForm(request.POST)
        if form.is_valid():
            livraison.signaler_paiement_frais_client(
                request.user, form.cleaned_data['montant_paye'], form.cleaned_data['integralite']
            )
            messages.success(request, "Paiement des frais signalé.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire.")
    return redirect('apps_livraison:livreur_detail_livraison', pk=pk)
 
 
@login_required
def livreur_terminer_livraison(request, pk):
    """EN_COURS → LIVREE, avec preuve photo/signature obligatoire."""
    from apps_livraison.models import Livraison
    from apps_livraison.forms import ConfirmationLivraisonForm
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(Livraison, pk=pk, livreur=livreur)
 
    if livraison.statut != Livraison.Statut.EN_COURS:
        messages.error(request, "Cette commande n'est pas en cours de livraison.")
        return redirect('apps_livraison:livreur_detail_livraison', pk=pk)
 
    if request.method == 'POST':
        form = ConfirmationLivraisonForm(request.POST, request.FILES, instance=livraison)
        if form.is_valid():
            form.save()
            livraison.confirmation_recu = True
            livraison.save(update_fields=['confirmation_recu'])
            livraison.changer_statut(Livraison.Statut.LIVREE, request.user)
            messages.success(request, f"Commande {livraison.numero} marquée comme livrée.")
            return redirect('apps_livraison:livreur_detail_livraison', pk=pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ConfirmationLivraisonForm(instance=livraison)
 
    return render(request, 'apps_livraison/livreur_terminer_livraison.html', {
        'form': form, 'livraison': livraison,
    })
 
 
@login_required
def livreur_signaler_echec(request, pk):
    """EN_COURS → ECHEC, motif obligatoire."""
    from apps_livraison.models import Livraison
    from apps_livraison.forms import MotifLivraisonForm
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(Livraison, pk=pk, livreur=livreur)
 
    if request.method == 'POST':
        form = MotifLivraisonForm(request.POST)
        if livraison.statut != Livraison.Statut.EN_COURS:
            messages.error(request, "Cette commande n'est pas en cours de livraison.")
        elif form.is_valid():
            livraison.changer_statut(Livraison.Statut.ECHEC, request.user, motif=form.cleaned_data['motif'])
            messages.success(request, f"Échec signalé pour la commande {livraison.numero}.")
        else:
            messages.error(request, "Le motif de l'échec est obligatoire.")
    return redirect('apps_livraison:livreur_detail_livraison', pk=pk)
 



# ═══════════════════════════════════════════════════════════════════════
# ESPACE ENTREPRISE — création et suivi de ses propres commandes
# ═══════════════════════════════════════════════════════════════════════

@login_required
def entreprise_nouvelle_livraison_directe(request):
    """Une entreprise inscrite peut aussi initier une course directe, sans passer par le circuit produits/stock."""
    from apps_livraison.forms import LivraisonDirecteForm

    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')

    if request.method == 'POST':
        form = LivraisonDirecteForm(request.POST)
        if form.is_valid():
            livraison = form.save(commit=False)
            livraison.livraison_par_entreprise = entreprise
            livraison.save()
            messages.success(request, f"Course directe {livraison.numero} créée — prix estimé : {livraison.prix_total} FCFA.")
            return redirect('apps_livraison:mes_livraisons_directes')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = LivraisonDirecteForm()

    return render(request, 'apps_livraison/entreprise_nouvelle_livraison_directe.html', {'form': form})


 
@login_required
def mes_livraisons_directes(request):
    """Courses directes initiées par l'entreprise connectée."""
    from apps_livraison.models import LivraisonDirecte

    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')

    livraisons = LivraisonDirecte.objects.filter(
        livraison_par_entreprise=entreprise
    ).select_related('livreur__utilisateur').order_by('-date_creation')

    return render(request, 'apps_livraison/mes_livraisons_directes.html', {'livraisons': livraisons})
 
@login_required
def creer_livraison_directe(request):
    """
    Crée l'en-tête d'une commande (statut BROUILLON). Les lignes produit
    s'ajoutent ensuite depuis detail_livraison() — impossible d'en créer
    avant que l'en-tête n'existe, puisqu'elles portent sa FK.
    """
    from apps_core.choices import OrigineCommande
    from apps_livraison.forms import LivraisonCreationForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    if request.method == 'POST':
        form = LivraisonCreationForm(request.POST)
        if form.is_valid():
            livraison = form.save(commit=False)
            livraison.entreprise = entreprise
            livraison.cree_par = request.user
            livraison.origine_commande = OrigineCommande.ENTREPRISE
            livraison.statut = livraison.Statut.BROUILLON
            livraison.save()
            messages.success(
                request,
                f"Brouillon {livraison.numero} créé — ajoutez vos produits puis soumettez la commande."
            )
            return redirect('apps_livraison:detail_livraison', pk=livraison.pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = LivraisonCreationForm()
 
    return render(request, 'apps_livraison/creer_livraison_direct.html', {'form': form})
 
 
@login_required
def detail_livraison_direct(request, pk):
    """
    Fiche complète côté entreprise : lignes de la commande, formulaire
    d'ajout de ligne si encore BROUILLON, actions (soumettre / annuler /
    valider la réception) proposées par le template selon le statut.
    """
    from apps_livraison.models import Livraison
    from apps_livraison.forms import LigneLivraisonForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    livraison = get_object_or_404(Livraison, pk=pk, entreprise=entreprise)
    lignes = livraison.lignes.select_related('produit', 'stock_entrepot__entrepot')
    historique = livraison.historique_statuts.select_related('effectue_par')
 
    ligne_form = LigneLivraisonForm(entreprise=entreprise) if livraison.statut == Livraison.Statut.BROUILLON else None
 
    return render(request, 'apps_livraison/detail_livraison_direct.html', {
        'livraison': livraison, 'lignes': lignes, 'historique': historique, 'ligne_form': ligne_form,
    })
 
 
@login_required
def ajouter_ligne_livraison_direct(request, pk):
    """Ajoute un produit à une commande encore en BROUILLON."""
    from apps_livraison.models import Livraison, LigneLivraison
    from apps_livraison.forms import LigneLivraisonForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    livraison = get_object_or_404(Livraison, pk=pk, entreprise=entreprise)
 
    if livraison.statut != Livraison.Statut.BROUILLON:
        messages.error(request, "Impossible d'ajouter un produit : cette commande n'est plus en brouillon.")
        return redirect('apps_livraison:detail_livraison', pk=pk)
 
    if request.method == 'POST':
        form = LigneLivraisonForm(request.POST, entreprise=entreprise)
        if form.is_valid():
            LigneLivraison.objects.create(
                livraison=livraison,
                produit=form.cleaned_data['produit'],
                stock_entrepot=form.cleaned_data['stock_entrepot'],
                quantite=form.cleaned_data['quantite'],
            )
            livraison.recalculer_depuis_lignes()
            messages.success(request, "Produit ajouté à la commande.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire.")
    return redirect('apps_livraison:detail_livraison_direct', pk=pk)
 
 
@login_required
def supprimer_ligne_livraison_direct(request, ligne_pk):
    """
    Retire une ligne d'une commande encore en BROUILLON. La libération de
    la réservation de stock est gérée automatiquement par le signal
    post_delete sur LigneLivraison (apps_livraison/signals.py) — rien à
    dupliquer ici côté stock.
    """
    from apps_livraison.models import Livraison, LigneLivraison
 
    entreprise = getattr(request.user, 'entreprise', None)
    ligne = get_object_or_404(LigneLivraison, pk=ligne_pk, livraison__entreprise=entreprise)
    livraison_pk = ligne.livraison_id
 
    if ligne.livraison.statut != Livraison.Statut.BROUILLON:
        messages.error(request, "Impossible de retirer ce produit : la commande n'est plus en brouillon.")
        return redirect('apps_livraison:detail_livraison_direct', pk=livraison_pk)
 
    if request.method == 'POST':
        livraison = ligne.livraison
        ligne.delete()
        livraison.recalculer_depuis_lignes()
        messages.success(request, "Produit retiré de la commande.")
    return redirect('apps_livraison:detail_livraison', pk=livraison_pk)
 
 
@login_required
def soumettre_livraison(request, pk):
    """BROUILLON → EN_ATTENTE. Refusé si la commande n'a encore aucune ligne."""
    from apps_livraison.models import Livraison
 
    entreprise = getattr(request.user, 'entreprise', None)
    livraison = get_object_or_404(Livraison, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        if livraison.statut != Livraison.Statut.BROUILLON:
            messages.error(request, "Cette commande a déjà été soumise.")
        elif not livraison.lignes.exists():
            messages.error(request, "Ajoutez au moins un produit avant de soumettre la commande.")
        else:
            livraison.changer_statut(Livraison.Statut.EN_ATTENTE, request.user)
            messages.success(request, f"Commande {livraison.numero} soumise pour validation.")
    return redirect('apps_livraison:detail_livraison', pk=pk)
 
 
@login_required
def annuler_livraison(request, pk):
    """L'entreprise annule sa propre commande, uniquement avant validation admin."""
    from apps_livraison.models import Livraison
 
    entreprise = getattr(request.user, 'entreprise', None)
    livraison = get_object_or_404(Livraison, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        if livraison.statut not in (Livraison.Statut.BROUILLON, Livraison.Statut.EN_ATTENTE):
            messages.error(request, "Cette commande ne peut plus être annulée à ce stade.")
        else:
            livraison.changer_statut(Livraison.Statut.ANNULEE, request.user)
            messages.success(request, f"Commande {livraison.numero} annulée.")
    return redirect('apps_livraison:detail_livraison_direct', pk=pk)
 
 
@login_required
def valider_reception_livraison(request, pk):
    """L'entreprise confirme avoir reçu les informations de livraison (produit livré au client)."""
    from apps_livraison.models import Livraison
 
    entreprise = getattr(request.user, 'entreprise', None)
    livraison = get_object_or_404(Livraison, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        try:
            livraison.valider_reception_entreprise(request.user)
            messages.success(request, "Réception validée — cette livraison entrera dans votre prochain lot de paiement.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect('apps_livraison:detail_livraison', pk=pk)





# ═══════════════════════════════════════════════════════════════════════
# ADMINISTRATION DES LIVRAISONS
# TODO : protéger avec request.user.est_admin une fois les permissions
# par rôle branchées, comme dans le reste du projet.
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def admin_liste_livraisons(request):
    from apps_livraison.models import Livraison
 
    livraisons = Livraison.objects.select_related('entreprise', 'livreur__utilisateur').order_by('-date_creation')
 
    statut = request.GET.get('statut')
    if statut:
        livraisons = livraisons.filter(statut=statut)
 
    return render(request, 'apps_livraison/admin_liste_livraisons.html', {
        'livraisons': livraisons, 'statuts': Livraison.Statut.choices, 'filtre_statut': statut or '',
    })
 
 
@login_required
def admin_detail_livraison(request, pk):
    from apps_livraison.models import Livraison
    from apps_livraison.forms import AttributionLivreurForm
 
    livraison = get_object_or_404(
        Livraison.objects.select_related('entreprise', 'livreur__utilisateur'), pk=pk
    )
    lignes = livraison.lignes.select_related('produit', 'stock_entrepot__entrepot')
    historique = livraison.historique_statuts.select_related('effectue_par')
 
    return render(request, 'apps_livraison/admin_detail_livraison.html', {
        'livraison': livraison, 'lignes': lignes, 'historique': historique,
        'attribution_form': AttributionLivreurForm(livraison=livraison),
    })
 
 
@login_required
def admin_valider_livraison(request, pk):
    from apps_livraison.models import Livraison
 
    livraison = get_object_or_404(Livraison, pk=pk)
    if request.method == 'POST':
        if livraison.statut != Livraison.Statut.EN_ATTENTE:
            messages.error(request, "Cette commande n'est pas en attente de validation.")
        else:
            livraison.changer_statut(Livraison.Statut.VALIDEE, request.user)
            messages.success(request, f"Commande {livraison.numero} validée.")
    return redirect('apps_livraison:admin_detail_livraison', pk=pk)
 
 
@login_required
def admin_refuser_livraison(request, pk):
    from apps_livraison.models import Livraison
    from apps_livraison.forms import MotifLivraisonForm
 
    livraison = get_object_or_404(Livraison, pk=pk)
    if request.method == 'POST':
        form = MotifLivraisonForm(request.POST)
        if form.is_valid():
            livraison.changer_statut(Livraison.Statut.REFUSEE, request.user, motif=form.cleaned_data['motif'])
            messages.success(request, f"Commande {livraison.numero} refusée.")
        else:
            messages.error(request, "Le motif de refus est obligatoire.")
    return redirect('apps_livraison:admin_detail_livraison', pk=pk)
 
 
@login_required
def admin_attribuer_livreur(request, pk):
    """
    Attribue un livreur à une commande VALIDÉE. Ne touche QUE le champ
    `livreur` (+ `attribue_par`) : le passage du livreur en EN_MISSION, la
    date d'attribution et sa notification sont gérés automatiquement par
    le signal apps_livraison.signals.notifier_attribution_livreur() dès
    que ce save() détecte `livreur` passant de None à une valeur — pas de
    logique à dupliquer ici.
    """
    from apps_livraison.models import Livraison
    from apps_livraison.forms import AttributionLivreurForm
 
    livraison = get_object_or_404(Livraison, pk=pk)
    if request.method == 'POST':
        form = AttributionLivreurForm(request.POST, livraison=livraison)
        if form.is_valid():
            livraison.livreur = form.cleaned_data['livreur']
            livraison.attribue_par = request.user
            livraison.save(update_fields=['livreur', 'attribue_par'])
            messages.success(request, f"{livraison.livreur.utilisateur.nom} attribué à la commande {livraison.numero}.")
        else:
            messages.error(request, "Merci de choisir un livreur.")
    return redirect('apps_livraison:admin_detail_livraison', pk=pk)
 
 
@login_required
def generer_code_confirmation(request, pk):
    """Génère (ou régénère) le code à 4 chiffres que le client communique au livreur à la livraison."""
    from apps_livraison.models import Livraison
 
    livraison = get_object_or_404(Livraison, pk=pk)
    if request.method == 'POST':
        code = livraison.generer_code_confirmation()
        messages.success(request, f"Code de confirmation généré : {code}")
    return redirect('apps_livraison:admin_detail_livraison', pk=pk)
 
 
# ═══════════════════════════════════════════════════════════════════════
# ESPACE LIVREUR — courses attribuées
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def livreur_mes_livraisons(request):
    from apps_livraison.models import Livraison
 
    livreur = getattr(request.user, 'profil_livreur', None)
    if livreur is None:
        messages.error(request, "Aucun profil livreur associé à ce compte.")
        return redirect('apps_core:accueil')
 
    livraisons = Livraison.objects.filter(livreur=livreur).exclude(
        statut__in=[Livraison.Statut.BROUILLON, Livraison.Statut.EN_ATTENTE]
    ).select_related('entreprise').order_by('-date_attribution')
 
    return render(request, 'apps_livraison/livreur_mes_livraisons.html', {'livraisons': livraisons})
 
 
@login_required
def livreur_detail_livraison(request, pk):
    from apps_livraison.models import Livraison
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(Livraison, pk=pk, livreur=livreur)
    lignes = livraison.lignes.select_related('produit')
 
    return render(request, 'apps_livraison/livreur_detail_livraison.html', {
        'livraison': livraison, 'lignes': lignes,
    })
 
 
@login_required
def livreur_prendre_en_charge(request, pk):
    """VALIDEE → EN_COURS : le livreur démarre effectivement la course."""
    from apps_livraison.models import Livraison
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(Livraison, pk=pk, livreur=livreur)
 
    if request.method == 'POST':
        if livraison.statut != Livraison.Statut.VALIDEE:
            messages.error(request, "Cette commande n'est pas prête à être prise en charge.")
        else:
            livraison.changer_statut(Livraison.Statut.EN_COURS, request.user)
            messages.success(request, f"Commande {livraison.numero} prise en charge.")
    return redirect('apps_livraison:livreur_detail_livraison', pk=pk)
 
 
@login_required
def livreur_signaler_paiement_frais(request, pk):
    from apps_livraison.models import Livraison
    from apps_livraison.forms import SignalerPaiementFraisForm
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(Livraison, pk=pk, livreur=livreur)
 
    if request.method == 'POST':
        form = SignalerPaiementFraisForm(request.POST)
        if form.is_valid():
            livraison.signaler_paiement_frais_client(
                request.user, form.cleaned_data['montant_paye'], form.cleaned_data['integralite']
            )
            messages.success(request, "Paiement des frais signalé.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire.")
    return redirect('apps_livraison:livreur_detail_livraison', pk=pk)
 
 
@login_required
def livreur_terminer_livraison(request, pk):
    """EN_COURS → LIVREE, avec preuve photo/signature obligatoire."""
    from apps_livraison.models import Livraison
    from apps_livraison.forms import ConfirmationLivraisonForm
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(Livraison, pk=pk, livreur=livreur)
 
    if livraison.statut != Livraison.Statut.EN_COURS:
        messages.error(request, "Cette commande n'est pas en cours de livraison.")
        return redirect('apps_livraison:livreur_detail_livraison', pk=pk)
 
    if request.method == 'POST':
        form = ConfirmationLivraisonForm(request.POST, request.FILES, instance=livraison)
        if form.is_valid():
            form.save()
            livraison.confirmation_recu = True
            livraison.save(update_fields=['confirmation_recu'])
            livraison.changer_statut(Livraison.Statut.LIVREE, request.user)
            messages.success(request, f"Commande {livraison.numero} marquée comme livrée.")
            return redirect('apps_livraison:livreur_detail_livraison', pk=pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ConfirmationLivraisonForm(instance=livraison)
 
    return render(request, 'apps_livraison/livreur_terminer_livraison.html', {
        'form': form, 'livraison': livraison,
    })
 
 
@login_required
def livreur_signaler_echec(request, pk):
    """EN_COURS → ECHEC, motif obligatoire."""
    from apps_livraison.models import Livraison
    from apps_livraison.forms import MotifLivraisonForm
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(Livraison, pk=pk, livreur=livreur)
 
    if request.method == 'POST':
        form = MotifLivraisonForm(request.POST)
        if livraison.statut != Livraison.Statut.EN_COURS:
            messages.error(request, "Cette commande n'est pas en cours de livraison.")
        elif form.is_valid():
            livraison.changer_statut(Livraison.Statut.ECHEC, request.user, motif=form.cleaned_data['motif'])
            messages.success(request, f"Échec signalé pour la commande {livraison.numero}.")
        else:
            messages.error(request, "Le motif de l'échec est obligatoire.")
    return redirect('apps_livraison:livreur_detail_livraison', pk=pk)
 
 
# ═══════════════════════════════════════════════════════════════════════
# LIVRAISON DIRECTE — PUBLIC (aucun compte requis)
#
# NB : LivraisonDirecte n'a pas de champ `motif_echec` (contrairement à
# Livraison B2B) — les transitions ÉCHEC/ANNULÉE ci-dessous n'enregistrent
# donc pas de raison en base ; si tu veux en garder une trace, ajoute le
# champ au modèle avant d'étoffer ces vues.
# ═══════════════════════════════════════════════════════════════════════
 
def nouvelle_livraison_directe(request):
    """
    Formulaire public de création d'une course directe — pas de
    @login_required, volontairement accessible sans compte. `client` et
    `livraison_par_entreprise` restent NULL ici ; seule
    entreprise_nouvelle_livraison_directe() (plus bas) renseigne le
    second.
    """
    from apps_livraison.forms import LivraisonDirecteForm
 
    if request.method == 'POST':
        form = LivraisonDirecteForm(request.POST)
        if form.is_valid():
            livraison = form.save(commit=False)
            if request.user.is_authenticated:
                livraison.client = request.user
            livraison.save()
            messages.success(
                request,
                f"Votre demande {livraison.numero} a été enregistrée — prix estimé : {livraison.prix_total} FCFA."
            )
            return redirect('apps_livraison:suivre_livraison_directe', token=livraison.token_suivi)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = LivraisonDirecteForm()
 
    return render(request, 'apps_livraison/nouvelle_livraison_directe.html', {'form': form})
 
 
def suivre_livraison_directe(request, token):
    """
    Page de suivi publique — accessible via le lien contenant le
    token_suivi, sans compte ni mot de passe. Autorise aussi l'annulation
    par l'expéditeur tant que la course est encore EN_ATTENTE.
    """
    from apps_livraison.models import LivraisonDirecte
 
    livraison = get_object_or_404(LivraisonDirecte, token_suivi=token)
 
    if request.method == 'POST' and request.POST.get('action') == 'annuler':
        if livraison.statut == LivraisonDirecte.Statut.EN_ATTENTE:
            livraison.statut = LivraisonDirecte.Statut.ANNULEE
            livraison.save(update_fields=['statut'])
            messages.success(request, "Votre demande a été annulée.")
        else:
            messages.error(request, "Cette course ne peut plus être annulée à ce stade.")
        return redirect('apps_livraison:suivre_livraison_directe', token=token)
 
    return render(request, 'apps_livraison/suivre_livraison_directe.html', {'livraison': livraison})
 
 
# ═══════════════════════════════════════════════════════════════════════
# LIVRAISON DIRECTE — ESPACE ENTREPRISE (initiée par une entreprise inscrite)
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def entreprise_nouvelle_livraison_directe(request):
    """Une entreprise inscrite peut aussi initier une course directe, sans passer par le circuit produits/stock."""
    from apps_livraison.forms import LivraisonDirecteForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    if request.method == 'POST':
        form = LivraisonDirecteForm(request.POST)
        if form.is_valid():
            livraison = form.save(commit=False)
            livraison.livraison_par_entreprise = entreprise
            livraison.save()
            messages.success(request, f"Course directe {livraison.numero} créée — prix estimé : {livraison.prix_total} FCFA.")
            return redirect('apps_livraison:mes_livraisons_directes')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = LivraisonDirecteForm()
 
    return render(request, 'apps_livraison/entreprise_nouvelle_livraison_directe.html', {'form': form})
 
 
@login_required
def mes_livraisons_directes(request):
    """Courses directes initiées par l'entreprise connectée."""
    from apps_livraison.models import LivraisonDirecte
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    livraisons = LivraisonDirecte.objects.filter(
        livraison_par_entreprise=entreprise
    ).select_related('livreur__utilisateur').order_by('-date_creation')
 
    return render(request, 'apps_livraison/mes_livraisons_directes.html', {'livraisons': livraisons})
 
 
# ═══════════════════════════════════════════════════════════════════════
# LIVRAISON DIRECTE — ADMINISTRATION
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def admin_liste_livraisons_directes(request):
    from apps_livraison.models import LivraisonDirecte
 
    livraisons = LivraisonDirecte.objects.select_related(
        'livreur__utilisateur', 'livraison_par_entreprise'
    ).order_by('-date_creation')
 
    statut = request.GET.get('statut')
    if statut:
        livraisons = livraisons.filter(statut=statut)
 
    return render(request, 'apps_livraison/admin_liste_livraisons_directes.html', {
        'livraisons': livraisons, 'statuts': LivraisonDirecte.Statut.choices, 'filtre_statut': statut or '',
    })
 
 
@login_required
def admin_detail_livraison_directe(request, pk):
    from apps_livraison.models import LivraisonDirecte
    from apps_livraison.forms import AttributionLivreurDirecteForm, LivraisonDirecteAdminForm
 
    livraison = get_object_or_404(
        LivraisonDirecte.objects.select_related('livreur__utilisateur', 'livraison_par_entreprise', 'client'), pk=pk
    )
 
    return render(request, 'apps_livraison/admin_detail_livraison_directe.html', {
        'livraison': livraison,
        'attribution_form': AttributionLivreurDirecteForm(livraison_directe=livraison),
        'prix_form': LivraisonDirecteAdminForm(instance=livraison),
    })
 
 
@login_required
def admin_confirmer_livraison_directe(request, pk):
    """EN_ATTENTE → CONFIRMEE."""
    from apps_livraison.models import LivraisonDirecte
 
    livraison = get_object_or_404(LivraisonDirecte, pk=pk)
    if request.method == 'POST':
        if livraison.statut != LivraisonDirecte.Statut.EN_ATTENTE:
            messages.error(request, "Cette course n'est pas en attente de confirmation.")
        else:
            livraison.statut = LivraisonDirecte.Statut.CONFIRMEE
            livraison.save(update_fields=['statut'])
            messages.success(request, f"Course {livraison.numero} confirmée.")
    return redirect('apps_livraison:admin_detail_livraison_directe', pk=pk)
 
 
@login_required
def admin_attribuer_livreur_directe(request, pk):
    """
    Attribue un livreur à une course directe CONFIRMÉE.
    ⚠️ Contrairement à Livraison (B2B), aucun signal existant ne fait
    automatiquement passer ce livreur en EN_MISSION à cette attribution
    (le signal apps_livreur.signals ne couvre que 'apps_livraison.Livraison').
    À étendre si ce comportement est souhaité aussi pour LivraisonDirecte.
    """
    from apps_livraison.models import LivraisonDirecte
    from apps_livraison.forms import AttributionLivreurDirecteForm
 
    livraison = get_object_or_404(LivraisonDirecte, pk=pk)
    if request.method == 'POST':
        form = AttributionLivreurDirecteForm(request.POST, livraison_directe=livraison)
        if form.is_valid():
            livraison.livreur = form.cleaned_data['livreur']
            livraison.save(update_fields=['livreur'])
            messages.success(request, f"{livraison.livreur.utilisateur.nom} attribué à la course {livraison.numero}.")
        else:
            messages.error(request, "Merci de choisir un livreur.")
    return redirect('apps_livraison:admin_detail_livraison_directe', pk=pk)
 
 
@login_required
def admin_modifier_prix_directe(request, pk):
    """
    Édite la course (y compris tarif NÉGOCIÉ + montant) — seule cette vue
    admin a accès à LivraisonDirecteAdminForm en édition ; le formulaire
    public (LivraisonDirecteForm) ne propose jamais NEGOCIE.
    """
    from apps_livraison.models import LivraisonDirecte
    from apps_livraison.forms import LivraisonDirecteAdminForm
 
    livraison = get_object_or_404(LivraisonDirecte, pk=pk)
    if request.method == 'POST':
        form = LivraisonDirecteAdminForm(request.POST, instance=livraison)
        if form.is_valid():
            form.save()
            messages.success(request, f"Course {livraison.numero} mise à jour — prix : {livraison.prix_total} FCFA.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire.")
    return redirect('apps_livraison:admin_detail_livraison_directe', pk=pk)
 
 
@login_required
def admin_annuler_livraison_directe(request, pk):
    from apps_livraison.models import LivraisonDirecte
 
    livraison = get_object_or_404(LivraisonDirecte, pk=pk)
    if request.method == 'POST':
        if livraison.statut == LivraisonDirecte.Statut.LIVREE:
            messages.error(request, "Une course déjà livrée ne peut plus être annulée.")
        else:
            livraison.statut = LivraisonDirecte.Statut.ANNULEE
            livraison.save(update_fields=['statut'])
            messages.success(request, f"Course {livraison.numero} annulée.")
    return redirect('apps_livraison:admin_detail_livraison_directe', pk=pk)
 
 
# ═══════════════════════════════════════════════════════════════════════
# LIVRAISON DIRECTE — ESPACE LIVREUR
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def livreur_livraisons_directes(request):
    from apps_livraison.models import LivraisonDirecte
 
    livreur = getattr(request.user, 'profil_livreur', None)
    if livreur is None:
        messages.error(request, "Aucun profil livreur associé à ce compte.")
        return redirect('apps_core:accueil')
 
    livraisons = LivraisonDirecte.objects.filter(livreur=livreur).exclude(
        statut=LivraisonDirecte.Statut.EN_ATTENTE
    ).order_by('-date_creation')
 
    return render(request, 'apps_livraison/livreur_livraisons_directes.html', {'livraisons': livraisons})
 
 
@login_required
def livreur_detail_livraison_directe(request, pk):
    from apps_livraison.models import LivraisonDirecte
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(LivraisonDirecte, pk=pk, livreur=livreur)
 
    return render(request, 'apps_livraison/livreur_detail_livraison_directe.html', {'livraison': livraison})
 
 
@login_required
def livreur_prendre_en_charge_directe(request, pk):
    """CONFIRMEE → EN_COURS."""
    from apps_livraison.models import LivraisonDirecte
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(LivraisonDirecte, pk=pk, livreur=livreur)
 
    if request.method == 'POST':
        if livraison.statut != LivraisonDirecte.Statut.CONFIRMEE:
            messages.error(request, "Cette course n'est pas prête à être prise en charge.")
        else:
            livraison.statut = LivraisonDirecte.Statut.EN_COURS
            livraison.save(update_fields=['statut'])
            messages.success(request, f"Course {livraison.numero} prise en charge.")
    return redirect('apps_livraison:livreur_detail_livraison_directe', pk=pk)
 
 
@login_required
def livreur_terminer_livraison_directe(request, pk):
    """EN_COURS → LIVREE."""
    from apps_livraison.models import LivraisonDirecte
    from django.utils import timezone
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(LivraisonDirecte, pk=pk, livreur=livreur)
 
    if request.method == 'POST':
        if livraison.statut != LivraisonDirecte.Statut.EN_COURS:
            messages.error(request, "Cette course n'est pas en cours de livraison.")
        else:
            livraison.statut = LivraisonDirecte.Statut.LIVREE
            livraison.date_livraison = timezone.now()
            livraison.save(update_fields=['statut', 'date_livraison'])
            messages.success(request, f"Course {livraison.numero} marquée comme livrée.")
    return redirect('apps_livraison:livreur_detail_livraison_directe', pk=pk)
 
 
@login_required
def livreur_signaler_echec_directe(request, pk):
    """EN_COURS → ECHEC."""
    from apps_livraison.models import LivraisonDirecte
 
    livreur = getattr(request.user, 'profil_livreur', None)
    livraison = get_object_or_404(LivraisonDirecte, pk=pk, livreur=livreur)
 
    if request.method == 'POST':
        if livraison.statut != LivraisonDirecte.Statut.EN_COURS:
            messages.error(request, "Cette course n'est pas en cours de livraison.")
        else:
            livraison.statut = LivraisonDirecte.Statut.ECHEC
            livraison.save(update_fields=['statut'])
            messages.success(request, f"Échec signalé pour la course {livraison.numero}.")
    return redirect('apps_livraison:livreur_detail_livraison_directe', pk=pk)
 
 
 
