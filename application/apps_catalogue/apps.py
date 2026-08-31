from django.apps import AppConfig


class AppsCatalogueConfig(AppConfig):
    name = 'apps_catalogue'
    verbose_name = 'application catalogue'


    def ready(self):
        import apps_catalogue.signals
