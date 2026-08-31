from django.apps import AppConfig


class AppsNotificationConfig(AppConfig):
    name = 'apps_notification'
    verbose_name = 'application notification'


    def ready(self):
        import apps_notification.signals
