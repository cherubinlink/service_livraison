from django.urls import path
from apps_core import views


app_name = 'apps_core'


urlpatterns = [

    path('', views.accueil, name='accueil'),
    path('conditions-utilisation/', views.conditions_utilisation, name='conditions_utilisation'),
    path('politique-confidentialite/', views.politique_confidentialite, name='politique_confidentialite'),
    path('contact/', views.contact, name='contact'),

    # dashboard
    path('gestion/tableau-de-bord/', views.dashboard_admin, name='dashboard_admin'),
    path('client/tableau-de-bord/', views.dashboard_client, name='dashboard_client'),

    # Authentification
    path('inscription/', views.inscription, name='inscription'),
    path('connexion/', views.connexion, name='connexion'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
    path('verifier-otp/', views.verifier_otp, name='verifier_otp'),
    path('renvoyer-otp/', views.renvoyer_otp, name='renvoyer_otp'),
    path('mot-de-passe-oublie/', views.mot_de_passe_oublie, name='mot_de_passe_oublie'),
    path('reinitialiser-mot-de-passe/<str:token>/', views.reinitialiser_mot_de_passe, name='reinitialiser_mot_de_passe'),
    path('mon-profil/', views.mon_profil, name='mon_profil'),
    path('parametres/', views.parametres, name='parametres'),

    # confuguration pays zone
    path('gestion/geographie/', views.configuration_geographie, name='configuration_geographie'),
    path('gestion/geographie/<str:niveau>/<uuid:pk>/modifier/', views.modifier_geographie, name='modifier_geographie'),
    path('gestion/geographie/<str:niveau>/<uuid:pk>/activer-desactiver/', views.toggle_actif_geographie, name='toggle_actif_geographie'),
    path('gestion/geographie/<str:niveau>/<uuid:pk>/supprimer/', views.supprimer_geographie, name='supprimer_geographie'),
    path('gestion/geographie/zone/<uuid:pk>/tarif/', views.modifier_tarif_zone, name='modifier_tarif_zone'),
    path('gestion/geographie/zone/<uuid:pk>/historique-tarifs/', views.historique_tarifs_zone, name='historique_tarifs_zone'),
    path('gestion/geographie/coefficients-vehicule/', views.gerer_coefficients_vehicule, name='gerer_coefficients_vehicule'),
    # ── Tarifs inter-villes (livraison directe entre deux villes) ────
    path('gestion/tarifs/intervilles/', views.gerer_tarifs_intervilles, name='gerer_tarifs_intervilles'),
    path('gestion/tarifs/intervilles/<int:pk>/toggle/', views.toggle_actif_tarif_intervville, name='toggle_actif_tarif_intervville'),
    path('gestion/tarifs/intervilles/<int:pk>/supprimer/', views.supprimer_tarif_intervville, name='supprimer_tarif_intervville'),

    path('gestion/parametres-systeme/', views.gerer_parametres_systeme, name='gerer_parametres_systeme'),
    path('gestion/parametres-systeme/<int:pk>/supprimer/', views.supprimer_parametre_systeme, name='supprimer_parametre_systeme'),
    
]
