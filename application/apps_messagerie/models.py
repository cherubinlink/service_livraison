import uuid

from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps_core.models import Utilisateur
from apps_livraison.models import Livraison
from apps_entreprise.models import Entreprise


class Conversation(models.Model):
    class TypeConversation(models.TextChoices):
        ADMIN_ADMIN      = 'ADMIN_ADMIN', _('Admin - Admin')
        ADMIN_ENTEPRISE  = 'ADMIN_ENT', _('Admin - Entreprise')
        ADMIN_LIVREUR     = 'ADMIN_LIV', _('Admin - Livreur')
        ADMIN_CLIENT        = 'ADMIN_CLI', _('Admin - Client')

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type_conv        = models.CharField(max_length=15, choices=TypeConversation.choices, db_index=True)
    participant_1        = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='conversations_en_tant_que_1')
    participant_2            = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name='conversations_en_tant_que_2')
    livraison_liee                = models.ForeignKey(Livraison, on_delete=models.SET_NULL, null=True, blank=True,
                                                          related_name='conversations')
    entreprise_liee                   = models.ForeignKey(Entreprise, on_delete=models.SET_NULL, null=True, blank=True,
                                                              related_name='conversations')
    sujet                                = models.CharField(max_length=200, blank=True)
    est_archivee                            = models.BooleanField(default=False)
    date_creation                              = models.DateTimeField(auto_now_add=True, db_index=True)
    date_dernier_msg                              = models.DateTimeField(null=True, db_index=True)

    class Meta:
        verbose_name        = _('conversation')
        verbose_name_plural = _('conversations')
        ordering            = ['-date_dernier_msg']
        unique_together     = [['participant_1', 'participant_2']]
        indexes = [
            models.Index(fields=['participant_1', 'est_archivee']),
            models.Index(fields=['participant_2', 'est_archivee']),
        ]

    def __str__(self):
        return f"{self.participant_1.nom} - {self.participant_2.nom}{' |' + self.sujet if self.sujet else ''}"

    def get_autre_participant(self, user):
        return self.participant_2 if self.participant_1_id == user.pk else self.participant_1

    def nb_non_lus(self, user):
        return self.messages.filter(lu=False).exclude(expediteur=user).count()

    @classmethod
    def get_ou_creer(cls, user1, user2):
        conv = cls.objects.filter(participant_1=user1, participant_2=user2).first() \
            or cls.objects.filter(participant_1=user2, participant_2=user1).first()
        if not conv:
            roles = {user1.role, user2.role}
            if roles == {'ADMIN'}:
                type_conv = cls.TypeConversation.ADMIN_ADMIN
            elif 'ADMIN' in roles and 'ENTREPRISE' in roles:
                type_conv = cls.TypeConversation.ADMIN_ENTEPRISE
            elif 'ADMIN' in roles and 'LIVREUR' in roles:
                type_conv = cls.TypeConversation.ADMIN_LIVREUR
            elif 'ADMIN' in roles and 'CLIENT' in roles:
                type_conv = cls.TypeConversation.ADMIN_CLIENT
            else:
                type_conv = cls.TypeConversation.ADMIN_ADMIN
            conv = cls.objects.create(participant_1=user1, participant_2=user2, type_conv=type_conv)
        return conv


class Message(models.Model):
    class TypeContenu(models.TextChoices):
        TEXTE   = 'TEXTE', _('Texte')
        FICHIER = 'FICHIER', _('Fichier joint')
        SYSTEME = 'SYSTEME', _('Message système')

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation       = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    expediteur            = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
                                                 related_name='message_envoye')
    contenu                  = models.TextField()
    type_contenu                 = models.CharField(max_length=10, choices=TypeContenu.choices, default=TypeContenu.TEXTE)
    fichier_joint                    = models.FileField(upload_to='message/fichier/', blank=True, null=True,
                                                            validators=[FileExtensionValidator(
                                                                allowed_extensions=['pdf', 'jpg', 'jpeg', 'doc', 'docx', 'xlsx'])])
    lu                                  = models.BooleanField(default=False)
    date_lecture                          = models.DateTimeField(null=True, blank=True)
    date_envoi                               = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = _('message')
        verbose_name_plural = _('messages')
        ordering            = ['date_envoi']
        indexes = [
            models.Index(fields=['conversation', 'date_envoi']),
            models.Index(fields=['expediteur', 'lu']),
        ]

    def __str__(self):
        return f"{self.expediteur.nom if self.expediteur else '-'}-{self.conversation} : {self.contenu[:40]}"

    def marquer_lu(self):
        if not self.lu:
            self.lu = True
            self.date_lecture = timezone.now()
            self.save(update_fields=['lu', 'date_lecture'])
