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
 
    # ── Livraison directe — PUBLIC (aucune authentification requise) ──
    path('envoyer-un-colis/', views.nouvelle_livraison_directe, name='nouvelle_livraison_directe'),
    path('suivi/<str:token>/', views.suivre_livraison_directe, name='suivre_livraison_directe'),
 
    # ── Livraison directe — espace entreprise ─────────────────────────
    path('mes-courses-directes/nouvelle/', views.entreprise_nouvelle_livraison_directe, name='entreprise_nouvelle_livraison_directe'),
    path('mes-courses-directes/', views.mes_livraisons_directes, name='mes_livraisons_directes'),
 
    # ── Livraison directe — administration ────────────────────────────
    path('gestion/courses-directes/', views.admin_liste_livraisons_directes, name='admin_liste_livraisons_directes'),
    path('gestion/courses-directes/<uuid:pk>/', views.admin_detail_livraison_directe, name='admin_detail_livraison_directe'),
    path('gestion/courses-directes/<uuid:pk>/confirmer/', views.admin_confirmer_livraison_directe, name='admin_confirmer_livraison_directe'),
    path('gestion/courses-directes/<uuid:pk>/attribuer/', views.admin_attribuer_livreur_directe, name='admin_attribuer_livreur_directe'),
    path('gestion/courses-directes/<uuid:pk>/modifier-prix/', views.admin_modifier_prix_directe, name='admin_modifier_prix_directe'),
    path('gestion/courses-directes/<uuid:pk>/annuler/', views.admin_annuler_livraison_directe, name='admin_annuler_livraison_directe'),
 
    # ── Livraison directe — espace livreur ────────────────────────────
    path('mes-courses-directes-livreur/', views.livreur_livraisons_directes, name='livreur_livraisons_directes'),
    path('mes-courses-directes-livreur/<uuid:pk>/', views.livreur_detail_livraison_directe, name='livreur_detail_livraison_directe'),
    path('mes-courses-directes-livreur/<uuid:pk>/prendre-en-charge/', views.livreur_prendre_en_charge_directe, name='livreur_prendre_en_charge_directe'),
    path('mes-courses-directes-livreur/<uuid:pk>/terminer/', views.livreur_terminer_livraison_directe, name='livreur_terminer_livraison_directe'),
    path('mes-courses-directes-livreur/<uuid:pk>/echec/', views.livreur_signaler_echec_directe, name='livreur_signaler_echec_directe'),

    
]
