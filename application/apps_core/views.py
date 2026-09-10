from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
 
from apps_core.forms import (
    InscriptionForm, ConnexionForm, DemandeReinitialisationForm,
    NouveauMotDePasseForm, VerificationOtpForm,
)
from apps_core.models import Utilisateur

# Create your views here.



def accueil(request):
    """
    Page d'accueil publique de SwiftDrop.

    Présente la plateforme aux visiteurs (entreprises, livreurs, clients)
    et les oriente vers la création de compte ou la connexion. Les
    compteurs affichés dans la section "chiffres clés" sont calculés
    depuis la base ; si les modèles d'autres apps ne sont pas encore
    migrés/disponibles, on retombe silencieusement sur des zéros plutôt
    que de faire planter la page d'accueil.
    """
    contexte = {
        'nb_entreprises': 0,
        'nb_livreurs': 0,
        'nb_livraisons': 0,
        'nb_villes': 0,
    }
    try:
        from apps_core.models import Ville
        from apps_entreprise.models import Entreprise
        from apps_livreur.models import Livreur
        from apps_livraison.models import Livraison

        contexte['nb_entreprises'] = Entreprise.objects.filter(statut=Entreprise.Statut.VALIDE).count()
        contexte['nb_livreurs'] = Livreur.objects.filter(
            statut__in=[Livreur.Statut.ACTIF, Livreur.Statut.EN_MISSION]
        ).count()
        contexte['nb_livraisons'] = Livraison.objects.filter(statut=Livraison.Statut.LIVREE).count()
        contexte['nb_villes'] = Ville.objects.filter(est_active=True).count()
    except Exception:
        # Base pas encore migrée, app pas encore installée, etc. — la
        # page d'accueil doit rester consultable même sans données.
        pass

    return render(request, 'apps_core/accueil.html', contexte)


def conditions_utilisation(request):
    """
    Page publique des conditions générales d'utilisation (CGU) de SwiftDrop.
 
    Contenu statique — pas de requête base nécessaire. La date de
    dernière mise à jour est centralisée ici pour être facile à changer
    à chaque révision du texte.
    """
    contexte = {
        'date_maj': 'Août 2026',
    }
    return render(request, 'apps_core/conditions_utilisation.html', contexte)


def politique_confidentialite(request):
    """
    Page publique de la politique de confidentialité de SwiftDrop.
 
    Contenu statique — pas de requête base nécessaire. Même logique que
    conditions_utilisation() : la date de dernière mise à jour est
    centralisée ici pour être facile à changer à chaque révision.
    """
    contexte = {
        'date_maj': 'Août 2026',
    }
    return render(request, 'apps_core/politique_confidentialite.html', contexte)


def contact(request):
    """
    Page publique de contact, avec formulaire (nom, email, téléphone,
    sujet, message).
 
    NB : l'envoi réel (email à l'équipe support, création d'une entrée
    en base, notification Slack…) n'est pas branché ici — voir le
    commentaire dans le bloc POST. Le formulaire suit le pattern
    Post/Redirect/Get pour éviter tout renvoi accidentel au rechargement.
    """
    from django.contrib import messages
    from django.shortcuts import redirect
    import logging
 
    from apps_core.forms import ContactForm
 
    logger = logging.getLogger('apps_core')
 
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # TODO : brancher ici l'envoi réel du message, par exemple :
            #   - envoi d'un email à l'équipe support (django.core.mail)
            #   - création d'une entrée ContactMessage en base pour suivi
            #   - notification interne (Slack, apps_notification, etc.)
            logger.info(
                "Nouveau message de contact : %s <%s> — sujet=%s",
                form.cleaned_data['nom'], form.cleaned_data['email'], form.cleaned_data['sujet'],
            )
            messages.success(
                request,
                "Merci, votre message a bien été envoyé ! Notre équipe vous répondra dans les plus brefs délais."
            )
            return redirect('contact')
    else:
        form = ContactForm()
 
    return render(request, 'apps_core/contact.html', {'form': form})


def dashboard_admin(request):
    """
    Tableau de bord administrateur.
 
    TODO : protéger avec @login_required + vérification request.user.est_admin
    une fois le système d'authentification branché.
 
    Comme pour accueil(), les requêtes sont protégées par un try/except
    pour que le template reste affichable même si une app n'est pas
    encore migrée en base.
    """
    contexte = {
        'nb_entreprises_attente': 0,
        'nb_livraisons_cours': 0,
        'nb_livreurs_actifs': 0,
        'nb_lots_a_envoyer': 0,
        'entreprises_a_valider': [],
        'livraisons_recentes': [],
        'entreprises_inactives': [],
    }
    try:
        from apps_entreprise.models import Entreprise
        from apps_livreur.models import Livreur
        from apps_livraison.models import Livraison
        from apps_transaction.models import LotPaiementEntreprise
        from apps_core.choices import StatutLotPaiement
 
        contexte['nb_entreprises_attente'] = Entreprise.objects.filter(
            statut=Entreprise.Statut.EN_ATTENTE).count()
        contexte['nb_livraisons_cours'] = Livraison.objects.filter(
            statut=Livraison.Statut.EN_COURS).count()
        contexte['nb_livreurs_actifs'] = Livreur.objects.filter(
            statut__in=[Livreur.Statut.ACTIF, Livreur.Statut.EN_MISSION]).count()
        contexte['nb_lots_a_envoyer'] = LotPaiementEntreprise.objects.filter(
            statut=StatutLotPaiement.PRET_A_ENVOYER).count()
 
        contexte['entreprises_a_valider'] = Entreprise.objects.filter(
            statut=Entreprise.Statut.EN_ATTENTE).order_by('-date_creation')[:5]
        contexte['livraisons_recentes'] = Livraison.objects.select_related(
            'entreprise').order_by('-date_creation')[:8]
        contexte['entreprises_inactives'] = Entreprise.objects.filter(
            statut=Entreprise.Statut.VALIDE,
            derniere_activite_livraison__isnull=False,
        ).order_by('derniere_activite_livraison')[:5]
    except Exception:
        pass
 
    return render(request, 'apps_core/dashboard_admin.html', contexte)


def dashboard_client(request):
    """
    Tableau de bord du client direct (particulier avec compte).
 
    TODO : protéger avec @login_required + filtrer sur request.user une
    fois l'authentification branchée ; ici on illustre la structure avec
    un filtrage défensif (retombe sur une liste vide si non connecté).
    """
    contexte = {
        'nb_colis_cours': 0,
        'nb_colis_livres': 0,
        'total_depense': 0,
        'envois_recents': [],
    }
    try:
        from apps_livraison.models import LivraisonDirecte
        from django.db.models import Sum
 
        if request.user.is_authenticated:
            envois = LivraisonDirecte.objects.filter(client=request.user)
            contexte['nb_colis_cours'] = envois.filter(
                statut__in=[LivraisonDirecte.Statut.EN_ATTENTE, LivraisonDirecte.Statut.CONFIRMEE,
                            LivraisonDirecte.Statut.EN_COURS]).count()
            contexte['nb_colis_livres'] = envois.filter(statut=LivraisonDirecte.Statut.LIVREE).count()
            contexte['total_depense'] = envois.filter(
                statut=LivraisonDirecte.Statut.LIVREE).aggregate(t=Sum('prix_total'))['t'] or 0
            contexte['envois_recents'] = envois.order_by('-date_creation')[:8]
    except Exception:
        pass
 
    return render(request, 'apps_core/dashboard_client.html', contexte)




# ═══════════════════════════════════════════════════════════════════════
# AUTHENTIFICATION
# ═══════════════════════════════════════════════════════════════════════

  
def inscription(request):
    """
    Inscription d'un compte Client (auto-service, sans validation admin).
    Les comptes Entreprise / Livreur se créent via des formulaires dédiés
    dans apps_entreprise / apps_livreur (ils créent en plus le profil
    métier lié et restent soumis à validation admin).
 
    NOTE OTP — comme demandé : un code de vérification est généré à la
    création (le flux reste prêt pour le jour où l'envoi SMS/email sera
    opérationnel en production, cf. apps_notification/signals.py), mais
    SA VÉRIFICATION N'EST PAS EXIGÉE pour l'instant puisqu'aucun message
    ne peut encore être réellement envoyé. Le compte est donc actif et
    l'utilisateur est connecté immédiatement après inscription.
 
    Pour réactiver le blocage plus tard : remplacer le login() direct par
    une redirection vers 'apps_core:verifier_otp', et conditionner l'accès
    aux vues protégées à user.telephone_verifie (ou email_verifie).
    """
    if request.user.is_authenticated:
        return redirect('apps_core:accueil')
 
    if request.method == 'POST':
        form = InscriptionForm(request.POST)
        if form.is_valid():
            user = form.save(role=Utilisateur.Role.CLIENT)
 
            # Génère un OTP pour garder le flux prêt — l'envoi réel est
            # simulé (loggé) tant qu'aucun provider SMS/email n'est
            # branché. Voir apps_notification/signals.py.
            user.generer_otp()
 
            login(request, user)
            messages.success(request, f"Bienvenue {user.nom} ! Votre compte a été créé avec succès.")
            return redirect('apps_core:accueil')
    else:
        form = InscriptionForm()
 
    return render(request, 'apps_core/inscription.html', {'form': form})



def connexion(request):
    """
    Connexion par email + mot de passe (USERNAME_FIELD = 'email' sur
    Utilisateur, donc authenticate() reçoit bien l'email dans "username").
    Bloque temporairement le compte après 5 tentatives échouées, en
    s'appuyant sur Utilisateur.tentatives_connexion / compte_bloque.
    """
    if request.user.is_authenticated:
        return redirect('apps_core:accueil')
 
    if request.method == 'POST':
        form = ConnexionForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].lower().strip()
            mot_de_passe = form.cleaned_data['mot_de_passe']
            user = authenticate(request, username=email, password=mot_de_passe)
 
            if user is not None:
                if not user.est_actif:
                    messages.error(request, "Ce compte est désactivé. Contactez l'administration.")
                elif user.compte_bloque:
                    messages.error(request, "Ce compte est temporairement bloqué suite à plusieurs tentatives échouées.")
                else:
                    login(request, user)
                    user.enregistrer_connexion(ip=request.META.get('REMOTE_ADDR'))
                    return _rediriger_selon_role(user)
            else:
                _enregistrer_tentative_echouee(email)
                messages.error(request, "Email ou mot de passe incorrect.")
    else:
        form = ConnexionForm()
 
    return render(request, 'apps_core/connexion.html', {'form': form})



def _rediriger_selon_role(user):
    """Redirige chaque rôle vers son tableau de bord dédié après connexion."""
    if user.est_admin:
        return redirect('apps_core:dashboard_admin')
    if user.est_entreprise_user:
        return redirect('apps_entreprise:dashboard')
    if user.est_livreur_user:
        return redirect('apps_livreur:dashboard_livreur')
    return redirect('apps_core:dashboard_client')
 
 
def _enregistrer_tentative_echouee(email):
    """Incrémente le compteur d'échecs et bloque 15 min après 5 tentatives."""
    try:
        user = Utilisateur.objects.get(email=email)
        user.tentatives_connexion += 1
        if user.tentatives_connexion >= 5:
            user.compte_bloque_jusqu_au = timezone.now() + timezone.timedelta(minutes=15)
        user.save(update_fields=['tentatives_connexion', 'compte_bloque_jusqu_au'])
    except Utilisateur.DoesNotExist:
        # On ne révèle jamais si l'email existe ou non.
        pass
 
 
@login_required
def deconnexion(request):
    logout(request)
    messages.info(request, "Vous avez été déconnecté.")
    return redirect('apps_core:accueil')
 
 
@login_required
def verifier_otp(request):
    """
    Vérification du code OTP — actuellement OPTIONNELLE (voir note dans
    inscription() ci-dessus). La vue reste pleinement fonctionnelle pour
    le jour où l'envoi réel de SMS/email sera activé et où ce contrôle
    redeviendra bloquant dans le parcours d'inscription.
    """
    if request.method == 'POST':
        form = VerificationOtpForm(request.POST)
        if form.is_valid():
            if request.user.otp_valide(form.cleaned_data['code']):
                request.user.telephone_verifie = True
                request.user.code_otp = ''
                request.user.save(update_fields=['telephone_verifie', 'code_otp'])
                messages.success(request, "Votre numéro a été vérifié avec succès.")
                return redirect('apps_core:accueil')
            messages.error(request, "Code invalide ou expiré.")
    else:
        form = VerificationOtpForm()
 
    return render(request, 'apps_core/verifier_otp.html', {'form': form})
 
 
@login_required
def renvoyer_otp(request):
    request.user.generer_otp()
    messages.info(request, "Un nouveau code a été généré.")
    return redirect('apps_core:verifier_otp')
 
 
def mot_de_passe_oublie(request):
    if request.method == 'POST':
        form = DemandeReinitialisationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].lower().strip()
            try:
                user = Utilisateur.objects.get(email=email)
                user.generer_token_reinit_mdp()
            except Utilisateur.DoesNotExist:
                pass
            # Message volontairement identique que le compte existe ou
            # non, pour ne jamais révéler quels emails sont enregistrés.
            messages.success(
                request,
                "Si un compte existe avec cet email, un lien de réinitialisation a été envoyé."
            )
            return redirect('apps_core:connexion')
    else:
        form = DemandeReinitialisationForm()
 
    return render(request, 'apps_core/mot_de_passe_oublie.html', {'form': form})


def reinitialiser_mot_de_passe(request, token):
    try:
        user = Utilisateur.objects.get(token_reinit_mdp=token)
    except Utilisateur.DoesNotExist:
        user = None
 
    if user is None or not user.token_reinit_expiration or timezone.now() > user.token_reinit_expiration:
        messages.error(request, "Ce lien de réinitialisation est invalide ou a expiré.")
        return redirect('apps_core:mot_de_passe_oublie')
 
    if request.method == 'POST':
        form = NouveauMotDePasseForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['mot_de_passe'])
            user.token_reinit_mdp = ''
            user.token_reinit_expiration = None
            user.save(update_fields=['password', 'token_reinit_mdp', 'token_reinit_expiration'])
            messages.success(request, "Votre mot de passe a été mis à jour. Vous pouvez vous connecter.")
            return redirect('apps_core:connexion')
    else:
        form = NouveauMotDePasseForm()
 
    return render(request, 'apps_core/reinitialiser_mot_de_passe.html', {'form': form})

@login_required
def mon_profil(request):
    """
    Modification des informations de base du compte connecté (tous
    rôles confondus). Ne touche jamais au mot de passe — cf. parametres()
    pour ça — ni aux champs de vérification (compte_bloque, otp, etc.)
    qui restent gérés par le système.
    """
    from apps_core.forms import ModifierProfilForm

    if request.method == 'POST':
        form = ModifierProfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour.")
            return redirect('apps_core:mon_profil')
    else:
        form = ModifierProfilForm(instance=request.user)

    return render(request, 'apps_core/mon_profil.html', {'form': form})


@login_required
def parametres(request):
    """
    Changement de mot de passe pour un utilisateur déjà connecté
    (distinct du flux mot_de_passe_oublie, qui lui ne nécessite pas
    d'être connecté et repose sur un token par email).
    """
    from django.contrib.auth import update_session_auth_hash
    from apps_core.forms import ChangerMotDePasseForm

    if request.method == 'POST':
        form = ChangerMotDePasseForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # évite la déconnexion après changement
            messages.success(request, "Votre mot de passe a été modifié avec succès.")
            return redirect('apps_core:parametres')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ChangerMotDePasseForm(request.user)

    return render(request, 'apps_core/parametres.html', {'form': form})



def configuration_geographie(request):
    """
    Page d'administration : configuration hiérarchique Pays → Ville →
    Zone → Quartier, chaque niveau permettant d'ajouter directement le
    niveau enfant depuis sa propre carte (ex : "+ Ville" depuis un Pays,
    avec le pays déjà présélectionné dans le formulaire modal).
 
    Un seul POST gère les 4 formulaires, distingués par le champ caché
    `action` — évite de dupliquer 4 vues quasi identiques. Chaque
    formulaire utilise un `prefix` distinct (pays/ville/zone/quartier)
    car les 4 modèles partagent un champ `nom` : sans prefix, Django
    générerait un id="id_nom" identique dans les 4 modals présents
    simultanément dans le DOM, ce qui casse le focus/la saisie clavier.
 
    En cas d'erreur de validation, on ne redirige pas : on renvoie la
    page avec le formulaire fautif lié (donc ses erreurs affichées) et
    un indicateur `modal_ouvert` pour que le template rouvre
    automatiquement le bon modal via JS (bootstrap.Modal().show()) —
    jamais via une classe CSS statique, qui laisserait aria-hidden en
    place et rendrait les champs impossibles à remplir.
    """
    from django.contrib import messages
    from django.shortcuts import redirect
    from django.db.models import Prefetch
 
    from apps_core.models import Pays, Ville, Zone, Quartier
    from apps_core.forms import PaysForm, VilleForm, ZoneForm, QuartierForm
 
    FORMULAIRES = {
        'ajouter_pays': (PaysForm, 'pays'),
        'ajouter_ville': (VilleForm, 'ville'),
        'ajouter_zone': (ZoneForm, 'zone'),
        'ajouter_quartier': (QuartierForm, 'quartier'),
    }
 
    pays_form = PaysForm(prefix='pays')
    ville_form = VilleForm(prefix='ville')
    zone_form = ZoneForm(prefix='zone')
    quartier_form = QuartierForm(prefix='quartier')
    modal_ouvert = None  # 'pays' | 'ville' | 'zone' | 'quartier' — voir template
 
    if request.method == 'POST':
        action = request.POST.get('action')
        entree = FORMULAIRES.get(action)
        if entree is None:
            messages.error(request, "Action de formulaire inconnue.")
            return redirect('apps_core:configuration_geographie')
 
        FormClass, prefix = entree
        form = FormClass(request.POST, prefix=prefix)
        if form.is_valid():
            objet = form.save()
            messages.success(request, {
                'ajouter_pays': f"Le pays « {objet.nom} » a été ajouté.",
                'ajouter_ville': f"La ville « {objet.nom} » a été ajoutée.",
                'ajouter_zone': f"La zone « {objet.nom} » a été ajoutée.",
                'ajouter_quartier': f"Le quartier « {objet.nom} » a été ajouté.",
            }[action])
            return redirect('apps_core:configuration_geographie')
 
        # Formulaire invalide : on le réinjecte lié (avec erreurs) à la
        # place de sa version vierge, et on note quel modal rouvrir.
        modal_ouvert = prefix
        if prefix == 'pays':
            pays_form = form
        elif prefix == 'ville':
            ville_form = form
        elif prefix == 'zone':
            zone_form = form
        elif prefix == 'quartier':
            quartier_form = form
 
    # Un seul aller-retour base grâce aux Prefetch imbriqués : sans ça,
    # afficher N pays x M villes x P zones x Q quartiers ferait exploser
    # le nombre de requêtes (N+1 à chaque niveau).
    pays_liste = Pays.objects.prefetch_related(
        Prefetch(
            'villes',
            queryset=Ville.objects.order_by('nom').prefetch_related(
                Prefetch(
                    'zones',
                    queryset=Zone.objects.order_by('nom').prefetch_related(
                        Prefetch('quartiers', queryset=Quartier.objects.order_by('nom'))
                    )
                )
            )
        )
    ).order_by('nom')
 
    contexte = {
        'pays_liste': pays_liste,
        'pays_form': pays_form,
        'ville_form': ville_form,
        'zone_form': zone_form,
        'quartier_form': quartier_form,
        'modal_ouvert': modal_ouvert,
    }
    return render(request, 'apps_core/configuration_geographie.html', contexte)


# ═══════════════════════════════════════════════════════════════════════
# GÉOGRAPHIE — complète configuration_geographie() : modification,
# activation/désactivation, suppression, tarification, coefficients véhicule
# ═══════════════════════════════════════════════════════════════════════

# Table de correspondance niveau → (Modèle, Formulaire, champ actif, libellé).
# Les 4 modèles ne nomment pas leur booléen d'activation de la même façon
# (est_actif sur Pays/Quartier, est_active sur Ville/Zone — hérité du
# modèle d'origine) : ce mapping absorbe l'incohérence une seule fois au
# lieu de la reproduire dans chaque vue.
def _niveaux_geographie():
    from apps_core.models import Pays, Ville, Zone, Quartier
    from apps_core.forms import PaysForm, VilleForm, ZoneForm, QuartierForm
    return {
        'pays':     {'model': Pays,     'form': PaysForm,     'champ_actif': 'est_actif',  'label': 'Pays'},
        'ville':    {'model': Ville,    'form': VilleForm,    'champ_actif': 'est_active', 'label': 'Ville'},
        'zone':     {'model': Zone,     'form': ZoneForm,     'champ_actif': 'est_active', 'label': 'Zone'},
        'quartier': {'model': Quartier, 'form': QuartierForm, 'champ_actif': 'est_actif',  'label': 'Quartier'},
    }


@login_required
def modifier_geographie(request, niveau, pk):
    """
    Édite un Pays / Ville / Zone / Quartier existant. Complète
    configuration_geographie(), qui ne gère que la création.

    NB : n'édite PAS le prix d'une Zone — voir modifier_tarif_zone()
    ci-dessous, qui journalise le changement dans TarifHistorique.
    """
    from django.shortcuts import get_object_or_404

    config = _niveaux_geographie().get(niveau)
    if config is None:
        messages.error(request, "Niveau géographique inconnu.")
        return redirect('apps_core:configuration_geographie')

    objet = get_object_or_404(config['model'], pk=pk)

    if request.method == 'POST':
        # Une Zone se modifie via ce formulaire pour tout SAUF le prix :
        # on fige prix_livraison à sa valeur actuelle avant validation
        # pour empêcher un contournement de modifier_tarif_zone().
        form = config['form'](request.POST, instance=objet)
        if niveau == 'zone':
            form.data = form.data.copy()
            form.data['prix_livraison'] = objet.prix_livraison

        if form.is_valid():
            form.save()
            messages.success(request, f"{config['label']} « {objet.nom} » mis(e) à jour.")
            return redirect('apps_core:configuration_geographie')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = config['form'](instance=objet)

    return render(request, 'apps_core/modifier_geographie.html', {
        'form': form, 'objet': objet, 'niveau': niveau, 'label': config['label'],
    })


@login_required
def toggle_actif_geographie(request, niveau, pk):
    """Active/désactive un Pays / Ville / Zone / Quartier en un clic (bouton, pas de formulaire)."""
    from django.shortcuts import get_object_or_404

    config = _niveaux_geographie().get(niveau)
    if config is None:
        messages.error(request, "Niveau géographique inconnu.")
        return redirect('apps_core:configuration_geographie')

    objet = get_object_or_404(config['model'], pk=pk)
    champ = config['champ_actif']
    setattr(objet, champ, not getattr(objet, champ))
    objet.save(update_fields=[champ])

    etat = 'activé(e)' if getattr(objet, champ) else 'désactivé(e)'
    messages.success(request, f"{config['label']} « {objet.nom} » {etat}.")
    return redirect('apps_core:configuration_geographie')


@login_required
def supprimer_geographie(request, niveau, pk):
    """
    Supprime un Pays / Ville / Zone / Quartier — POST uniquement (jamais
    sur un simple lien GET, pour éviter les suppressions accidentelles
    via crawler/prefetch de navigateur).

    Zone et Quartier sont protégés en cascade par des livraisons
    (apps_livraison.Livraison.zone_livraison est en on_delete=PROTECT) :
    on intercepte ProtectedError plutôt que de laisser une 500 s'afficher,
    et on oriente vers la désactivation comme alternative sûre.
    """
    from django.shortcuts import get_object_or_404
    from django.db.models import ProtectedError

    if request.method != 'POST':
        return redirect('apps_core:configuration_geographie')

    config = _niveaux_geographie().get(niveau)
    if config is None:
        messages.error(request, "Niveau géographique inconnu.")
        return redirect('apps_core:configuration_geographie')

    objet = get_object_or_404(config['model'], pk=pk)
    nom = objet.nom
    try:
        objet.delete()
        messages.success(request, f"{config['label']} « {nom} » supprimé(e).")
    except ProtectedError:
        messages.error(
            request,
            f"Impossible de supprimer « {nom} » : des livraisons ou entrepôts en dépendent encore. "
            f"Désactivez-le/la plutôt depuis le bouton dédié."
        )
    return redirect('apps_core:configuration_geographie')


@login_required
def modifier_tarif_zone(request, pk):
    """
    Change le prix de référence (véhicule moto) d'une Zone et journalise
    systématiquement le changement dans TarifHistorique — c'est le SEUL
    endroit du site où Zone.prix_livraison doit être modifié, pour que
    l'historique reste fiable à 100%.
    """
    from django.shortcuts import get_object_or_404
    from apps_core.models import Zone, TarifHistorique
    from apps_core.forms import ZoneTarifForm

    zone = get_object_or_404(Zone, pk=pk)

    if request.method == 'POST':
        form = ZoneTarifForm(request.POST)
        if form.is_valid():
            nouveau_prix = form.cleaned_data['nouveau_prix']
            raison = form.cleaned_data['raison']

            if nouveau_prix == zone.prix_livraison:
                messages.info(request, "Le nouveau prix est identique à l'actuel — aucun changement enregistré.")
                return redirect('apps_core:configuration_geographie')

            TarifHistorique.objects.create(
                zone=zone,
                ancien_prix=zone.prix_livraison,
                nouveau_prix=nouveau_prix,
                raison=raison,
                modifie_par=request.user if request.user.is_authenticated else None,
            )
            zone.prix_livraison = nouveau_prix
            zone.save(update_fields=['prix_livraison'])

            messages.success(request, f"Tarif de « {zone.nom} » mis à jour : {nouveau_prix} FCFA.")
            return redirect('apps_core:configuration_geographie')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ZoneTarifForm(initial={'nouveau_prix': zone.prix_livraison})

    return render(request, 'apps_core/modifier_tarif_zone.html', {'form': form, 'zone': zone})


@login_required
def historique_tarifs_zone(request, pk):
    """Journal des changements de prix d'une Zone — lecture seule."""
    from django.shortcuts import get_object_or_404
    from apps_core.models import Zone

    zone = get_object_or_404(Zone, pk=pk)
    historique = zone.historique_tarifs.select_related('modifie_par').order_by('-date')

    return render(request, 'apps_core/historique_tarifs_zone.html', {
        'zone': zone, 'historique': historique,
    })


@login_required
def gerer_coefficients_vehicule(request):
    """
    Liste + création/édition des majorations tarifaires par véhicule
    (CoefficientVehicule). Sans cette vue, Zone.get_prix_pour_vehicule()
    retombe silencieusement sur le prix de base moto pour tout véhicule
    non configuré — impossible à corriger sans passage par l'admin Django.
 
    type_vehicule étant unique sur le modèle, on fait un update_or_create
    plutôt qu'une création systématique : soumettre le formulaire pour un
    véhicule déjà configuré met simplement à jour son coefficient.
 
    Édition d'une ligne existante : le bouton "Modifier" du tableau pointe
    vers cette même URL avec ?vehicule=MOTO — pas besoin de JS ni de vue
    séparée, le formulaire se pré-remplit simplement avec les valeurs
    actuelles de ce véhicule s'il est déjà configuré.
    """
    from apps_core.models import CoefficientVehicule
    from apps_core.forms import CoefficientVehiculeForm
 
    if request.method == 'POST':
        form = CoefficientVehiculeForm(request.POST)
        if form.is_valid():
            CoefficientVehicule.objects.update_or_create(
                type_vehicule=form.cleaned_data['type_vehicule'],
                defaults={
                    'coefficient_multiplicateur': form.cleaned_data['coefficient_multiplicateur'],
                    'frais_fixe_supplement': form.cleaned_data['frais_fixe_supplement'],
                    'description': form.cleaned_data['description'],
                    'est_actif': form.cleaned_data['est_actif'],
                },
            )
            messages.success(request, "Coefficient véhicule enregistré.")
            return redirect('apps_core:gerer_coefficients_vehicule')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        vehicule_a_editer = request.GET.get('vehicule')
        instance = None
        if vehicule_a_editer:
            instance = CoefficientVehicule.objects.filter(type_vehicule=vehicule_a_editer).first()
        form = CoefficientVehiculeForm(
            instance=instance,
            initial={'type_vehicule': vehicule_a_editer} if vehicule_a_editer and not instance else None,
        )
 
    coefficients = CoefficientVehicule.objects.all().order_by('coefficient_multiplicateur')
    return render(request, 'apps_core/coefficients_vehicule.html', {
        'form': form, 'coefficients': coefficients,
    })



@login_required
def gerer_tarifs_intervilles(request):
    """
    Liste + création/édition des tarifs entre deux villes
    (TarifInterVille). Sans cette vue, un admin ne peut définir ces
    tarifs que via l'admin Django brut, alors qu'ils sont déjà
    exploités par TarifInterVille.calculer_prix() pour les livraisons
    directes inter-villes.
 
    (ville_depart, ville_arrivee) étant unique_together, on fait un
    update_or_create plutôt qu'une création systématique : soumettre
    le formulaire pour un couple de villes déjà configuré met
    simplement à jour son tarif.
 
    Édition d'une ligne existante : le bouton "Modifier" du tableau
    pointe vers cette même URL avec ?tarif=<pk> — le formulaire se
    pré-remplit avec les valeurs actuelles de ce tarif.
    """
    from django.shortcuts import get_object_or_404
    from apps_core.models import TarifInterVille, Ville
    from apps_core.forms import TarifInterVilleForm
 
    tarif_a_editer = None
    if request.method == 'GET' and request.GET.get('tarif'):
        tarif_a_editer = get_object_or_404(TarifInterVille, pk=request.GET['tarif'])
 
    if request.method == 'POST':
        pk_existant = request.POST.get('tarif_id') or None
        instance = get_object_or_404(TarifInterVille, pk=pk_existant) if pk_existant else None
        form = TarifInterVilleForm(request.POST, instance=instance)
        if form.is_valid():
            ville_depart = form.cleaned_data['ville_depart']
            ville_arrivee = form.cleaned_data['ville_arrivee']
            if ville_depart == ville_arrivee:
                messages.error(request, "La ville de départ et d'arrivée doivent être différentes.")
            else:
                TarifInterVille.objects.update_or_create(
                    ville_depart=ville_depart,
                    ville_arrivee=ville_arrivee,
                    defaults={
                        'prix_forfaitaire': form.cleaned_data['prix_forfaitaire'],
                        'tarif_par_km': form.cleaned_data['tarif_par_km'],
                        'distance_km_reference': form.cleaned_data['distance_km_reference'],
                        'coefficient_vehicule_applicable': form.cleaned_data['coefficient_vehicule_applicable'],
                        'est_actif': form.cleaned_data['est_actif'],
                    },
                )
                messages.success(request, f"Tarif « {ville_depart.nom} → {ville_arrivee.nom} » enregistré.")
                return redirect('apps_core:gerer_tarifs_intervilles')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = TarifInterVilleForm(instance=tarif_a_editer)
 
    tarifs = (
        TarifInterVille.objects
        .select_related('ville_depart', 'ville_arrivee')
        .order_by('ville_depart__nom', 'ville_arrivee__nom')
    )
    return render(request, 'apps_core/tarifs_intervilles.html', {
        'form': form, 'tarifs': tarifs, 'tarif_a_editer': tarif_a_editer,
    })
 
 
@login_required
def toggle_actif_tarif_intervville(request, pk):
    """Active/désactive un tarif inter-villes en un clic."""
    from django.shortcuts import get_object_or_404
    from apps_core.models import TarifInterVille
 
    tarif = get_object_or_404(TarifInterVille, pk=pk)
    tarif.est_actif = not tarif.est_actif
    tarif.save(update_fields=['est_actif'])
 
    etat = 'activé' if tarif.est_actif else 'désactivé'
    messages.success(request, f"Tarif « {tarif.ville_depart.nom} → {tarif.ville_arrivee.nom} » {etat}.")
    return redirect('apps_core:gerer_tarifs_intervilles')
 
 
@login_required
def supprimer_tarif_intervville(request, pk):
    """Supprime un tarif inter-villes — POST uniquement."""
    from django.shortcuts import get_object_or_404
    from apps_core.models import TarifInterVille
 
    if request.method != 'POST':
        return redirect('apps_core:gerer_tarifs_intervilles')
 
    tarif = get_object_or_404(TarifInterVille, pk=pk)
    nom = f"{tarif.ville_depart.nom} → {tarif.ville_arrivee.nom}"
    tarif.delete()
    messages.success(request, f"Tarif « {nom} » supprimé.")
    return redirect('apps_core:gerer_tarifs_intervilles')




@login_required
def gerer_parametres_systeme(request):
    """
    Liste + création/édition des paramètres système (ParametreSysteme).
    Même pattern que gerer_tarifs_intervilles : formulaire et tableau sur
    la même page, édition d'une ligne existante via ?param=<pk> en GET
    qui pré-remplit le formulaire, hidden input param_id en POST pour
    distinguer une mise à jour d'une création.
 
    cle étant unique sur le modèle, la création d'un paramètre avec une
    clé déjà existante déclenche naturellement une erreur de validation
    Django plutôt qu'un update_or_create silencieux : contrairement aux
    coefficients véhicule ou aux tarifs inter-villes, ici on veut que
    l'admin voie explicitement qu'il modifie un paramètre existant (via
    le bouton "Modifier"), pas qu'il l'écrase par inadvertance en
    retapant la même clé dans le formulaire de création.
    """
    from django.shortcuts import get_object_or_404
    from apps_core.models import ParametreSysteme
    from apps_core.forms import ParametreSystemeForm
 
    parametre_a_editer = None
    if request.method == 'GET' and request.GET.get('param'):
        parametre_a_editer = get_object_or_404(ParametreSysteme, pk=request.GET['param'])
 
    if request.method == 'POST':
        pk_existant = request.POST.get('param_id') or None
        instance = get_object_or_404(ParametreSysteme, pk=pk_existant) if pk_existant else None
        form = ParametreSystemeForm(request.POST, instance=instance)
        if form.is_valid():
            parametre = form.save(commit=False)
            parametre.modifie_par = request.user if request.user.is_authenticated else None
            parametre.save()
            verbe = 'mis à jour' if pk_existant else 'créé'
            messages.success(request, f"Paramètre « {parametre.cle} » {verbe}.")
            return redirect('apps_core:gerer_parametres_systeme')
        messages.error(request, "Merci de corriger les erreurs du formulaire.")
    else:
        form = ParametreSystemeForm(instance=parametre_a_editer)
 
    parametres = ParametreSysteme.objects.select_related('modifie_par').order_by('cle')
    return render(request, 'apps_core/parametres_systeme.html', {
        'form': form, 'parametres': parametres, 'parametre_a_editer': parametre_a_editer,
    })
 
 
@login_required
def supprimer_parametre_systeme(request, pk):
    """
    Supprime un paramètre système — POST uniquement.
 
    Attention : la suppression d'un paramètre encore lu quelque part via
    ParametreSysteme.get(cle, defaut=...) ne casse rien immédiatement
    (le code retombe sur sa valeur par défaut), mais un audit rapide du
    code avant suppression reste préférable pour éviter un comportement
    métier silencieusement différent de ce que l'admin croit configurer.
    """
    from django.shortcuts import get_object_or_404
    from apps_core.models import ParametreSysteme
 
    if request.method != 'POST':
        return redirect('apps_core:gerer_parametres_systeme')
 
    parametre = get_object_or_404(ParametreSysteme, pk=pk)
    cle = parametre.cle
    parametre.delete()
    messages.success(request, f"Paramètre « {cle} » supprimé.")
    return redirect('apps_core:gerer_parametres_systeme')
 

 
 