from django.urls import path
from apps_notification import views

app_name = 'apps_notification'


urlpatterns = [

    # Administration : toutes les notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification_liste'),
    path('creer/', views.NotificationCreateView.as_view(), name='notification_creer'),
    path('notifications/<uuid:pk>/', views.NotificationDetailView.as_view(), name='notification_detail'),
    path('notifications/<uuid:pk>/renvoyer/', views.notification_renvoyer, name='notification_renvoyer'),
 
    # Côté utilisateur : ses propres notifications
    path('mes-notifications/', views.MesNotificationsListView.as_view(), name='mes_notifications'),
    path('mes-notifications/<uuid:pk>/marquer-lue/', views.notification_marquer_livree, name='notification_marquer_livree'),
    path('mes-notifications/compteur/', views.compteur_non_livrees, name='compteur_non_livrees'),
    
]
