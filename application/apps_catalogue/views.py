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
 


# ═══════════════════════════════════════════════════════════════════════
# STOCKS PAR ENTREPÔT
# ═══════════════════════════════════════════════════════════════════════

@login_required
def mes_stocks(request):
    """Vue d'ensemble des stocks de l'entreprise connectée, tous entrepôts confondus."""
    from apps_catalogue.models import StockEntrepot

    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')

    stocks = StockEntrepot.objects.filter(
        produit__entreprise=entreprise
    ).select_related('produit', 'entrepot').order_by('produit__nom', 'entrepot__nom')

    return render(request, 'apps_catalogue/mes_stocks.html', {'stocks': stocks})


@login_required
def admin_liste_stocks_entrepot(request, entrepot_pk):
    """Vue admin : tout ce qui est stocké dans un entrepôt donné."""
    from apps_catalogue.models import StockEntrepot
    from apps_entreprise.models import Entrepot

    entrepot = get_object_or_404(Entrepot, pk=entrepot_pk)
    stocks = StockEntrepot.objects.filter(entrepot=entrepot).select_related('produit', 'produit__entreprise')

    return render(request, 'apps_catalogue/admin_stocks_entrepot.html', {'entrepot': entrepot, 'stocks': stocks})


@login_required
def detail_stock_entrepot(request, pk):
    """
    Détail d'une ligne StockEntrepot : mouvements, alertes, et actions
    (réapprovisionner, transférer, ajuster) — accessible à l'admin ou à
    l'entreprise propriétaire du produit concerné (vérifié explicitement).
    """
    from apps_catalogue.models import StockEntrepot
    from apps_catalogue.forms import ReapprovisionnementForm, TransfertStockForm, AjustementStockForm

    stock = get_object_or_404(StockEntrepot.objects.select_related('produit', 'entrepot'), pk=pk)

    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is not None and stock.produit.entreprise_id != entreprise.id:
        messages.error(request, "Ce stock n'appartient pas à votre entreprise.")
        return redirect('apps_catalogue:mes_stocks')

    mouvements = stock.mouvements.select_related('effectue_par')[:30]
    alertes = stock.alertes.filter(traitee=False)

    return render(request, 'apps_catalogue/detail_stock_entrepot.html', {
        'stock': stock,
        'mouvements': mouvements,
        'alertes': alertes,
        'reappro_form': ReapprovisionnementForm(),
        'transfert_form': TransfertStockForm(),
        'ajustement_form': AjustementStockForm(),
    })


@login_required
def reapprovisionner_stock(request, pk):
    """Ajoute de la quantité à un stock existant (réception de marchandise)."""
    from apps_catalogue.models import StockEntrepot, MouvementStock, Produit
    from apps_catalogue.forms import ReapprovisionnementForm

    stock = get_object_or_404(StockEntrepot, pk=pk)
    if request.method == 'POST':
        form = ReapprovisionnementForm(request.POST)
        if form.is_valid():
            quantite = form.cleaned_data['quantite']
            avant = stock.quantite_stock
            stock.quantite_stock += quantite
            stock.save(update_fields=['quantite_stock'])

            MouvementStock.objects.create(
                stock_entrepot=stock,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE_REAPPRO,
                quantite=quantite,
                stock_avant=avant,
                stock_apres=stock.quantite_stock,
                cout_unitaire=form.cleaned_data.get('cout_unitaire'),
                note=form.cleaned_data.get('note', ''),
                effectue_par=request.user,
            )

            # Un réappro peut faire sortir le produit de rupture.
            if stock.produit.statut == Produit.StatutProduit.EPUISE and stock.produit.stock_total_disponible > 0:
                stock.produit.statut = Produit.StatutProduit.VALIDE
                stock.produit.save(update_fields=['statut'])

            messages.success(request, f"+{quantite} unité(s) ajoutée(s) à {stock.produit.nom} @ {stock.entrepot.nom}.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire.")
    return redirect('apps_catalogue:detail_stock_entrepot', pk=pk)


@login_required
def transferer_stock(request, pk):
    """
    Transfère une quantité d'un entrepôt vers un autre pour le même
    produit — décrémente la ligne source, crée ou incrémente la ligne
    destination, journalise un MouvementStock des deux côtés.
    """
    from apps_catalogue.models import StockEntrepot, MouvementStock
    from apps_catalogue.forms import TransfertStockForm

    stock_source = get_object_or_404(StockEntrepot, pk=pk)
    if request.method == 'POST':
        form = TransfertStockForm(request.POST)
        if form.is_valid():
            quantite = form.cleaned_data['quantite']
            entrepot_dest = form.cleaned_data['entrepot_destination']

            if entrepot_dest == stock_source.entrepot:
                messages.error(request, "L'entrepôt de destination doit être différent de l'entrepôt source.")
                return redirect('apps_catalogue:detail_stock_entrepot', pk=pk)

            if quantite > stock_source.quantite_disponible:
                messages.error(
                    request, f"Stock insuffisant : {stock_source.quantite_disponible} disponible(s) seulement."
                )
                return redirect('apps_catalogue:detail_stock_entrepot', pk=pk)

            # Sortie côté source
            avant_source = stock_source.quantite_stock
            stock_source.quantite_stock -= quantite
            stock_source.save(update_fields=['quantite_stock'])
            MouvementStock.objects.create(
                stock_entrepot=stock_source,
                type_mouvement=MouvementStock.TypeMouvement.TRANSFERT_ENTREPOT,
                quantite=-quantite,
                stock_avant=avant_source,
                stock_apres=stock_source.quantite_stock,
                note=form.cleaned_data.get('note', '') or f"Transfert vers {entrepot_dest.nom}",
                effectue_par=request.user,
            )

            # Entrée côté destination (créée si elle n'existe pas encore)
            stock_dest, _cree = StockEntrepot.objects.get_or_create(
                produit=stock_source.produit, entrepot=entrepot_dest,
                defaults={'seuil_alerte': stock_source.seuil_alerte, 'seuil_rupture': stock_source.seuil_rupture},
            )
            avant_dest = stock_dest.quantite_stock
            stock_dest.quantite_stock += quantite
            stock_dest.save(update_fields=['quantite_stock'])
            MouvementStock.objects.create(
                stock_entrepot=stock_dest,
                type_mouvement=MouvementStock.TypeMouvement.TRANSFERT_ENTREPOT,
                quantite=quantite,
                stock_avant=avant_dest,
                stock_apres=stock_dest.quantite_stock,
                note=form.cleaned_data.get('note', '') or f"Transfert depuis {stock_source.entrepot.nom}",
                effectue_par=request.user,
            )

            messages.success(request, f"{quantite} unité(s) transférée(s) vers {entrepot_dest.nom}.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire.")
    return redirect('apps_catalogue:detail_stock_entrepot', pk=pk)


@login_required
def ajuster_stock(request, pk):
    """Ajustement manuel après inventaire physique, ou signalement de perte/péremption."""
    from apps_catalogue.models import StockEntrepot, MouvementStock
    from apps_catalogue.forms import AjustementStockForm

    stock = get_object_or_404(StockEntrepot, pk=pk)
    if request.method == 'POST':
        form = AjustementStockForm(request.POST)
        if form.is_valid():
            type_mouvement = form.cleaned_data['type_mouvement']
            quantite = form.cleaned_data['quantite']
            est_negatif = type_mouvement in (
                MouvementStock.TypeMouvement.AJUSTEMENT_MOINS,
                MouvementStock.TypeMouvement.PERTE,
                MouvementStock.TypeMouvement.PEREMPTION,
            )

            if est_negatif and quantite > stock.quantite_stock:
                messages.error(request, f"Impossible : seulement {stock.quantite_stock} en stock.")
                return redirect('apps_catalogue:detail_stock_entrepot', pk=pk)

            avant = stock.quantite_stock
            stock.quantite_stock += -quantite if est_negatif else quantite
            stock.save(update_fields=['quantite_stock'])

            MouvementStock.objects.create(
                stock_entrepot=stock,
                type_mouvement=type_mouvement,
                quantite=-quantite if est_negatif else quantite,
                stock_avant=avant,
                stock_apres=stock.quantite_stock,
                note=form.cleaned_data['note'],
                effectue_par=request.user,
            )
            stock._verifier_alertes()

            messages.success(request, "Ajustement enregistré.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire (une justification est obligatoire).")
    return redirect('apps_catalogue:detail_stock_entrepot', pk=pk)


# ═══════════════════════════════════════════════════════════════════════
# ALERTES DE STOCK
# ═══════════════════════════════════════════════════════════════════════

@login_required
def mes_alertes_stock(request):
    """Alertes actives (non traitées) sur les produits de l'entreprise connectée."""
    from apps_catalogue.models import AlerteStock

    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')

    alertes = AlerteStock.objects.filter(
        stock_entrepot__produit__entreprise=entreprise, traitee=False
    ).select_related('stock_entrepot__produit', 'stock_entrepot__entrepot').order_by('-date')

    return render(request, 'apps_catalogue/mes_alertes_stock.html', {'alertes': alertes})


@login_required
def admin_liste_alertes_stock(request):
    """Toutes les alertes actives, tous produits/entreprises confondus."""
    from apps_catalogue.models import AlerteStock

    alertes = AlerteStock.objects.filter(traitee=False).select_related(
        'stock_entrepot__produit__entreprise', 'stock_entrepot__entrepot'
    ).order_by('-date')

    return render(request, 'apps_catalogue/admin_alertes_stock.html', {'alertes': alertes})


@login_required
def traiter_alerte_stock(request, pk):
    """Marque une alerte comme traitée (réapprovisionnement effectué, ou faux positif accepté)."""
    from apps_catalogue.models import AlerteStock
    from django.utils import timezone

    alerte = get_object_or_404(AlerteStock, pk=pk)
    if request.method == 'POST':
        alerte.traitee = True
        alerte.traitee_par = request.user
        alerte.date_traitement = timezone.now()
        alerte.save(update_fields=['traitee', 'traitee_par', 'date_traitement'])
        messages.success(request, "Alerte marquée comme traitée.")

    if getattr(request.user, 'entreprise', None):
        return redirect('apps_catalogue:mes_alertes_stock')
    return redirect('apps_catalogue:admin_liste_alertes_stock')


# ═══════════════════════════════════════════════════════════════════════
# RETOURS DE STOCK AU PROPRIÉTAIRE (inactivité 30 jours, etc.)
# ═══════════════════════════════════════════════════════════════════════

@login_required
def mes_retours_stock(request):
    """
    Liste, côté entreprise, les produits qui lui ont été retournés (ex :
    suite à une désactivation pour inactivité — cf. apps_entreprise.
    Entreprise.desactiver_pour_inactivite). L'entreprise confirme ici
    être passée récupérer physiquement la marchandise.
    """
    from apps_catalogue.models import RetourStockProprietaire

    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')

    retours = RetourStockProprietaire.objects.filter(entreprise=entreprise).select_related(
        'produit', 'entrepot'
    ).order_by('-date_creation')

    return render(request, 'apps_catalogue/mes_retours_stock.html', {'retours': retours})


@login_required
def confirmer_retrait_stock(request, pk):
    """L'entreprise confirme être passée récupérer la marchandise retournée."""
    from apps_catalogue.models import RetourStockProprietaire
    from django.utils import timezone

    entreprise = getattr(request.user, 'entreprise', None)
    retour = get_object_or_404(RetourStockProprietaire, pk=pk, entreprise=entreprise)

    if request.method == 'POST':
        retour.confirme_retire_par_entreprise = True
        retour.date_confirmation = timezone.now()
        retour.save(update_fields=['confirme_retire_par_entreprise', 'date_confirmation'])
        messages.success(request, "Retrait confirmé.")
    return redirect('apps_catalogue:mes_retours_stock')


@login_required
def admin_liste_retours_stock(request):
    """Vue admin de tous les retours de stock, avec filtre sur les retraits non encore confirmés."""
    from apps_catalogue.models import RetourStockProprietaire

    retours = RetourStockProprietaire.objects.select_related(
        'entreprise', 'produit', 'entrepot'
    ).order_by('-date_creation')

    if request.GET.get('non_confirmes') == '1':
        retours = retours.filter(confirme_retire_par_entreprise=False)

    return render(request, 'apps_catalogue/admin_retours_stock.html', {'retours': retours})