import logging

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse, NoReverseMatch
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.generic import ListView, DetailView, CreateView

from .forms import NotificationManuelleForm, RechercheNotificationForm
from .models import Notification

logger = logging.getLogger(__name__)


def est_admin(user):
    return user.is_authenticated and getattr(user, 'est_admin', False)


def redirection_surete(*noms_urls, defaut='/'):
    """Reverse le premier nom d'URL valide, sinon retombe sur `defaut` (évite un crash NoReverseMatch)."""
    for nom in noms_urls:
        try:
            return redirect(reverse(nom))
        except NoReverseMatch:
            continue
    return redirect(defaut)


class AdminRequisMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Réserve les vues de gestion des notifications aux administrateurs."""

    def test_func(self):
        return est_admin(self.request.user)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        django_messages.error(self.request, "Accès réservé aux administrateurs.")
        return redirection_surete('apps_core:dashboard_admin', defaut='/')


def envoyer_notification(notification):
    """
    Point d'intégration avec les fournisseurs externes (Africa's Talking
    pour SMS/WhatsApp, FCM pour le push, SMTP pour l'email).

    ⚠️ Stub à implémenter : brancher ici le vrai client d'envoi.
    En attendant, on simule un envoi réussi pour ne pas bloquer le flux
    applicatif (création de livraison, OTP, etc.).
    """
    try:
        # TODO: appeler le provider réel selon notification.canal
        notification.statut_envoi = Notification.StatutEnvoi.ENVOYE
        notification.nb_tentatives += 1
        notification.save(update_fields=['statut_envoi', 'nb_tentatives'])
    except Exception as exc:  # pragma: no cover - dépend du provider réel
        logger.exception("Échec d'envoi de la notification %s", notification.pk)
        notification.statut_envoi = Notification.StatutEnvoi.ECHEC
        notification.nb_tentatives += 1
        notification.erreur = str(exc)
        notification.save(update_fields=['statut_envoi', 'nb_tentatives', 'erreur'])


# ─────────────────────────────────────────────────────────
# Administration : toutes les notifications
# ─────────────────────────────────────────────────────────

class NotificationListView(AdminRequisMixin, ListView):
    model = Notification
    template_name = 'apps_notification/notification_liste.html'
    context_object_name = 'notifications'
    paginate_by = 30

    def get_queryset(self):
        qs = Notification.objects.select_related('destinataire', 'livraison').order_by('-date_envoi')

        self.form = RechercheNotificationForm(self.request.GET or None)
        if self.form.is_valid():
            q = self.form.cleaned_data.get('q')
            canal = self.form.cleaned_data.get('canal')
            evenement = self.form.cleaned_data.get('evenement')
            statut_envoi = self.form.cleaned_data.get('statut_envoi')

            if q:
                qs = qs.filter(
                    Q(destinataire__nom__icontains=q) |
                    Q(sujet__icontains=q) |
                    Q(message__icontains=q)
                )
            if canal:
                qs = qs.filter(canal=canal)
            if evenement:
                qs = qs.filter(evenement=evenement)
            if statut_envoi:
                qs = qs.filter(statut_envoi=statut_envoi)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form
        return context


class NotificationDetailView(AdminRequisMixin, DetailView):
    model = Notification
    template_name = 'apps_notification/notification_detail.html'
    context_object_name = 'notification'

    def get_queryset(self):
        return Notification.objects.select_related('destinataire', 'livraison')


class NotificationCreateView(AdminRequisMixin, CreateView):
    model = Notification
    form_class = NotificationManuelleForm
    template_name = 'apps_notification/notification_form.html'
    success_url = reverse_lazy('apps_notification:notification_liste')

    def form_valid(self, form):
        response = super().form_valid(form)
        envoyer_notification(self.object)
        django_messages.success(self.request, "Notification créée et envoyée à la file.")
        return response


@login_required
@user_passes_test(est_admin)
@require_POST
def notification_renvoyer(request, pk):
    """Relance manuellement l'envoi d'une notification en échec."""
    notification = get_object_or_404(Notification, pk=pk)

    if notification.statut_envoi not in (Notification.StatutEnvoi.ECHEC, Notification.StatutEnvoi.EN_ATTENTE):
        django_messages.warning(request, "Cette notification n'est pas en échec, aucun renvoi effectué.")
        return redirect('apps_notification:notification_detail', pk=notification.pk)

    notification.erreur = ''
    envoyer_notification(notification)
    django_messages.success(request, "Notification relancée.")
    return redirect('apps_notification:notification_detail', pk=notification.pk)


# ─────────────────────────────────────────────────────────
# Côté utilisateur : ses propres notifications
# ─────────────────────────────────────────────────────────

class MesNotificationsListView(LoginRequiredMixin, ListView):
    """Liste des notifications reçues par l'utilisateur connecté."""

    model = Notification
    template_name = 'apps_notification/mes_notifications_liste.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        qs = Notification.objects.filter(destinataire=self.request.user).order_by('-date_envoi')

        canal = self.request.GET.get('canal')
        if canal:
            qs = qs.filter(canal=canal)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['canaux'] = Notification.Canal.choices
        context['canal_actif'] = self.request.GET.get('canal', '')
        return context


@login_required
@require_POST
def notification_marquer_livree(request, pk):
    """
    Marque une notification comme lue/accusée réception par son destinataire.
    Sécurité : seul le destinataire peut marquer sa propre notification.
    """
    notification = get_object_or_404(Notification, pk=pk)

    if notification.destinataire_id != request.user.id:
        return HttpResponseForbidden("Cette notification ne vous appartient pas.")

    if notification.statut_envoi != Notification.StatutEnvoi.LIVRE:
        notification.statut_envoi = Notification.StatutEnvoi.LIVRE
        notification.date_livraison_notif = timezone.now()
        notification.save(update_fields=['statut_envoi', 'date_livraison_notif'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('apps_notification:mes_notifications')


@login_required
@require_GET
def compteur_non_livrees(request):
    """Nombre de notifications non encore accusées réception (badge navbar)."""
    total = (
        Notification.objects
        .filter(destinataire=request.user)
        .exclude(statut_envoi=Notification.StatutEnvoi.LIVRE)
        .count()
    )
    return JsonResponse({'non_livrees': total})