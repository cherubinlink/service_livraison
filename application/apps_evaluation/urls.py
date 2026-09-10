from django.urls import path
from apps_evaluation import views

app_name = 'apps_evaluation'


urlpatterns = [

    # ── Dépôt public (pas de compte requis) ─────────────────────────
    path('livraison/<uuid:livraison_pk>/evaluer/', views.laisser_evaluation, name='laisser_evaluation'),

    # ── Administration ───────────────────────────────────────────────
    path('admin/evaluations/', views.admin_liste_evaluations, name='admin_liste_evaluations'),
    path('admin/evaluations/<uuid:pk>/', views.admin_detail_evaluation, name='admin_detail_evaluation'),

    # ── Espace livreur ────────────────────────────────────────────────
    path('mes-evaluations/', views.livreur_mes_evaluations, name='livreur_mes_evaluations'),

    # ── Espace entreprise ────────────────────────────────────────────
    path('mes-avis-clients/', views.entreprise_mes_evaluations, name='entreprise_mes_evaluations'),
    
]
