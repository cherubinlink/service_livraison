from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

# Create your views here.



# ═══════════════════════════════════════════════════════════════════════
# CATÉGORIES (administration — taxonomie plateforme, pas par entreprise)
# TODO : protéger chaque vue admin_* avec une vérification
# request.user.est_admin une fois les permissions par rôle branchées.
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def admin_liste_categories(request):
    """
    Liste hiérarchique (parent → sous-catégories) + formulaire unique
    d'ajout/édition. Si categorie_id est fourni en POST, le formulaire
    édite cette catégorie ; sinon il en crée une nouvelle — même principe
    que apps_core.views.configuration_geographie.
    """
    from apps_catalogue.models import Categorie
    from apps_catalogue.forms import CategorieForm
 
    if request.method == 'POST':
        categorie_id = request.POST.get('categorie_id')
        instance = get_object_or_404(Categorie, pk=categorie_id) if categorie_id else None
        form = CategorieForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Catégorie enregistrée.")
            return redirect('apps_catalogue:admin_liste_categories')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = CategorieForm()
 
    categories = Categorie.objects.filter(parent__isnull=True).prefetch_related(
        'sous_categories'
    ).order_by('ordre', 'nom')
 
    return render(request, 'apps_catalogue/admin_categories.html', {'categories': categories, 'form': form})
 
 
@login_required
def admin_modifier_categorie(request, pk):
    from apps_catalogue.models import Categorie
    from apps_catalogue.forms import CategorieForm
 
    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == 'POST':
        form = CategorieForm(request.POST, instance=categorie)
        if form.is_valid():
            form.save()
            messages.success(request, "Catégorie mise à jour.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire.")
    return redirect('apps_catalogue:admin_liste_categories')
 
 
@login_required
def admin_toggle_categorie(request, pk):
    from apps_catalogue.models import Categorie
 
    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == 'POST':
        categorie.est_active = not categorie.est_active
        categorie.save(update_fields=['est_active'])
        etat = 'activée' if categorie.est_active else 'désactivée'
        messages.success(request, f"Catégorie « {categorie.nom} » {etat}.")
    return redirect('apps_catalogue:admin_liste_categories')
 
 
@login_required
def admin_supprimer_categorie(request, pk):
    """Protégée par Django lui-même : Produit.categorie et Categorie.parent sont en SET_NULL, donc la suppression n'échoue jamais ici — mais on garde le try/except par prudence si le schéma évolue."""
    from apps_catalogue.models import Categorie
    from django.db.models import ProtectedError
 
    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == 'POST':
        try:
            nom = categorie.nom
            categorie.delete()
            messages.success(request, f"Catégorie « {nom} » supprimée.")
        except ProtectedError:
            messages.error(request, "Impossible de supprimer : des éléments y sont encore rattachés.")
    return redirect('apps_catalogue:admin_liste_categories')


# ═══════════════════════════════════════════════════════════════════════
# PRODUITS — ADMINISTRATION (enregistrement au nom d'une entreprise)
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def admin_liste_produits(request):
    """Liste des produits pour l'admin, avec filtres par statut, entreprise et recherche texte."""
    from apps_catalogue.models import Produit
    from django.db.models import Q
 
    produits = Produit.objects.select_related('entreprise', 'categorie').order_by('-date_creation')
 
    statut = request.GET.get('statut')
    if statut:
        produits = produits.filter(statut=statut)
 
    entreprise_id = request.GET.get('entreprise')
    if entreprise_id:
        produits = produits.filter(entreprise_id=entreprise_id)
 
    recherche = request.GET.get('q')
    if recherche:
        produits = produits.filter(Q(nom__icontains=recherche) | Q(reference_sku__icontains=recherche))
 
    return render(request, 'apps_catalogue/admin_liste_produits.html', {
        'produits': produits,
        'statuts': Produit.StatutProduit.choices,
        'filtre_statut': statut or '',
        'recherche': recherche or '',
    })
 
 
@login_required
def admin_creer_produit(request):
    """
    Enregistre un nouveau produit au nom d'une entreprise et le place
    immédiatement dans un entrepôt avec une quantité initiale. C'est
    l'ENTREPRISE qui valide ensuite ce produit — cf. Produit.StatutProduit
    (workflow inversé par rapport à la validation d'une Entreprise, où
    c'est l'admin qui valide).
    """
    from apps_catalogue.models import Produit, StockEntrepot
    from apps_catalogue.forms import ProduitCreationForm
 
    if request.method == 'POST':
        form = ProduitCreationForm(request.POST, request.FILES)
        if form.is_valid():
            produit = form.save(commit=False)
            produit.enregistre_par = request.user
            produit.statut = Produit.StatutProduit.EN_ATTENTE
            produit.save()
 
            StockEntrepot.objects.create(
                produit=produit,
                entrepot=form.cleaned_data['entrepot'],
                quantite_stock=form.cleaned_data['quantite_initiale'],
                seuil_alerte=produit.seuil_alerte_defaut,
                seuil_rupture=produit.seuil_rupture_defaut,
            )
 
            messages.success(
                request,
                f"Produit « {produit.nom} » enregistré — en attente de validation par l'entreprise."
            )
            return redirect('apps_catalogue:admin_detail_produit', pk=produit.pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ProduitCreationForm()
 
    return render(request, 'apps_catalogue/admin_creer_produit.html', {'form': form})
 
 
@login_required
def admin_detail_produit(request, pk):
    from apps_catalogue.models import Produit
 
    produit = get_object_or_404(Produit.objects.select_related('entreprise', 'categorie'), pk=pk)
    stocks = produit.stocks_entrepots.select_related('entrepot')
    photos = produit.photos.all()
 
    return render(request, 'apps_catalogue/admin_detail_produit.html', {
        'produit': produit, 'stocks': stocks, 'photos': photos,
    })
 


# ═══════════════════════════════════════════════════════════════════════
# PRODUITS — ESPACE ENTREPRISE (self-service)
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def mes_produits(request):
    """Liste des produits de l'entreprise connectée, avec filtre par statut."""
    from apps_catalogue.models import Produit
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    produits = Produit.objects.filter(entreprise=entreprise).select_related('categorie').order_by('-date_creation')
 
    statut = request.GET.get('statut')
    if statut:
        produits = produits.filter(statut=statut)
 
    return render(request, 'apps_catalogue/mes_produits.html', {
        'produits': produits, 'statuts': Produit.StatutProduit.choices, 'filtre_statut': statut or '',
    })
 
 
@login_required
def detail_produit(request, pk):
    """Fiche produit côté entreprise — inclut les actions valider/refuser si EN_ATTENTE."""
    from apps_catalogue.models import Produit
    from apps_catalogue.forms import MotifRefusProduitForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    produit = get_object_or_404(Produit, pk=pk, entreprise=entreprise)
    stocks = produit.stocks_entrepots.select_related('entrepot')
    photos = produit.photos.all()
 
    return render(request, 'apps_catalogue/detail_produit.html', {
        'produit': produit, 'stocks': stocks, 'photos': photos, 'motif_form': MotifRefusProduitForm(),
    })
 
 
@login_required
def valider_produit(request, pk):
    """L'entreprise confirme que le produit enregistré par l'admin en son nom est correct."""
    from apps_catalogue.models import Produit
 
    entreprise = getattr(request.user, 'entreprise', None)
    produit = get_object_or_404(Produit, pk=pk, entreprise=entreprise)
    if request.method == 'POST':
        produit.valider(request.user)
        messages.success(request, f"Produit « {produit.nom} » validé.")
    return redirect('apps_catalogue:detail_produit', pk=pk)
 
 
@login_required
def refuser_produit(request, pk):
    from apps_catalogue.models import Produit
    from apps_catalogue.forms import MotifRefusProduitForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    produit = get_object_or_404(Produit, pk=pk, entreprise=entreprise)
    if request.method == 'POST':
        form = MotifRefusProduitForm(request.POST)
        if form.is_valid():
            produit.refuser(request.user, form.cleaned_data['motif'])
            messages.success(request, f"Produit « {produit.nom} » refusé.")
        else:
            messages.error(request, "Le motif de refus est obligatoire.")
    return redirect('apps_catalogue:detail_produit', pk=pk)
 
 
@login_required
def modifier_produit(request, pk):
    """Ajuste les aspects commerciaux d'un produit déjà enregistré (prix, description, mise en ligne...)."""
    from apps_catalogue.models import Produit
    from apps_catalogue.forms import ProduitEditForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    produit = get_object_or_404(Produit, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        form = ProduitEditForm(request.POST, request.FILES, instance=produit)
        if form.is_valid():
            form.save()
            messages.success(request, "Produit mis à jour.")
            return redirect('apps_catalogue:detail_produit', pk=pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ProduitEditForm(instance=produit)
 
    return render(request, 'apps_catalogue/modifier_produit.html', {'form': form, 'produit': produit})
 
 
@login_required
def ajouter_photo_produit(request, pk):
    from apps_catalogue.models import Produit
    from apps_catalogue.forms import PhotoProduitForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    produit = get_object_or_404(Produit, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        form = PhotoProduitForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.produit = produit
            photo.save()
            messages.success(request, "Photo ajoutée.")
            return redirect('apps_catalogue:detail_produit', pk=pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = PhotoProduitForm()
 
    return render(request, 'apps_catalogue/ajouter_photo_produit.html', {'form': form, 'produit': produit})
 
 
@login_required
def supprimer_photo_produit(request, pk):
    from apps_catalogue.models import PhotoProduit
 
    entreprise = getattr(request.user, 'entreprise', None)
    photo = get_object_or_404(PhotoProduit, pk=pk, produit__entreprise=entreprise)
    produit_pk = photo.produit_id
 
    if request.method == 'POST':
        photo.delete()
        messages.success(request, "Photo supprimée.")
    return redirect('apps_catalogue:detail_produit', pk=produit_pk)
 
