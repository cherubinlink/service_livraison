from .models import Notification


def notifications_utilisateur(request):
    """
    Rend disponibles dans TOUS les templates (via TEMPLATES.OPTIONS.context_processors) :
        - mes_notifications_recentes : les 5 dernières notifications de l'utilisateur connecté
        - mes_notifications_non_lues : le nombre de notifications non "LIVRE" (= non lues)

    Utilisé par le dropdown de la cloche dans navigateur/base_dashboard.html.
    """
    if not request.user.is_authenticated:
        return {}

    qs = Notification.objects.filter(destinataire=request.user).order_by('-date_envoi')

    return {
        'mes_notifications_recentes': qs[:5],
        'mes_notifications_non_lues': qs.exclude(statut_envoi=Notification.StatutEnvoi.LIVRE).count(),
    }