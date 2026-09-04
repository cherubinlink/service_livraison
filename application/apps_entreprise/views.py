from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from apps_entreprise.forms import EntrepotForm, AffectationEntrepotForm
from apps_entreprise.models import Entrepot, AffectationEntrepot

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


def inscription_entreprise(request):
    """
    Inscription Entreprise — crée le compte Utilisateur (role=ENTREPRISE)
    ET le profil Entreprise lié en une seule opération, contrairement à
    apps_core.views.inscription() qui ne crée que des comptes CLIENT.
 
    Contrairement à l'inscription Client (compte actif immédiatement),
    l'Entreprise créée ici reste au statut EN_ATTENTE — elle ne peut pas
    encore enregistrer de produits ni recevoir de livraisons tant qu'un
    admin ne l'a pas validée (cf. Entreprise.valider()). L'utilisateur
    est quand même connecté immédiatement après inscription : son
    tableau de bord entreprise doit afficher un bandeau "en attente de
    validation" tant que entreprise.statut != VALIDE.
 
    Même logique OTP que apps_core.views.inscription() : générée pour
    garder le flux prêt, non bloquante pour l'instant (voir la note dans
    cette dernière pour le détail).
    """
    from apps_core.models import Utilisateur
    from apps_entreprise.forms import InscriptionEntrepriseForm
    from apps_entreprise.models import Entreprise, DocumentEntreprise
 
    if request.user.is_authenticated:
        return redirect('apps_core:accueil')
 
    if request.method == 'POST':
        form = InscriptionEntrepriseForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
 
            user = Utilisateur.objects.create_user(
                email=cd['email'],
                password=cd['mot_de_passe'],
                nom=cd['nom_contact'],
                telephone=cd['telephone'],
                role=Utilisateur.Role.ENTREPRISE,
            )
 
            entreprise = Entreprise.objects.create(
                utilisateur=user,
                raison_sociale=cd['raison_sociale'],
                nom_commercial=cd.get('nom_commercial', ''),
                secteur=cd['secteur'],
                taille=cd['taille'],
                type_entreprise=cd['type_entreprise'],
                numero_registre=cd.get('numero_registre', ''),
                numero_contribuable_niu=cd.get('numero_contribuable_niu', ''),
                adresse_siege=cd['adresse_siege'],
                ville_principale=cd['ville_principale'],
                telephone_principal=cd['telephone_principal'],
            )
 
            # Documents optionnels — uploadés à l'inscription ou plus
            # tard depuis le tableau de bord, avant validation admin.
            if cd.get('document_registre'):
                fichier = cd['document_registre']
                DocumentEntreprise.objects.create(
                    entreprise=entreprise,
                    type_doc=DocumentEntreprise.TypeDocument.REGISTRE_COMMERCE,
                    nom_fichier=fichier.name,
                    fichier=fichier,
                    taille_fichier=fichier.size,
                )
            if cd.get('document_niu'):
                fichier = cd['document_niu']
                DocumentEntreprise.objects.create(
                    entreprise=entreprise,
                    type_doc=DocumentEntreprise.TypeDocument.CARTE_NIU,
                    nom_fichier=fichier.name,
                    fichier=fichier,
                    taille_fichier=fichier.size,
                )
 
            # OTP généré mais non bloquant — voir apps_core.views.inscription()
            user.generer_otp()
 
            login(request, user)
            messages.success(
                request,
                f"Bienvenue {entreprise.nom_affichage} ! Votre compte a été créé. "
                f"Il est en attente de validation par notre équipe avant de pouvoir "
                f"enregistrer des produits ou recevoir des livraisons."
            )
            return redirect('apps_entreprise:dashboard')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = InscriptionEntrepriseForm()
 
    return render(request, 'apps_entreprise/inscription_entreprise.html', {'form': form})


# ═══════════════════════════════════════════════════════════════════════
# ESPACE ENTREPRISE (self-service)
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def modifier_profil(request):
    """
    Édite les informations NON critiques de son entreprise. Volontairement
    exclus : raison_sociale, statut, numero_registre, numero_contribuable_niu,
    type_entreprise — ces champs engagent la validation admin et ne
    doivent pas être modifiables librement après inscription.
    """
    from apps_entreprise.forms import ProfilEntrepriseForm
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    if request.method == 'POST':
        form = ProfilEntrepriseForm(request.POST, request.FILES, instance=entreprise)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect('apps_entreprise:dashboard')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ProfilEntrepriseForm(instance=entreprise)
 
    return render(request, 'apps_entreprise/modifier_profil.html', {'form': form, 'entreprise': entreprise})
 
 
@login_required
def mes_documents(request):
    """Liste les documents de l'entreprise connectée + formulaire d'ajout."""
    from apps_entreprise.forms import DocumentEntrepriseForm
    from apps_entreprise.models import DocumentEntreprise
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    if request.method == 'POST':
        form = DocumentEntrepriseForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.entreprise = entreprise
            document.nom_fichier = form.cleaned_data['fichier'].name
            document.taille_fichier = form.cleaned_data['fichier'].size
            document.save()
            messages.success(request, "Document ajouté. Il sera vérifié par notre équipe.")
            return redirect('apps_entreprise:mes_documents')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = DocumentEntrepriseForm()
 
    documents = DocumentEntreprise.objects.filter(entreprise=entreprise).order_by('-date_upload')
    return render(request, 'apps_entreprise/mes_documents.html', {'form': form, 'documents': documents})
 
 
@login_required
def supprimer_document(request, pk):
    """Supprime un document — uniquement s'il n'est pas encore vérifié (un document validé ne se retire plus soi-même)."""
    from apps_entreprise.models import DocumentEntreprise
 
    entreprise = getattr(request.user, 'entreprise', None)
    document = get_object_or_404(DocumentEntreprise, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        if document.verifie:
            messages.error(request, "Impossible de supprimer un document déjà vérifié. Contactez l'administration.")
        else:
            document.delete()
            messages.success(request, "Document supprimé.")
    return redirect('apps_entreprise:mes_documents')
 
 
@login_required
def mes_contacts(request):
    """Liste les contacts secondaires de l'entreprise (gérant, comptable...) + formulaire d'ajout."""
    from apps_entreprise.forms import ContactEntrepriseForm
    from apps_entreprise.models import ContactEntreprise
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    if request.method == 'POST':
        form = ContactEntrepriseForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.entreprise = entreprise
            contact.save()
            messages.success(request, "Contact ajouté.")
            return redirect('apps_entreprise:mes_contacts')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ContactEntrepriseForm()
 
    contacts = ContactEntreprise.objects.filter(entreprise=entreprise)
    return render(request, 'apps_entreprise/mes_contacts.html', {'form': form, 'contacts': contacts})

@login_required
def modifier_contact(request, pk):
    from apps_entreprise.forms import ContactEntrepriseForm
    from apps_entreprise.models import ContactEntreprise
 
    entreprise = getattr(request.user, 'entreprise', None)
    contact = get_object_or_404(ContactEntreprise, pk=pk, entreprise=entreprise)
 
    if request.method == 'POST':
        form = ContactEntrepriseForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            messages.success(request, "Contact mis à jour.")
            return redirect('apps_entreprise:mes_contacts')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ContactEntrepriseForm(instance=contact)
 
    return render(request, 'apps_entreprise/modifier_contact.html', {'form': form, 'contact': contact})
 
 
@login_required
def supprimer_contact(request, pk):
    from apps_entreprise.models import ContactEntreprise
 
    entreprise = getattr(request.user, 'entreprise', None)
    contact = get_object_or_404(ContactEntreprise, pk=pk, entreprise=entreprise)
    if request.method == 'POST':
        contact.delete()
        messages.success(request, "Contact supprimé.")
    return redirect('apps_entreprise:mes_contacts')
 
 
@login_required
def mes_frais_gardiennage(request):
    """
    Lecture seule : l'entreprise voit ce qu'elle doit éventuellement payer
    pour éviter/annuler un retour de stock ou réactiver son compte après
    inactivité. La confirmation de paiement reste une action ADMIN
    (Entreprise.reactiver_via_gardiennage exige un admin_user) — cette vue
    n'autorise donc aucune écriture, seulement la consultation.
    """
    from apps_entreprise.models import FraisGardiennage
 
    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')
 
    frais = FraisGardiennage.objects.filter(entreprise=entreprise).order_by('-date_creation')
    return render(request, 'apps_entreprise/mes_frais_gardiennage.html', {'frais': frais, 'entreprise': entreprise})



# ═══════════════════════════════════════════════════════════════════════
# ADMINISTRATION DES ENTREPRISES
# TODO : protéger chaque vue avec une vérification request.user.est_admin
# une fois les permissions par rôle branchées (actuellement seul
# @login_required est appliqué, comme dans le reste du projet).
# ═══════════════════════════════════════════════════════════════════════
 
@login_required
def admin_liste_entreprises(request):
    """Liste des entreprises pour l'admin, avec filtres par statut, secteur et recherche texte."""
    from apps_entreprise.models import Entreprise
    from django.db.models import Q
 
    entreprises = Entreprise.objects.select_related('utilisateur', 'ville_principale').order_by('-date_creation')
 
    statut = request.GET.get('statut')
    if statut:
        entreprises = entreprises.filter(statut=statut)
 
    secteur = request.GET.get('secteur')
    if secteur:
        entreprises = entreprises.filter(secteur=secteur)
 
    recherche = request.GET.get('q')
    if recherche:
        entreprises = entreprises.filter(
            Q(raison_sociale__icontains=recherche) | Q(nom_commercial__icontains=recherche)
        )
 
    return render(request, 'apps_entreprise/admin_liste.html', {
        'entreprises': entreprises,
        'statuts': Entreprise.Statut.choices,
        'secteurs': Entreprise.Secteur.choices,
        'filtre_statut': statut or '',
        'filtre_secteur': secteur or '',
        'recherche': recherche or '',
    })
 
 
@login_required
def admin_detail_entreprise(request, pk):
    """Fiche complète d'une entreprise pour l'admin : infos, documents, contacts, gardiennage, actions de validation."""
    from apps_entreprise.models import Entreprise, DocumentEntreprise, ContactEntreprise, FraisGardiennage
    from apps_entreprise.forms import MotifForm, FraisGardiennageForm
 
    entreprise = get_object_or_404(Entreprise, pk=pk)
    documents = DocumentEntreprise.objects.filter(entreprise=entreprise).order_by('-date_upload')
    contacts = ContactEntreprise.objects.filter(entreprise=entreprise)
    frais_gardiennage = FraisGardiennage.objects.filter(entreprise=entreprise).order_by('-date_creation')
 
    return render(request, 'apps_entreprise/admin_detail.html', {
        'entreprise': entreprise,
        'documents': documents,
        'contacts': contacts,
        'frais_gardiennage': frais_gardiennage,
        'motif_form': MotifForm(),
        'gardiennage_form': FraisGardiennageForm(),
    })
 
 
@login_required
def admin_valider_entreprise(request, pk):
    from apps_entreprise.models import Entreprise
 
    entreprise = get_object_or_404(Entreprise, pk=pk)
    if request.method == 'POST':
        entreprise.valider(request.user)
        messages.success(request, f"Entreprise « {entreprise.raison_sociale} » validée.")
    return redirect('apps_entreprise:admin_detail_entreprise', pk=pk)
 
 
@login_required
def admin_refuser_entreprise(request, pk):
    from apps_entreprise.models import Entreprise
    from apps_entreprise.forms import MotifForm
 
    entreprise = get_object_or_404(Entreprise, pk=pk)
    if request.method == 'POST':
        form = MotifForm(request.POST)
        if form.is_valid():
            entreprise.refuser(request.user, form.cleaned_data['motif'])
            messages.success(request, f"Entreprise « {entreprise.raison_sociale} » refusée.")
        else:
            messages.error(request, "Le motif de refus est obligatoire.")
    return redirect('apps_entreprise:admin_detail_entreprise', pk=pk)
 
 
@login_required
def admin_suspendre_entreprise(request, pk):
    from apps_entreprise.models import Entreprise
    from apps_entreprise.forms import MotifForm
 
    entreprise = get_object_or_404(Entreprise, pk=pk)
    if request.method == 'POST':
        form = MotifForm(request.POST)
        if form.is_valid():
            entreprise.suspendre(request.user, form.cleaned_data['motif'])
            messages.success(request, f"Entreprise « {entreprise.raison_sociale} » suspendue.")
        else:
            messages.error(request, "Le motif de suspension est obligatoire.")
    return redirect('apps_entreprise:admin_detail_entreprise', pk=pk)
 
 
@login_required
def admin_recalculer_score(request, pk):
    from apps_entreprise.models import Entreprise
 
    entreprise = get_object_or_404(Entreprise, pk=pk)
    if request.method == 'POST':
        entreprise.recalculer_score()
        messages.success(request, f"Score de fiabilité recalculé : {entreprise.score_fiabilite}.")
    return redirect('apps_entreprise:admin_detail_entreprise', pk=pk)
 
 
@login_required
def admin_verifier_document(request, pk):
    """Marque un document comme vérifié par l'admin courant."""
    from apps_entreprise.models import DocumentEntreprise
    from django.utils import timezone
 
    document = get_object_or_404(DocumentEntreprise, pk=pk)
    if request.method == 'POST':
        document.verifie = True
        document.verifie_par = request.user
        document.date_verification = timezone.now()
        document.save(update_fields=['verifie', 'verifie_par', 'date_verification'])
        messages.success(request, "Document marqué comme vérifié.")
    return redirect('apps_entreprise:admin_detail_entreprise', pk=document.entreprise_id)
 
 
@login_required
def admin_creer_frais_gardiennage(request, pk):
    """Crée une amende de gardiennage pour une entreprise (typiquement désactivée pour inactivité)."""
    from apps_entreprise.models import Entreprise, FraisGardiennage
    from apps_entreprise.forms import FraisGardiennageForm
 
    entreprise = get_object_or_404(Entreprise, pk=pk)
    if request.method == 'POST':
        form = FraisGardiennageForm(request.POST)
        if form.is_valid():
            FraisGardiennage.objects.create(
                entreprise=entreprise,
                montant_du=form.cleaned_data['montant_du'],
                raison=form.cleaned_data.get('raison', ''),
            )
            messages.success(request, "Frais de gardiennage créés.")
        else:
            messages.error(request, "Merci de corriger les erreurs du formulaire.")
    return redirect('apps_entreprise:admin_detail_entreprise', pk=pk)
 
 
@login_required
def admin_confirmer_paiement_gardiennage(request, pk):
    """
    Confirme la réception du paiement de gardiennage et réactive
    l'entreprise (Entreprise.reactiver_via_gardiennage). C'est le SEUL
    chemin qui déclenche cette réactivation — jamais côté entreprise,
    puisque la méthode exige explicitement un admin_user.
    """
    from apps_entreprise.models import FraisGardiennage
    from apps_entreprise.forms import ConfirmerPaiementGardiennageForm
 
    frais = get_object_or_404(FraisGardiennage, pk=pk)
    if request.method == 'POST':
        form = ConfirmerPaiementGardiennageForm(request.POST)
        if form.is_valid():
            try:
                frais.entreprise.reactiver_via_gardiennage(request.user, form.cleaned_data['montant_paye'])
                messages.success(request, f"Paiement confirmé — « {frais.entreprise.raison_sociale} » réactivée.")
            except ValueError as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "Merci d'indiquer le montant reçu.")
    return redirect('apps_entreprise:admin_detail_entreprise', pk=frais.entreprise_id)



@login_required
def admin_entreprises_en_attente(request):
    """
    File d'attente des entreprises à valider.
 
    Différence avec admin_liste_entreprises() : celle-ci sert à
    consulter/rechercher TOUTES les entreprises (avec filtres) ; celle-ci
    est pensée pour un TRAITEMENT RAPIDE en file — uniquement les
    entreprises EN_ATTENTE, triées de la plus ancienne à la plus récente
    (FIFO, pour traiter en premier celles qui attendent depuis le plus
    longtemps), avec les actions Valider/Refuser directement disponibles
    depuis la ligne plutôt que d'obliger à ouvrir chaque fiche complète.
 
    Réutilise volontairement admin_valider_entreprise() et
    admin_refuser_entreprise() déjà existantes pour le traitement des
    actions (pas de duplication de logique) — après action, l'admin est
    redirigé vers la fiche détail de l'entreprise traitée (comportement
    inchangé de ces deux vues), pas ramené sur cette file d'attente.
    """
    from apps_entreprise.models import Entreprise
    from apps_entreprise.forms import MotifForm
 
    entreprises = Entreprise.objects.filter(
        statut=Entreprise.Statut.EN_ATTENTE
    ).select_related('utilisateur', 'ville_principale').order_by('date_creation')
 
    return render(request, 'apps_entreprise/admin_entreprises_attente.html', {
        'entreprises': entreprises,
        'motif_form': MotifForm(),
    })

# ═══════════════════════════════════════════════════════════════════════
# ENTREPÔTS (ADMIN) — gestion des entrepôts et de l'affectation des
# entreprises à ces entrepôts. C'est TOUJOURS la plateforme qui affecte
# (jamais l'entreprise elle-même), cf. docstring de AffectationEntrepot.
# ═══════════════════════════════════════════════════════════════════════

@login_required
def admin_liste_entrepots(request):
    """Liste des entrepôts, avec filtre par ville et recherche texte."""
    from django.db.models import Count, Q
    from apps_entreprise.models import Entrepot
    from apps_core.models import Ville

    entrepots = Entrepot.objects.select_related('ville', 'zone', 'responsable').annotate(
        nb_entreprises=Count('affectationentrepot', filter=Q(affectationentrepot__est_active=True))
    ).order_by('ville__nom', 'nom')

    ville_id = request.GET.get('ville')
    if ville_id:
        entrepots = entrepots.filter(ville_id=ville_id)

    recherche = request.GET.get('q')
    if recherche:
        entrepots = entrepots.filter(Q(nom__icontains=recherche) | Q(code__icontains=recherche))

    return render(request, 'apps_entreprise/admin_liste_entrepots.html', {
        'entrepots': entrepots,
        'villes': Ville.objects.filter(est_active=True).order_by('nom'),
        'filtre_ville': ville_id or '',
        'recherche': recherche or '',
    })


@login_required
def admin_creer_entrepot(request):
    from apps_entreprise.forms import EntrepotForm

    if request.method == 'POST':
        form = EntrepotForm(request.POST)
        if form.is_valid():
            entrepot = form.save()
            messages.success(request, f"Entrepôt « {entrepot.nom} » créé.")
            return redirect('apps_entreprise:admin_detail_entrepot', pk=entrepot.pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = EntrepotForm()

    return render(request, 'apps_entreprise/admin_creer_entrepot.html', {'form': form})


@login_required
def admin_detail_entrepot(request, pk):
    """
    Fiche d'un entrepôt : informations + entreprises affectées, avec un
    formulaire pour en affecter une nouvelle directement depuis cette page.
    """
    from apps_entreprise.models import Entrepot, AffectationEntrepot
    from apps_entreprise.forms import AffectationEntrepotForm

    entrepot = get_object_or_404(Entrepot, pk=pk)
    affectations = AffectationEntrepot.objects.filter(entrepot=entrepot).select_related(
        'entreprise', 'affecte_par'
    ).order_by('-est_active', '-date_affectation')

    if request.method == 'POST':
        form = AffectationEntrepotForm(request.POST, entrepot=entrepot)
        if form.is_valid():
            AffectationEntrepot.objects.create(
                entreprise=form.cleaned_data['entreprise'],
                entrepot=entrepot,
                affecte_par=request.user,
            )
            messages.success(request, "Entreprise affectée à cet entrepôt.")
            return redirect('apps_entreprise:admin_detail_entrepot', pk=pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = AffectationEntrepotForm(entrepot=entrepot)

    return render(request, 'apps_entreprise/admin_detail_entrepot.html', {
        'entrepot': entrepot, 'affectations': affectations, 'form': form,
    })


@login_required
def admin_modifier_entrepot(request, pk):
    from apps_entreprise.models import Entrepot
    from apps_entreprise.forms import EntrepotForm

    entrepot = get_object_or_404(Entrepot, pk=pk)
    if request.method == 'POST':
        form = EntrepotForm(request.POST, instance=entrepot)
        if form.is_valid():
            form.save()
            messages.success(request, f"Entrepôt « {entrepot.nom} » mis à jour.")
            return redirect('apps_entreprise:admin_detail_entrepot', pk=pk)
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = EntrepotForm(instance=entrepot)

    return render(request, 'apps_entreprise/admin_modifier_entrepot.html', {'form': form, 'entrepot': entrepot})


@login_required
def admin_toggle_actif_entrepot(request, pk):
    """Active/désactive un entrepôt en un clic (bouton, pas de formulaire)."""
    from apps_entreprise.models import Entrepot

    entrepot = get_object_or_404(Entrepot, pk=pk)
    if request.method == 'POST':
        entrepot.est_actif = not entrepot.est_actif
        entrepot.save(update_fields=['est_actif'])
        etat = 'activé' if entrepot.est_actif else 'désactivé'
        messages.success(request, f"Entrepôt « {entrepot.nom} » {etat}.")
    return redirect('apps_entreprise:admin_detail_entrepot', pk=pk)


@login_required
def admin_supprimer_entrepot(request, pk):
    """
    Supprime un entrepôt — POST uniquement. StockEntrepot.entrepot est en
    on_delete=PROTECT (apps_catalogue) : on intercepte ProtectedError
    plutôt que de laisser une 500 s'afficher dès qu'un stock existe
    encore dans cet entrepôt, et on oriente vers la désactivation.
    """
    from django.db.models import ProtectedError
    from apps_entreprise.models import Entrepot

    entrepot = get_object_or_404(Entrepot, pk=pk)
    if request.method != 'POST':
        return redirect('apps_entreprise:admin_detail_entrepot', pk=pk)

    nom = entrepot.nom
    try:
        entrepot.delete()
        messages.success(request, f"Entrepôt « {nom} » supprimé.")
        return redirect('apps_entreprise:admin_liste_entrepots')
    except ProtectedError:
        messages.error(
            request,
            f"Impossible de supprimer « {nom} » : des stocks ou mouvements y sont encore rattachés. "
            f"Désactivez-le plutôt depuis le bouton dédié."
        )
        return redirect('apps_entreprise:admin_detail_entrepot', pk=pk)


@login_required
def admin_toggle_affectation(request, pk):
    """
    Active/désactive une affectation Entreprise↔Entrepôt. Volontairement
    un TOGGLE et non une suppression : unique_together = [['entreprise',
    'entrepot']] empêcherait de recréer la ligne plus tard si on la
    supprimait — désactiver puis réactiver la même ligne est plus sûr et
    garde l'historique (date_affectation, affecte_par) intact.
    """
    from apps_entreprise.models import AffectationEntrepot

    affectation = get_object_or_404(AffectationEntrepot, pk=pk)
    if request.method == 'POST':
        affectation.est_active = not affectation.est_active
        affectation.save(update_fields=['est_active'])
        etat = 'réactivée' if affectation.est_active else 'désactivée'
        messages.success(request, f"Affectation { etat }.")
    return redirect('apps_entreprise:admin_detail_entrepot', pk=affectation.entrepot_id)


# ═══════════════════════════════════════════════════════════════════════
# ENTREPÔTS (ESPACE ENTREPRISE) — lecture seule : une entreprise consulte
# les entrepôts auxquels elle a été affectée, mais ne peut jamais
# s'auto-affecter (seule la plateforme le fait, cf. admin_detail_entrepot).
# ═══════════════════════════════════════════════════════════════════════

@login_required
def mes_entrepots(request):
    from apps_entreprise.models import AffectationEntrepot

    entreprise = getattr(request.user, 'entreprise', None)
    if entreprise is None:
        messages.error(request, "Aucune entreprise associée à ce compte.")
        return redirect('apps_entreprise:dashboard')

    affectations = AffectationEntrepot.objects.filter(
        entreprise=entreprise, est_active=True
    ).select_related('entrepot', 'entrepot__ville').order_by('entrepot__nom')

    return render(request, 'apps_entreprise/mes_entrepots.html', {
        'affectations': affectations, 'entreprise': entreprise,
    })


@login_required
def zones_livraison(request):
    """
    Vue LECTURE SEULE pour l'espace entreprise : liste les villes/zones
    actives avec, pour chacune, le tarif calculé pour chaque type de
    véhicule (via Zone.get_prix_pour_vehicule()) ET la liste de ses
    quartiers actifs — permet à une entreprise de savoir à l'avance
    combien coûtera une livraison selon la zone de destination et le
    véhicule requis, ET quels quartiers précis sont couverts par
    chaque zone, sans passer par l'admin.
 
    Le Prefetch imbriqué (zones → quartiers) évite le N+1 classique :
    sans lui, charger les quartiers de chaque zone déclencherait une
    requête supplémentaire par zone affichée.
    """
    from django.db.models import Prefetch
    from apps_core.models import Ville, Zone, Quartier
    from apps_core.choices import TypeVehicule
 
    villes = Ville.objects.filter(est_active=True).select_related('pays').prefetch_related(
        Prefetch(
            'zones',
            queryset=Zone.objects.filter(est_active=True).order_by('nom').prefetch_related(
                Prefetch('quartiers', queryset=Quartier.objects.filter(est_actif=True).order_by('nom'))
            )
        )
    ).order_by('pays__nom', 'nom')
 
    vehicules = list(TypeVehicule.choices)  # [(valeur, libellé), ...] — ordre = ordre d'affichage des colonnes
 
    villes_data = []
    for ville in villes:
        zones_data = []
        for zone in ville.zones.all():
            tarifs = [zone.get_prix_pour_vehicule(valeur) for valeur, _label in vehicules]
            zones_data.append({'zone': zone, 'tarifs': tarifs, 'quartiers': zone.quartiers.all()})
        if zones_data:
            villes_data.append({'ville': ville, 'zones': zones_data})
 
    return render(request, 'apps_entreprise/zones_livraison.html', {
        'villes_data': villes_data,
        'vehicules_labels': [label for _valeur, label in vehicules],
    })
 
 