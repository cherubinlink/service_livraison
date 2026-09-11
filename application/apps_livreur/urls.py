from django.urls import path
from apps_livreur import views

app_name = 'apps_livreur'


urlpatterns = [

    path('tableau-de-bord/livreur/', views.dashboard, name='dashboard_livreur'),
    path('inscription/', views.inscription_livreur, name='inscription'),

    # ── Espace livreur (self-service) ───────────────────────────────────
    path('profil/modifier/', views.modifier_profil_livreur, name='modifier_profil'),
    path('statut/<str:statut>/', views.changer_statut_livreur, name='changer_statut'),
    path('position/mettre-a-jour/', views.mettre_a_jour_position, name='mettre_a_jour_position'),
    path('historique/', views.historique_livraisons, name='historique_livraisons'),
    path('ma-position/', views.historique_position, name='historique_position'),
    path('mes-revenus/', views.mes_revenus, name='mes_revenus'),

    # ── Administration ───────────────────────────────────────────────────
    path('admin/', views.admin_liste_livreurs, name='admin_liste_livreurs'),
    path('admin/<uuid:pk>/', views.admin_detail_livreur, name='admin_detail_livreur'),
    path('admin/<uuid:pk>/suspendre/', views.admin_suspendre_livreur, name='admin_suspendre_livreur'),
    path('admin/<uuid:pk>/reactiver/', views.admin_reactiver_livreur, name='admin_reactiver_livreur'),
    
]
