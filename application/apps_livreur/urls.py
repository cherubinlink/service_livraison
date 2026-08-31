from django.urls import path
from apps_livreur import views

app_name = 'apps_livreur'


urlpatterns = [

    path('tableau-de-bord/livreur/', views.dashboard, name='dashboard_livreur'),
    
]
