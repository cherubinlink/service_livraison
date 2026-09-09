from django.urls import path
from apps_transaction import views


app_name = 'apps_transaction'


urlpatterns = [

    # ── Administration ───────────────────────────────────────────────
    path('gestion/lots-paiement/', views.admin_liste_lots_paiement, name='admin_liste_lots_paiement'),
    path('gestion/lots-paiement/nouveau/', views.admin_creer_lot_paiement, name='admin_creer_lot_paiement'),
    path('gestion/lots-paiement/<uuid:pk>/', views.admin_detail_lot_paiement, name='admin_detail_lot_paiement'),
    path('gestion/lots-paiement/<uuid:pk>/marquer-envoye/', views.admin_marquer_lot_envoye, name='admin_marquer_lot_envoye'),
    path('gestion/transactions/', views.admin_liste_transactions, name='admin_liste_transactions'),
 
    # ── Espace entreprise ────────────────────────────────────────────
    path('mes-paiements/', views.mes_lots_paiement, name='mes_lots_paiement'),
    path('mes-paiements/<uuid:pk>/', views.detail_lot_paiement, name='detail_lot_paiement'),
    path('mes-paiements/<uuid:pk>/confirmer/', views.confirmer_reception_lot, name='confirmer_reception_lot'),
    path('mes-paiements/<uuid:pk>/litige/', views.signaler_litige_lot, name='signaler_litige_lot'),
    path('mes-transactions/', views.mes_transactions, name='mes_transactions'),
    
]
