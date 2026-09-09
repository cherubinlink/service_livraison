from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import localtime
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import ListView, DetailView

from .forms import MessageForm, NouvelleConversationForm, RechercheConversationForm
from .models import Conversation, Message


class ParticipantRequisMixin(UserPassesTestMixin):
    """S'assure que l'utilisateur connecté fait bien partie de la conversation."""

    def test_func(self):
        conv = self.get_object()
        user = self.request.user
        return user.pk in (conv.participant_1_id, conv.participant_2_id)

    def handle_no_permission(self):
        return HttpResponseForbidden("Vous n'avez pas accès à cette conversation.")


def _serialiser_message(message, request_user):
    """Représentation JSON d'un message, utilisée par l'envoi AJAX et le polling."""
    return {
        'id': str(message.id),
        'contenu': message.contenu,
        'type_contenu': message.type_contenu,
        'fichier_url': message.fichier_joint.url if message.fichier_joint else None,
        'expediteur_id': str(message.expediteur_id) if message.expediteur_id else None,
        'expediteur_nom': message.expediteur.nom if message.expediteur_id else None,
        'est_moi': message.expediteur_id == request_user.id,
        'date_envoi': localtime(message.date_envoi).strftime('%d/%m/%Y %H:%M'),
        'lu': message.lu,
    }


class ConversationListView(LoginRequiredMixin, ListView):
    """Liste des conversations de l'utilisateur connecté."""

    model = Conversation
    template_name = 'apps_messagerie/conversation_liste.html'
    context_object_name = 'conversations'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        qs = (
            Conversation.objects
            .filter(Q(participant_1=user) | Q(participant_2=user))
            .select_related('participant_1', 'participant_2', 'livraison_liee', 'entreprise_liee')
        )

        self.form = RechercheConversationForm(self.request.GET or None)
        if self.form.is_valid():
            q = self.form.cleaned_data.get('q')
            type_conv = self.form.cleaned_data.get('type_conv')
            archivees = self.form.cleaned_data.get('archivees')

            if q:
                qs = qs.filter(
                    Q(sujet__icontains=q) |
                    Q(participant_1__nom__icontains=q) |
                    Q(participant_2__nom__icontains=q)
                )
            if type_conv:
                qs = qs.filter(type_conv=type_conv)

            qs = qs.filter(est_archivee=archivees)
        else:
            qs = qs.filter(est_archivee=False)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form
        context['conversations'] = [
            {
                'obj': conv,
                'autre': conv.get_autre_participant(self.request.user),
                'non_lus': conv.nb_non_lus(self.request.user),
            }
            for conv in context['conversations']
        ]
        return context


class ConversationDetailView(LoginRequiredMixin, ParticipantRequisMixin, DetailView):
    """Détail d'une conversation : historique des messages + formulaire d'envoi."""

    model = Conversation
    template_name = 'apps_messagerie/conversation_detail.html'
    context_object_name = 'conversation'

    def get_queryset(self):
        return Conversation.objects.select_related('participant_1', 'participant_2')

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        # Marque comme lus les messages reçus par l'utilisateur courant
        self.object.messages.filter(lu=False).exclude(expediteur=request.user).update(
            lu=True, date_lecture=timezone.now()
        )

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conv = self.object

        page_number = self.request.GET.get('page')
        paginator = Paginator(conv.messages.select_related('expediteur'), 30)
        context['messages_page'] = paginator.get_page(page_number)

        context['autre_participant'] = conv.get_autre_participant(self.request.user)
        context['form'] = MessageForm()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = MessageForm(request.POST, request.FILES)

        if form.is_valid():
            message = form.save(conversation=self.object, expediteur=request.user)
            self.object.date_dernier_msg = timezone.now()
            self.object.save(update_fields=['date_dernier_msg'])

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'message': _serialiser_message(message, request.user)})
            return redirect('apps_messagerie:conversation_detail', pk=self.object.pk)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'erreurs': form.errors}, status=400)

        context = self.get_context_data(object=self.object)
        context['form'] = form
        return render(request, self.template_name, context)


@login_required
@require_GET
def messages_nouveaux(request, pk):
    """
    Polling temps réel léger : renvoie les messages arrivés après ?depuis=<id_message>.
    Marque également comme lus les messages reçus par l'utilisateur courant.
    Le front-end appelle cette route toutes les quelques secondes.
    """
    conv = get_object_or_404(Conversation, pk=pk)
    if request.user.pk not in (conv.participant_1_id, conv.participant_2_id):
        return HttpResponseForbidden()

    qs = conv.messages.select_related('expediteur')

    dernier_id = request.GET.get('depuis')
    if dernier_id:
        try:
            dernier = Message.objects.only('date_envoi').get(pk=dernier_id, conversation=conv)
            qs = qs.filter(date_envoi__gt=dernier.date_envoi)
        except (Message.DoesNotExist, ValueError):
            pass

    nouveaux = list(qs.order_by('date_envoi'))

    # Marque comme lus les messages reçus (pas envoyés par moi)
    a_marquer = [m for m in nouveaux if m.expediteur_id != request.user.id and not m.lu]
    if a_marquer:
        Message.objects.filter(pk__in=[m.id for m in a_marquer]).update(
            lu=True, date_lecture=timezone.now()
        )
        for m in a_marquer:
            m.lu = True

    return JsonResponse({
        'messages': [_serialiser_message(m, request.user) for m in nouveaux],
    })


@login_required
def demarrer_conversation(request):
    """Démarre (ou récupère) une conversation avec un destinataire donné par email."""
    if request.method == 'POST':
        form = NouvelleConversationForm(request.POST, expediteur=request.user)
        if form.is_valid():
            destinataire = form.cleaned_data['destinataire']
            conv = Conversation.get_ou_creer(request.user, destinataire)

            if form.cleaned_data.get('sujet') and not conv.sujet:
                conv.sujet = form.cleaned_data['sujet']
                conv.save(update_fields=['sujet'])

            Message.objects.create(
                conversation=conv,
                expediteur=request.user,
                contenu=form.cleaned_data['message_initial'],
                type_contenu=Message.TypeContenu.TEXTE,
            )
            conv.date_dernier_msg = timezone.now()
            conv.save(update_fields=['date_dernier_msg'])

            django_messages.success(request, "Conversation démarrée avec succès.")
            return redirect('apps_messagerie:conversation_detail', pk=conv.pk)
    else:
        form = NouvelleConversationForm(expediteur=request.user)

    return render(request, 'apps_messagerie/conversation_nouvelle.html', {'form': form})


@login_required
@require_POST
def archiver_conversation(request, pk):
    """Archive ou désarchive une conversation (toggle)."""
    conv = get_object_or_404(Conversation, pk=pk)
    if request.user.pk not in (conv.participant_1_id, conv.participant_2_id):
        return HttpResponseForbidden()

    conv.est_archivee = not conv.est_archivee
    conv.save(update_fields=['est_archivee'])

    django_messages.success(
        request,
        "Conversation archivée." if conv.est_archivee else "Conversation désarchivée."
    )
    return redirect('apps_messagerie:conversation_liste')


@login_required
@require_POST
def marquer_message_lu(request, pk):
    """Marque un message précis comme lu (usage AJAX, ex: accusé de lecture)."""
    message = get_object_or_404(Message, pk=pk)
    conv = message.conversation

    if request.user.pk not in (conv.participant_1_id, conv.participant_2_id):
        return HttpResponseForbidden()

    message.marquer_lu()
    return JsonResponse({'ok': True, 'lu': message.lu})


@login_required
def compteur_non_lus(request):
    """Nombre total de messages non lus, tous fils confondus (pour badge navbar)."""
    total = (
        Message.objects
        .filter(
            Q(conversation__participant_1=request.user) | Q(conversation__participant_2=request.user),
            lu=False,
        )
        .exclude(expediteur=request.user)
        .count()
    )
    return JsonResponse({'non_lus': total})