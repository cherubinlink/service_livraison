from django.urls import path
from apps_entreprise import views


app_name = 'apps_entreprise'


urlpatterns = [

    path('tableau-de-bord/entreprise/', views.dashboard, name='dashboard'),
    
]
