import uuid
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

tel_validator = RegexValidator(
    regex=r'^\+?[0-9]{8,15}$',
    message=_('Numéro de téléphone invalide. Format : +237XXXXXXXXX')
)

niu_validator = RegexValidator(
    regex=r'^[A-Z0-9]{8,20}$',
    message=_('NIU invalide. Lettres majuscules et chiffres uniquement.')
)


def upload_path(instance, filename):
    """Chemin d'upload unique basé sur l'UUID + nom du modèle."""
    ext = filename.split('.')[-1]
    nom = f"{uuid.uuid4().hex}.{ext}"
    model_name = instance.__class__.__name__.lower()
    return f"{model_name}/{nom}"
