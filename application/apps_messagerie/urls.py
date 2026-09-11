from django.urls import path
from apps_messagerie import views


app_name = 'apps_messagerie'


urlpatterns = [

    # Liste des conversations de l'utilisateur connecté
    path('conversation/', views.ConversationListView.as_view(), name='conversation_liste'),
 
    # Démarrer une nouvelle conversation (par email destinataire)
    path('nouvelle/', views.demarrer_conversation, name='conversation_nouvelle'),

    path('contacter-admin/', views.contacter_administration, name='contacter_administration'),
 
    # Détail d'une conversation (historique + envoi de message)
    path('conversation/<uuid:pk>/', views.ConversationDetailView.as_view(), name='conversation_detail'),

    # Polling temps réel : nouveaux messages depuis un id donné
    path('message/<uuid:pk>/nouveaux/', views.messages_nouveaux, name='messages_nouveaux'),
 
    # Archiver / désarchiver une conversation
    path('conversation/<uuid:pk>/archiver/', views.archiver_conversation, name='conversation_archiver'),
 
    # Marquer un message précis comme lu (AJAX)
    path('message/<uuid:pk>/lu/', views.marquer_message_lu, name='message_marquer_lu'),
 
    # Badge/compteur de messages non lus (AJAX, ex: navbar)
    path('non-lus/compteur/', views.compteur_non_lus, name='compteur_non_lus'),
    
]
