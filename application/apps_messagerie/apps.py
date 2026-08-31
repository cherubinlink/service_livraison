from django.apps import AppConfig


class AppsMessagerieConfig(AppConfig):
    name = 'apps_messagerie'
    verbose_name = 'application messagerie' 


    def ready(self):
        import apps_messagerie.signals
