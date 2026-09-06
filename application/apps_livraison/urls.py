from django.urls import path
from apps_livraison import views

app_name = 'apps_livraison'


urlpatterns = [

    # ── Espace entreprise ────────────────────────────────────────────
    path('mes-livraisons/', views.mes_livraisons, name='mes_livraisons'),
    path('mes-livraisons/nouvelle/', views.creer_livraison, name='creer_livraison'),
    path('mes-livraisons/<uuid:pk>/', views.detail_livraison, name='detail_livraison'),
    path('mes-livraisons/<uuid:pk>/lignes/ajouter/', views.ajouter_ligne_livraison, name='ajouter_ligne_livraison'),
    path('mes-livraisons/lignes/<uuid:ligne_pk>/supprimer/', views.supprimer_ligne_livraison, name='supprimer_ligne_livraison'),
    path('mes-livraisons/<uuid:pk>/soumettre/', views.soumettre_livraison, name='soumettre_livraison'),
    path('mes-livraisons/<uuid:pk>/annuler/', views.annuler_livraison, name='annuler_livraison'),
    path('mes-livraisons/<uuid:pk>/valider-reception/', views.valider_reception_livraison, name='valider_reception_livraison'),
 
    # ── Administration ───────────────────────────────────────────────
    path('gestion/livraisons/', views.admin_liste_livraisons, name='admin_liste_livraisons'),
    path('gestion/livraisons/<uuid:pk>/', views.admin_detail_livraison, name='admin_detail_livraison'),
    path('gestion/livraisons/<uuid:pk>/valider/', views.admin_valider_livraison, name='admin_valider_livraison'),
    path('gestion/livraisons/<uuid:pk>/refuser/', views.admin_refuser_livraison, name='admin_refuser_livraison'),
    path('gestion/livraisons/<uuid:pk>/attribuer/', views.admin_attribuer_livreur, name='admin_attribuer_livreur'),
    path('gestion/livraisons/<uuid:pk>/code-confirmation/', views.generer_code_confirmation, name='generer_code_confirmation'),
 
    # ── Espace livreur ───────────────────────────────────────────────
    path('mes-courses/', views.livreur_mes_livraisons, name='livreur_mes_livraisons'),
    path('mes-courses/<uuid:pk>/', views.livreur_detail_livraison, name='livreur_detail_livraison'),
    path('mes-courses/<uuid:pk>/prendre-en-charge/', views.livreur_prendre_en_charge, name='livreur_prendre_en_charge'),
    path('mes-courses/<uuid:pk>/signaler-paiement-frais/', views.livreur_signaler_paiement_frais, name='livreur_signaler_paiement_frais'),
    path('mes-courses/<uuid:pk>/terminer/', views.livreur_terminer_livraison, name='livreur_terminer_livraison'),
    path('mes-courses/<uuid:pk>/echec/', views.livreur_signaler_echec, name='livreur_signaler_echec'),
    
]
