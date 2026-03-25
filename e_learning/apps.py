from django.apps import AppConfig


class ELearningConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'e_learning'
    
    def ready(self):
        import e_learning.signals

