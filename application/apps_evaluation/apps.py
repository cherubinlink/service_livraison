from django.apps import AppConfig


class AppsEvaluationConfig(AppConfig):
    name = 'apps_evaluation'
    verbose_name = 'application evaluation'


    def ready(self):
        import apps_evaluation.signals
