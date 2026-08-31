from django.apps import AppConfig


class AppsLivreurConfig(AppConfig):
    name = 'apps_livreur'
    verbose_name = 'application livreur'


    def ready(self):
        import apps_livreur.signals
