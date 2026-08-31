from django.apps import AppConfig


class AppsBonusConfig(AppConfig):
    name = 'apps_bonus'
    verbose_name = 'application bonus'


    def ready(self):
        import apps_bonus.signals
