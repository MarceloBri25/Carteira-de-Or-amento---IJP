from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class Loja(models.Model):
    nome = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nome

class User(AbstractUser):
    ROLE_CHOICES = (
        ('consultor', 'Consultor'),
        ('gerente', 'Gerente'),
        ('administrador', 'Administrador'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    loja = models.ForeignKey(Loja, on_delete=models.SET_NULL, blank=True, null=True)

class Cliente(models.Model):
    nome_completo = models.CharField(max_length=100, unique=True)
    cpf_cnpj = models.CharField(max_length=20, blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.nome_completo

class Especificador(models.Model):
    nome_completo = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome_completo

class Orcamento(models.Model):
    THERMOMETER_CHOICES = [
        ('Quente', 'Quente'),
        ('Morno', 'Morno'),
        ('Frio', 'Frio'),
    ]

    CATEGORY_CHOICES = [
        ('Basic', 'Basic'),
        ('Black', 'Black'),
        ('Clássico', 'Clássico'),
        ('Novo', 'Novo'),
        ('Special', 'Special'),
    ]

    STAGE_CHOICES = [
        ('Perdida', 'Perdida'),
        ('Fechada e Ganha', 'Fechada e Ganha'),
        ('Em Negociação', 'Em Negociação'),
        ('Revisão de Projeto', 'Revisão de Projeto'),
        ('B2B', 'B2B'),
        ('Especificação', 'Especificação'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    data_solicitacao = models.DateField(default=timezone.now)
    especificador = models.ForeignKey(Especificador, on_delete=models.SET_NULL, blank=True, null=True)
    categoria = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='Novo')
    nome_cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, blank=True, null=True)
    numero_orcamento = models.CharField(max_length=50, unique=True, null=True)
    data_envio = models.DateField(blank=True, null=True)
    valor_orcamento = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    termometro = models.CharField(max_length=6, choices=THERMOMETER_CHOICES, default='Frio')
    data_previsao_fechamento = models.DateField(blank=True, null=True)
    semana_previsao_fechamento = models.CharField(max_length=20, blank=True, null=True) # e.g., 'Semana 1', 'Semana 2'
    etapa = models.CharField(max_length=50, choices=STAGE_CHOICES, default='Especificação')
    jornada_cliente = models.TextField(blank=True, null=True)
    data_fechada_ganha = models.DateField(blank=True, null=True)
    subscribers = models.ManyToManyField(User, related_name='subscribed_orcamentos', blank=True)

    def __str__(self):
        return f'{self.nome_cliente} - {self.numero_orcamento}'

    @property
    def ordered_historico_jornada(self):
        return self.historico_jornada.order_by('-data_edicao')

    @property
    def dias_em_aberto(self):
        if self.etapa not in ['Fechada e Ganha', 'Perdida']:
            today = timezone.now().date()
            return (today - self.data_solicitacao).days
        return None

    @property
    def dias_para_fechar(self):
        if self.etapa == 'Fechada e Ganha' and self.data_fechada_ganha:
            return (self.data_fechada_ganha - self.data_solicitacao).days
        return None

class JornadaClienteHistorico(models.Model):
    orcamento = models.ForeignKey(Orcamento, on_delete=models.CASCADE, related_name='historico_jornada')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    comentario = models.TextField()
    data_edicao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_edicao'] # Order by most recent first

    def __str__(self):
        return f'Comentário de {self.usuario.username if self.usuario else "Usuário Desconhecido"} em {self.data_edicao.strftime("%d/%m/%Y %H:%M")}'

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    comment = models.ForeignKey(JornadaClienteHistorico, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Notificação para {self.recipient.username} sobre o comentário {self.comment.id}'
