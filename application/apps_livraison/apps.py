from django.apps import AppConfig


class AppsLivraisonConfig(AppConfig):
    name = 'apps_livraison'
    verbose_name = 'application livraison'


    def ready(self):
        import apps_livraison.signals
