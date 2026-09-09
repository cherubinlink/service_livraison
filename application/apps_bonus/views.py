from django.contrib import messages as django_messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from .forms import TypeBonusForm, BonusEntrepriseForm, RechercheBonusForm
from .models import TypeBonus, BonusEntreprise


def est_admin(user):
    return user.is_authenticated and getattr(user, 'est_admin', False)


class AdminRequisMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Réserve les vues de gestion des bonus aux administrateurs."""

    def test_func(self):
        return est_admin(self.request.user)

    def handle_no_permission(self):
        # Sans ce override, un utilisateur connecté mais non-admin reçoit
        # un 403 brut de Django. Ici on redirige avec un message clair.
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()

        django_messages.error(self.request, "Accès réservé aux administrateurs.")
        if getattr(self.request.user, 'est_entreprise_user', False):
            return redirect('apps_entreprise:dashboard')
        return redirect('apps_core:dashboard_admin')  # ou une page d'accueil générique


def get_entreprise_utilisateur(user):
    """
    Récupère l'Entreprise liée à l'utilisateur connecté.

    ⚠️ À adapter selon le champ réel de liaison sur ton modèle Entreprise.
    On suppose ici une relation (FK ou OneToOne) accessible via
    `user.entreprise` — c'est-à-dire un related_name='entreprise' (ou le
    related_name par défaut d'un OneToOneField vers Utilisateur). Si ton
    champ s'appelle autrement (ex: `entreprise_set.first()`, `gerant`,
    `compte_entreprise`...), remplace la ligne ci-dessous en conséquence.
    """
    return getattr(user, 'entreprise', None)


class EntrepriseBonusRequisMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Réserve l'accès aux vues "mes bonus" aux utilisateurs de type ENTREPRISE
    qui ont au moins un bonus attribué. Tant qu'aucun bonus n'a été
    attribué, l'accès à la liste/au détail est refusé.
    """

    message_pas_de_bonus = "Vous n'avez pas encore de bonus. Revenez ici une fois qu'un bonus vous aura été attribué."
    message_pas_entreprise = "Cette page est réservée aux comptes entreprise."

    def test_func(self):
        user = self.request.user
        if not getattr(user, 'est_entreprise_user', False):
            self._raison_refus = self.message_pas_entreprise
            return False

        entreprise = get_entreprise_utilisateur(user)
        if entreprise is None:
            self._raison_refus = self.message_pas_entreprise
            return False

        self.entreprise = entreprise

        if not BonusEntreprise.objects.filter(entreprise=entreprise).exists():
            self._raison_refus = self.message_pas_de_bonus
            return False

        return True

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()

        django_messages.info(self.request, getattr(self, '_raison_refus', self.message_pas_de_bonus))
        return redirect('apps_entreprise:dashboard')


def _actualiser_statut(bonus):
    """
    Recalcule le statut d'un bonus en fonction de la date du jour et du quota,
    sans écraser un ANNULE manuel. Retourne True si une sauvegarde a eu lieu.
    """
    if bonus.statut in (BonusEntreprise.Statut.ANNULE,):
        return False

    today = timezone.localdate()
    nouveau_statut = bonus.statut

    if today > bonus.date_expiration:
        nouveau_statut = BonusEntreprise.Statut.EXPIRE
    elif bonus.nb_utilisations_max and bonus.nb_utilisations_actuelles >= bonus.nb_utilisations_max:
        nouveau_statut = BonusEntreprise.Statut.UTILISE
    elif bonus.date_debut <= today <= bonus.date_expiration:
        nouveau_statut = BonusEntreprise.Statut.ACTIF

    if nouveau_statut != bonus.statut:
        bonus.statut = nouveau_statut
        bonus.save(update_fields=['statut'])
        return True
    return False


# ─────────────────────────────────────────────────────────
# Types de bonus (catalogue)
# ─────────────────────────────────────────────────────────

class TypeBonusListView(AdminRequisMixin, ListView):
    model = TypeBonus
    template_name = 'apps_bonus/type_bonus_liste.html'
    context_object_name = 'types_bonus'
    paginate_by = 20

    def get_queryset(self):
        qs = TypeBonus.objects.all().order_by('nom')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(nom__icontains=q) | Q(description__icontains=q))
        return qs


class TypeBonusCreateView(AdminRequisMixin, CreateView):
    model = TypeBonus
    form_class = TypeBonusForm
    template_name = 'apps_bonus/type_bonus_form.html'
    success_url = reverse_lazy('apps_bonus:type_bonus_liste')

    def form_valid(self, form):
        response = super().form_valid(form)
        django_messages.success(self.request, "Type de bonus créé avec succès.")
        return response


class TypeBonusUpdateView(AdminRequisMixin, UpdateView):
    model = TypeBonus
    form_class = TypeBonusForm
    template_name = 'apps_bonus/type_bonus_form.html'
    success_url = reverse_lazy('apps_bonus:type_bonus_liste')

    def form_valid(self, form):
        response = super().form_valid(form)
        django_messages.success(self.request, "Type de bonus mis à jour.")
        return response


@login_required
@user_passes_test(est_admin)
@require_POST
def type_bonus_toggle_actif(request, pk):
    """Active / désactive un type de bonus (toggle)."""
    type_bonus = get_object_or_404(TypeBonus, pk=pk)
    type_bonus.est_actif = not type_bonus.est_actif
    type_bonus.save(update_fields=['est_actif'])
    django_messages.success(
        request,
        "Type de bonus activé." if type_bonus.est_actif else "Type de bonus désactivé."
    )
    return redirect('apps_bonus:type_bonus_liste')


# ─────────────────────────────────────────────────────────
# Bonus attribués aux entreprises
# ─────────────────────────────────────────────────────────

class BonusEntrepriseListView(AdminRequisMixin, ListView):
    model = BonusEntreprise
    template_name = 'apps_bonus/bonus_liste.html'
    context_object_name = 'bonus_liste'
    paginate_by = 20

    def get_queryset(self):
        qs = (
            BonusEntreprise.objects
            .select_related('entreprise', 'type_bonus', 'zone_cible')
            .order_by('-date_creation')
        )

        # Réactualise le statut (expiration/quota) des bonus affichés
        for bonus in qs:
            _actualiser_statut(bonus)

        self.form = RechercheBonusForm(self.request.GET or None)
        if self.form.is_valid():
            q = self.form.cleaned_data.get('q')
            statut = self.form.cleaned_data.get('statut')
            categorie = self.form.cleaned_data.get('categorie')

            if q:
                qs = qs.filter(
                    Q(entreprise__raison_sociale__icontains=q) |
                    Q(type_bonus__nom__icontains=q)
                )
            if statut:
                qs = qs.filter(statut=statut)
            if categorie:
                qs = qs.filter(type_bonus__categorie=categorie)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form
        return context


class BonusEntrepriseDetailView(AdminRequisMixin, DetailView):
    model = BonusEntreprise
    template_name = 'apps_bonus/bonus_detail.html'
    context_object_name = 'bonus'

    def get_queryset(self):
        return BonusEntreprise.objects.select_related(
            'entreprise', 'type_bonus', 'zone_cible', 'attribue_par'
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        _actualiser_statut(self.object)
        return super().get(request, *args, **kwargs)


class BonusEntrepriseCreateView(AdminRequisMixin, CreateView):
    model = BonusEntreprise
    form_class = BonusEntrepriseForm
    template_name = 'apps_bonus/bonus_form.html'
    success_url = reverse_lazy('apps_bonus:bonus_liste')

    def form_valid(self, form):
        form.instance.attribue_par = self.request.user
        response = super().form_valid(form)
        django_messages.success(self.request, "Bonus attribué à l'entreprise avec succès.")
        return response


@login_required
@user_passes_test(est_admin)
@require_POST
def bonus_annuler(request, pk):
    """Annule un bonus (ne peut plus être réutilisé)."""
    bonus = get_object_or_404(BonusEntreprise, pk=pk)
    bonus.statut = BonusEntreprise.Statut.ANNULE
    bonus.save(update_fields=['statut'])
    django_messages.success(request, "Bonus annulé.")
    return redirect('apps_bonus:bonus_detail', pk=bonus.pk)


@login_required
@user_passes_test(est_admin)
@require_POST
def bonus_utiliser(request, pk):
    """
    Enregistre une utilisation du bonus (ex: appliqué sur une livraison).
    Bascule automatiquement le statut à UTILISE si le quota est atteint.
    """
    bonus = get_object_or_404(BonusEntreprise, pk=pk)

    if not bonus.est_valide_aujourd_hui:
        django_messages.error(request, "Ce bonus n'est plus valide (expiré, épuisé ou annulé).")
        return redirect('apps_bonus:bonus_detail', pk=bonus.pk)

    bonus.nb_utilisations_actuelles += 1
    update_fields = ['nb_utilisations_actuelles']

    if bonus.nb_utilisations_max and bonus.nb_utilisations_actuelles >= bonus.nb_utilisations_max:
        bonus.statut = BonusEntreprise.Statut.UTILISE
        update_fields.append('statut')

    bonus.save(update_fields=update_fields)
    django_messages.success(request, "Utilisation du bonus enregistrée.")
    return redirect('apps_bonus:bonus_detail', pk=bonus.pk)


# ─────────────────────────────────────────────────────────
# Côté entreprise : "Mes bonus" (lecture seule, propres bonus uniquement)
# ─────────────────────────────────────────────────────────

class MesBonusListView(EntrepriseBonusRequisMixin, ListView):
    """
    Liste des bonus de l'entreprise connectée.
    Inaccessible tant qu'aucun bonus ne lui a été attribué
    (voir EntrepriseBonusRequisMixin.test_func).
    """
    model = BonusEntreprise
    template_name = 'apps_bonus/mes_bonus_liste_entreprise.html'
    context_object_name = 'bonus_liste'
    paginate_by = 20

    def get_queryset(self):
        qs = (
            BonusEntreprise.objects
            .filter(entreprise=self.entreprise)
            .select_related('type_bonus', 'zone_cible')
            .order_by('-date_creation')
        )
        for bonus in qs:
            _actualiser_statut(bonus)

        statut = self.request.GET.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuts'] = BonusEntreprise.Statut.choices
        context['statut_actif'] = self.request.GET.get('statut', '')
        return context


class MonBonusDetailView(EntrepriseBonusRequisMixin, DetailView):
    """
    Détail d'un bonus de l'entreprise connectée.
    Un bonus qui n'appartient pas à l'entreprise renvoie un 404
    (get_queryset filtre déjà par entreprise, en plus du contrôle d'accès
    du mixin).
    """
    model = BonusEntreprise
    template_name = 'apps_bonus/mon_bonus_detail_entreprise.html'
    context_object_name = 'bonus'

    def get_queryset(self):
        return BonusEntreprise.objects.filter(
            entreprise=self.entreprise
        ).select_related('type_bonus', 'zone_cible')

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        _actualiser_statut(self.object)
        return super().get(request, *args, **kwargs)