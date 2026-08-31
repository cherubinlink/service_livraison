from django.apps import AppConfig


class AppsTransactionConfig(AppConfig):
    name = 'apps_transaction'
    verbose_name = 'application transaction'

    def ready(self):
        import apps_transaction.signals
