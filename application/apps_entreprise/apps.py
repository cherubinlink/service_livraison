from django.apps import AppConfig


class AppsEntrepriseConfig(AppConfig):
    name = 'apps_entreprise'
    verbose_name = 'application entreprise'


    def ready(self):
        import apps_entreprise.signals
