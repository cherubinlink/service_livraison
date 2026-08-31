
import uuid

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps_livraison.models import Livraison


class Evaluation(models.Model):
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    livraison        = models.OneToOneField(Livraison, on_delete=models.CASCADE, related_name='evaluation')
    note_globale        = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    note_rapidite           = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)],
                                                                  blank=True, null=True)
    note_etat_colis            = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)],
                                                                      blank=True, null=True)
    note_livreur                   = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)],
                                                                          blank=True, null=True)
    commentaire                       = models.TextField(blank=True)
    recommande                           = models.BooleanField(default=True)
    date                                    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Évaluation')
        verbose_name_plural = _('Évaluations')
        ordering            = ['-date']

    def __str__(self):
        return f"Éval {self.livraison.numero} – {self.note_globale}/5"
