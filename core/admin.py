from django.contrib import admin
from .models import User, Cliente, Especificador, Orcamento, JornadaClienteHistorico

# Register your models here.
admin.site.register(User)

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'cpf_cnpj', 'telefone', 'email')
    search_fields = ('nome_completo', 'cpf_cnpj', 'telefone', 'email')

admin.site.register(Especificador)
admin.site.register(Orcamento)
admin.site.register(JornadaClienteHistorico)