from django.urls import path
from apps_entreprise import views


app_name = 'apps_entreprise'


urlpatterns = [

    path('tableau-de-bord/entreprise/', views.dashboard, name='dashboard'),

    path('entreprise/inscription/', views.inscription_entreprise, name='inscription_entreprise'),

    # ── Espace entreprise (self-service) ────────────────────────────────
    path('profil/modifier/', views.modifier_profil, name='modifier_profil'),
    path('documents/', views.mes_documents, name='mes_documents'),
    path('documents/<uuid:pk>/supprimer/', views.supprimer_document, name='supprimer_document'),
    path('contacts/', views.mes_contacts, name='mes_contacts'),
    path('contacts/<uuid:pk>/modifier/', views.modifier_contact, name='modifier_contact'),
    path('contacts/<uuid:pk>/supprimer/', views.supprimer_contact, name='supprimer_contact'),
    path('gardiennage/', views.mes_frais_gardiennage, name='mes_frais_gardiennage'),

    # ── Administration ───────────────────────────────────────────────────
    path('admin/', views.admin_liste_entreprises, name='admin_liste_entreprises'),
    path('admin/<uuid:pk>/', views.admin_detail_entreprise, name='admin_detail_entreprise'),
    path('admin/<uuid:pk>/valider/', views.admin_valider_entreprise, name='admin_valider_entreprise'),
    path('admin/<uuid:pk>/refuser/', views.admin_refuser_entreprise, name='admin_refuser_entreprise'),
    path('admin/<uuid:pk>/suspendre/', views.admin_suspendre_entreprise, name='admin_suspendre_entreprise'),
    path('admin/<uuid:pk>/recalculer-score/', views.admin_recalculer_score, name='admin_recalculer_score'),
    path('admin/documents/<uuid:pk>/verifier/', views.admin_verifier_document, name='admin_verifier_document'),
    path('admin/<uuid:pk>/gardiennage/creer/', views.admin_creer_frais_gardiennage, name='admin_creer_frais_gardiennage'),
    path('admin/gardiennage/<uuid:pk>/confirmer-paiement/', views.admin_confirmer_paiement_gardiennage, name='admin_confirmer_paiement_gardiennage'),
    path('gestion/entreprises/en-attente/', views.admin_entreprises_en_attente, name='admin_entreprises_en_attente'),

    # ── Entrepôts (admin) ────────────────────────────────────────
    path('admin/entrepots/', views.admin_liste_entrepots, name='admin_liste_entrepots'),
    path('admin/entrepots/creer/', views.admin_creer_entrepot, name='admin_creer_entrepot'),
    path('admin/entrepots/<uuid:pk>/', views.admin_detail_entrepot, name='admin_detail_entrepot'),
    path('admin/entrepots/<uuid:pk>/modifier/', views.admin_modifier_entrepot, name='admin_modifier_entrepot'),
    path('admin/entrepots/<uuid:pk>/toggle/', views.admin_toggle_actif_entrepot, name='admin_toggle_actif_entrepot'),
    path('admin/entrepots/<uuid:pk>/supprimer/', views.admin_supprimer_entrepot, name='admin_supprimer_entrepot'),
    path('admin/affectations/<int:pk>/toggle/', views.admin_toggle_affectation, name='admin_toggle_affectation'),

    # ── Entrepôts (espace entreprise, lecture seule) ──────────────
    path('mes-entrepots/', views.mes_entrepots, name='mes_entrepots'),

    path('zones-livraison/', views.zones_livraison, name='zones_livraisons'),
    
]
