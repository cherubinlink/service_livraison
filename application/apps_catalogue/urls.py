from django.urls import path
from apps_catalogue import views


app_name = 'apps_catalogue'


urlpatterns = [

    # ── Catégories (admin) ──────────────────────────────────────────
    path('gestion/categories/', views.admin_liste_categories, name='admin_liste_categories'),
    path('gestion/categories/<uuid:pk>/modifier/', views.admin_modifier_categorie, name='admin_modifier_categorie'),
    path('gestion/categories/<uuid:pk>/basculer/', views.admin_toggle_categorie, name='admin_toggle_categorie'),
    path('gestion/categories/<uuid:pk>/supprimer/', views.admin_supprimer_categorie, name='admin_supprimer_categorie'),
 
    # ── Produits (admin) ────────────────────────────────────────────
    path('gestion/produits/', views.admin_liste_produits, name='admin_liste_produits'),
    path('gestion/produits/nouveau/', views.admin_creer_produit, name='admin_creer_produit'),
    path('gestion/produits/<uuid:pk>/', views.admin_detail_produit, name='admin_detail_produit'),
 
    # ── Produits (espace entreprise) ────────────────────────────────
    path('mes-produits/', views.mes_produits, name='mes_produits'),
    path('mes-produits/<uuid:pk>/', views.detail_produit, name='detail_produit'),
    path('mes-produits/<uuid:pk>/valider/', views.valider_produit, name='valider_produit'),
    path('mes-produits/<uuid:pk>/refuser/', views.refuser_produit, name='refuser_produit'),
    path('mes-produits/<uuid:pk>/modifier/', views.modifier_produit, name='modifier_produit'),
    path('mes-produits/<uuid:pk>/photos/ajouter/', views.ajouter_photo_produit, name='ajouter_photo_produit'),
    path('mes-produits/photos/<uuid:pk>/supprimer/', views.supprimer_photo_produit, name='supprimer_photo_produit'),
    
]
