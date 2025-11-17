from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import JornadaClienteHistorico, Notification, User

@receiver(post_save, sender=JornadaClienteHistorico)
def create_notification_on_comment(sender, instance, created, **kwargs):
    if created:
        comment = instance
        orcamento = comment.orcamento
        comment_author = comment.usuario

        # Use a set to ensure each user is notified only once
        recipients = set()

        # 1. Add the budget owner (consultor)
        recipients.add(orcamento.usuario)

        # 2. Add the store manager (gerente)
        if orcamento.usuario.loja:
            managers = User.objects.filter(role='gerente', loja=orcamento.usuario.loja)
            for manager in managers:
                recipients.add(manager)

        # 3. Handle @admin mentions and add them to subscribers
        comentario_text = str(comment.comentario or '').lower()
        if '@admin' in comentario_text:
            admins = User.objects.filter(role='administrador')
            for admin in admins:
                recipients.add(admin)
                orcamento.subscribers.add(admin) # Subscribe admin to future comments

        # 4. Add all other existing subscribers for this budget
        for subscriber in orcamento.subscribers.all():
            recipients.add(subscriber)

        # 5. Remove the person who wrote the comment, so they don't get a notification for their own action
        if comment_author in recipients:
            recipients.remove(comment_author)

        # 6. Create notifications for all unique recipients
        for user in recipients:
            Notification.objects.create(
                recipient=user,
                comment=comment
            )
