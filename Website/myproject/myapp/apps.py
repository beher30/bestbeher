from django.apps import AppConfig


class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'
    verbose_name = 'Payment Management System'

    def ready(self):
        """Initialize app-specific configurations."""
        # Import and register template tags
        import myapp.templatetags.myapp_filters  # noqa
