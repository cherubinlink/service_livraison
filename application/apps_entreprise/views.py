from django.shortcuts import render

# Create your views here.



def dashboard(request):
    """
    Tableau de bord de l'entreprise connectée.
 
    TODO : protéger avec @login_required + récupérer l'Entreprise liée à
    request.user (request.user.entreprise) une fois l'authentification
    branchée. Ici, on illustre la structure avec un filtrage défensif :
    si aucune entreprise n'est liée à l'utilisateur, on retombe sur des
    valeurs vides plutôt que de faire planter la page.
    """
    contexte = {
        'entreprise': None,
        'nb_produits': 0,
        'nb_produits_stock_bas': 0,
        'nb_livraisons_cours': 0,
        'gain_du_mois': 0,
        'alertes_stock': [],
        'livraisons_recentes': [],
        'prochain_lot': None,
    }
    try:
        entreprise = getattr(request.user, 'entreprise', None)
        if entreprise is None:
            return render(request, 'apps_entreprise/dashboard.html', contexte)
 
        from apps_catalogue.models import Produit, AlerteStock
        from apps_livraison.models import Livraison
        from apps_transaction.models import LotPaiementEntreprise
        from apps_core.choices import StatutLotPaiement
        from django.db.models import Sum
 
        contexte['entreprise'] = entreprise
        contexte['nb_produits'] = Produit.objects.filter(entreprise=entreprise).count()
        contexte['nb_produits_stock_bas'] = AlerteStock.objects.filter(
            stock_entrepot__produit__entreprise=entreprise, traitee=False
        ).count()
        contexte['nb_livraisons_cours'] = Livraison.objects.filter(
            entreprise=entreprise, statut=Livraison.Statut.EN_COURS
        ).count()
        contexte['gain_du_mois'] = Livraison.objects.filter(
            entreprise=entreprise, statut=Livraison.Statut.LIVREE
        ).aggregate(t=Sum('gain_entreprise'))['t'] or 0
 
        contexte['alertes_stock'] = AlerteStock.objects.filter(
            stock_entrepot__produit__entreprise=entreprise, traitee=False
        ).select_related('stock_entrepot__produit', 'stock_entrepot__entrepot')[:5]
 
        contexte['livraisons_recentes'] = Livraison.objects.filter(
            entreprise=entreprise
        ).order_by('-date_creation')[:8]
 
        contexte['prochain_lot'] = LotPaiementEntreprise.objects.filter(
            entreprise=entreprise,
            statut__in=[StatutLotPaiement.EN_PREPARATION, StatutLotPaiement.PRET_A_ENVOYER, StatutLotPaiement.ENVOYE],
        ).order_by('-date_creation').first()
    except Exception:
        pass
 
    return render(request, 'apps_entreprise/dashboard.html', contexte)