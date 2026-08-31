"""
URL configuration for app_livraison project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('apps_core.urls', namespace='apps_core')),
    path('apps_bonus/', include('apps_bonus.urls', namespace='apps_bonus')),
    path('apps_entreprise/', include('apps_entreprise.urls', namespace='apps_entreprise')),
    path('apps_catalogue/', include('apps_catalogue.urls', namespace='apps_catalogue')),
    path('apps_evaluation/', include('apps_evaluation.urls',namespace='apps_evaluation')),
    path('apps_livraison/', include('apps_livraison.urls', namespace='apps_livraison')),
    path('apps_livreur/', include('apps_livreur.urls', namespace='apps_livreur')),
    path('apps_messagerie/', include('apps_messagerie.urls', namespace='apps_messagerie')),
    path('apps_notification/', include('apps_notification.urls', namespace='apps_notification')),
    path('apps_transaction/', include('apps_transaction.urls', namespace='apps_transaction')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
