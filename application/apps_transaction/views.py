 
# ═══════════════════════════════════════════════════════════════════════
# apps_transaction/views.py — FRAGMENT
# ═══════════════════════════════════════════════════════════════════════
 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
 
 
# ═══════════════════════════════════════════════════════════════════════
# ADMINISTRATION — Lots de paiement & transactions
# TODO : protéger avec request.user.est_admin une fois les permissions
# par rôle branchées, comme dans le reste du projet.
# ═══════════════════════════════════════════════════════════════════════



@login_required
def admin_liste_lots_paiement(request):
    from apps_transaction.models import LotPaiementEntreprise
    from apps_core.choices import StatutLotPaiement
 
    lots = LotPaiementEntreprise.objects.select_related('entreprise').order_by('-date_creation')
 
    statut = request.GET.get('statut')
    if statut:
        lots = lots.filter(statut=statut)
 
    entreprise_id = request.GET.get('entreprise')
    if entreprise_id:
        lots = lots.filter(entreprise_id=entreprise_id)
 
    return render(request, 'apps_transaction/admin_liste_lots_paiement.html', {
        'lots': lots, 'statuts': StatutLotPaiement.choices, 'filtre_statut': statut or '',
    })
 
 
@login_required
def admin_creer_lot_paiement(request):
    """
    Crée le lot puis appelle immédiatement construire_depuis_livraisons_
    eligibles() pour agréger les livraisons de la période et calculer le
    montant net — sans cet appel, le lot resterait à 0 FCFA en
    EN_PREPARATION indéfiniment.
    """
    from apps_transaction.forms import LotPaiementForm
 
    if request.method == 'POST':
        form = LotPaiementForm(request.POST)
        if form.is_valid():
            lot = form.save()
            lot.construire_depuis_livraisons_eligibles()
            if lot.livraisons.count() == 0:
                messages.info(request, f"Lot {lot.reference} créé, mais aucune livraison éligible sur cette période.")
            else:
                messages.success(
                    request,
                    f"Lot {lot.reference} créé — {lot.livraisons.count()} livraison(s), "
                    f"{lot.montant_net_a_payer} FCFA net à payer."
                )
            return redirect('apps_transaction:admin_detail_lot_paiement', pk=lot.pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = LotPaiementForm()
 
    return render(request, 'apps_transaction/admin_creer_lot_paiement.html', {'form': form})

@login_required
def admin_recalculer_lot_paiement(request, pk):
    """
    Ré-exécute construire_depuis_livraisons_eligibles() sur un lot
    existant — utile quand des livraisons ont été validées côté
    entreprise APRÈS la création initiale du lot (cf. bug des lots à 0
    FCFA créés avant la validation de réception).
    Refusé si le lot a déjà été envoyé, pour ne pas modifier un montant
    déjà communiqué à l'entreprise.
    """
    from apps_transaction.models import LotPaiementEntreprise

    lot = get_object_or_404(LotPaiementEntreprise, pk=pk)

    if not lot.peut_etre_recalcule:
        messages.error(request, "Ce lot a déjà été envoyé, il ne peut plus être recalculé.")
        return redirect('apps_transaction:admin_detail_lot_paiement', pk=pk)

    ancien_montant = lot.montant_net_a_payer
    lot.construire_depuis_livraisons_eligibles()

    if lot.livraisons.count() == 0:
        messages.info(request, f"Lot {lot.reference} recalculé — toujours aucune livraison éligible.")
    else:
        messages.success(
            request,
            f"Lot {lot.reference} recalculé — {lot.livraisons.count()} livraison(s), "
            f"{lot.montant_net_a_payer} FCFA net (ancien montant : {ancien_montant} FCFA)."
        )
    return redirect('apps_transaction:admin_detail_lot_paiement', pk=pk)
 
 
@login_required
def admin_detail_lot_paiement(request, pk):
    from apps_transaction.models import LotPaiementEntreprise
    from apps_transaction.forms import EnvoyerLotPaiementForm
 
    lot = get_object_or_404(LotPaiementEntreprise.objects.select_related('entreprise'), pk=pk)
    livraisons = lot.livraisons.order_by('-date_livraison_effective')
 
    # Transaction n'a pas de FK directe vers LotPaiementEntreprise :
    # confirmer_reception_entreprise() les journalise avec
    # note=f'Payé via lot {reference}' — c'est le seul lien exploitable.
    transactions = []
    if lot.entreprise_id:
        transactions = lot.entreprise.transactions.filter(note__icontains=lot.reference).order_by('-date')
 
    return render(request, 'apps_transaction/admin_detail_lot_paiement.html', {
        'lot': lot, 'livraisons': livraisons, 'transactions': transactions,
        'envoyer_form': EnvoyerLotPaiementForm(),
    })
 
 
@login_required
def admin_marquer_lot_envoye(request, pk):
    from apps_transaction.models import LotPaiementEntreprise
    from apps_transaction.forms import EnvoyerLotPaiementForm
 
    lot = get_object_or_404(LotPaiementEntreprise, pk=pk)
    if request.method == 'POST':
        form = EnvoyerLotPaiementForm(request.POST, request.FILES)
        if form.is_valid():
            lot.marquer_envoye(
                request.user,
                reference_externe=form.cleaned_data.get('reference_transaction_externe', ''),
                preuve=form.cleaned_data.get('preuve_paiement'),
            )
            messages.success(request, f"Lot {lot.reference} marqué comme envoyé.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire.")
    return redirect('apps_transaction:admin_detail_lot_paiement', pk=pk)
 
 
@login_required
def admin_liste_transactions(request):
    """Journal comptable complet, tous flux confondus (lecture seule)."""
    from apps_transaction.models import Transaction
 
    transactions = Transaction.objects.select_related('entreprise').order_by('-date')
 
    type_transaction = request.GET.get('type')
    if type_transaction:
        transactions = transactions.filter(type_transaction=type_transaction)
 
    entreprise_id = request.GET.get('entreprise')
    if entreprise_id:
        transactions = transactions.filter(entreprise_id=entreprise_id)
 
    return render(request, 'apps_transaction/admin_liste_transactions.html', {
        'transactions': transactions, 'types': Transaction.Type.choices, 'filtre_type': type_transaction or '',
    })


# ═══════════════════════════════════════════════════════════════════════
# ESPACE ENTREPRISE — mes lots de paiement & mes transactions
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def mes_lots_paiement(request):
    from apps_transaction.models import LotPaiementEntreprise
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    lots = LotPaiementEntreprise.objects.filter(entreprise=entreprise).order_by('-date_creation')
    return render(request, 'apps_transaction/mes_lots_paiement.html', {'lots': lots})
 
 
@login_required
def detail_lot_paiement(request, pk):
    from apps_transaction.models import LotPaiementEntreprise
    from apps_core.choices import StatutLotPaiement

    entreprise = getattr(request.user, 'entreprise', None)
    lot = get_object_or_404(LotPaiementEntreprise, pk=pk, entreprise=entreprise)
    livraisons = lot.livraisons.order_by('-date_livraison_effective')

    return render(request, 'apps_transaction/detail_lot_paiement.html', {
        'lot': lot, 'livraisons': livraisons, 'STATUT': StatutLotPaiement,
    })
    
@login_required
def confirmer_reception_lot(request, pk):
    """
    L'entreprise confirme avoir reçu le paiement — SEUL chemin qui génère
    les Transaction de type GAIN_ENTREPRISE pour ce lot (cf.
    LotPaiementEntreprise.confirmer_reception_entreprise()).
    """
    from apps_transaction.models import LotPaiementEntreprise
    from apps_core.choices import StatutLotPaiement
 
    entreprise = getattr(request.user, 'entreprise', None)
    lot = get_object_or_404(LotPaiementEntreprise, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        if lot.statut != StatutLotPaiement.ENVOYE:
            messages.error(request, "Ce lot n'a pas encore été marqué comme envoyé par l'administration.")
        else:
            lot.confirmer_reception_entreprise(request.user)
            messages.success(request, f"Réception du lot {lot.reference} confirmée — merci.")
    return redirect('apps_transaction:detail_lot_paiement', pk=pk)
 
 
@login_required
def signaler_litige_lot(request, pk):
    """
    Permet à l'entreprise de signaler un désaccord sur un lot ENVOYÉ,
    avant de le confirmer. N'écrit QUE note_litige : le modèle ne prévoit
    pas de statut de litige dédié, donc le statut du lot n'est
    volontairement pas modifié ici — la note est à traiter manuellement
    côté admin.
    """
    from apps_transaction.models import LotPaiementEntreprise
    from apps_transaction.forms import SignalerLitigeLotForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    lot = get_object_or_404(LotPaiementEntreprise, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        form = SignalerLitigeLotForm(request.POST)
        if form.is_valid():
            lot.note_litige = form.cleaned_data['note_litige']
            lot.save(update_fields=['note_litige'])
            messages.success(request, "Votre remarque a été transmise à l'administration.")
        else:
            messages.error(request, "Merci de décrire le problème rencontré.")
    return redirect('apps_transaction:detail_lot_paiement', pk=pk)
 
 
@login_required
def mes_transactions(request):
    """Journal comptable de l'entreprise connectée (lecture seule)."""
    from apps_transaction.models import Transaction
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    transactions = Transaction.objects.filter(entreprise=entreprise).order_by('-date')
    return render(request, 'apps_transaction/mes_transactions.html', {'transactions': transactions})
 