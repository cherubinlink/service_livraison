from django.urls import path
from apps_bonus import views


app_name = 'apps_bonus'


urlpatterns = [

    # Bonus attribués aux entreprises
    path('bonus', views.BonusEntrepriseListView.as_view(), name='bonus_liste'),
    path('attribuer/', views.BonusEntrepriseCreateView.as_view(), name='bonus_attribuer'),
    path('<uuid:pk>/', views.BonusEntrepriseDetailView.as_view(), name='bonus_detail'),
    path('<uuid:pk>/annuler/', views.bonus_annuler, name='bonus_annuler'),
    path('<uuid:pk>/utiliser/', views.bonus_utiliser, name='bonus_utiliser'),
 
    # Types de bonus (catalogue)
    path('types/', views.TypeBonusListView.as_view(), name='type_bonus_liste'),
    path('types/creer/', views.TypeBonusCreateView.as_view(), name='type_bonus_creer'),
    path('types/<uuid:pk>/modifier/', views.TypeBonusUpdateView.as_view(), name='type_bonus_modifier'),
    path('types/<uuid:pk>/toggle/', views.type_bonus_toggle_actif, name='type_bonus_toggle'),

    # Côté entreprise : accès en lecture seule à ses propres bonus
    # (refusé tant qu'aucun bonus n'a été attribué — voir EntrepriseBonusRequisMixin)
    path('mes-bonus/', views.MesBonusListView.as_view(), name='mes_bonus'),
    path('mes-bonus/<uuid:pk>/', views.MonBonusDetailView.as_view(), name='mon_bonus_detail'),
    
]
