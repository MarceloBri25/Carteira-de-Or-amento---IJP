from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.views.generic import ListView
from .models import Orcamento, Loja, User, Cliente, Especificador, JornadaClienteHistorico, Notification
from django.shortcuts import get_object_or_404
from django import forms
from .models import User, Orcamento, Cliente, Especificador, JornadaClienteHistorico
import pandas as pd
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Case, When, Value
import io
from datetime import datetime
from django.db import models
from django.utils import timezone
from django.views.decorators.http import require_POST
import json
from django.forms.models import model_to_dict

class UserRegistrationForm(forms.ModelForm):
    """
    Formulário para registro de novos usuários.
    Inclui campos para nome de usuário, nome, sobrenome, email, função (role) e loja,
    além de campos para senha e confirmação de senha.
    """
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirme a senha', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'loja']
    
    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        self.fields['loja'].required = False

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password2 = cleaned_data.get("password2")
        role = cleaned_data.get("role")
        loja = cleaned_data.get("loja")

        if password and password2 and password != password2:
            self.add_error('password2', "As senhas não correspondem.")
        
        if role in ['consultor', 'gerente'] and not loja:
            self.add_error('loja', 'Este campo é obrigatório para o cargo selecionado.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

class UserEditForm(forms.ModelForm):
    """
    Formulário para edição de informações de um usuário existente.
    Permite alterar nome, sobrenome, email, função (role) e loja.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'role', 'loja']

class OrcamentoForm(forms.ModelForm):
    """
    Formulário base para criação e edição de orçamentos.
    Exclui o campo 'usuario', que é preenchido automaticamente pela view.
    """
    class Meta:
        model = Orcamento
        exclude = ['usuario']

    def __init__(self, *args, **kwargs):
        super(OrcamentoForm, self).__init__(*args, **kwargs)
        self.fields['motivo_perda'].required = False

class OrcamentoAdminForm(forms.ModelForm):
    """
    Formulário administrativo para criação e edição de orçamentos.
    Inclui todos os campos do modelo Orcamento, permitindo que administradores
    selecionem o usuário associado ao orçamento.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['usuario'].widget.attrs.update({'class': 'form-select'})

    class Meta:
        model = Orcamento
        fields = '__all__'

class ClienteForm(forms.ModelForm):
    """
    Formulário para criação e edição de clientes.
    Utilizado principalmente em contextos AJAX para adicionar clientes rapidamente.
    """
    class Meta:
        model = Cliente
        fields = '__all__'

class EspecificadorForm(forms.ModelForm):
    """
    Formulário para criação e edição de especificadores.
    Utilizado em contextos AJAX e nas telas de gerenciamento de especificadores.
    """
    class Meta:
        model = Especificador
        fields = '__all__'

class JornadaClienteHistoricoForm(forms.ModelForm):
    """
    Formulário para adicionar um novo comentário ao histórico da jornada de um cliente.
    """
    class Meta:
        model = JornadaClienteHistorico
        fields = ['comentario']

class ClienteFullForm(forms.ModelForm):
    """
    Formulário completo para criação e edição de clientes, incluindo todos os campos.
    """
    class Meta:
        model = Cliente
        fields = '__all__'

@login_required
def home_view(request):
    """
    Redireciona o usuário para o dashboard apropriado com base em seu papel (role).
    Se o usuário não estiver autenticado, redireciona para a página de login.
    """
    if request.user.is_authenticated:
        if request.user.role == 'consultor':
            return redirect('consultor_dashboard')
        elif request.user.role == 'gerente':
            return redirect('gerente_dashboard')
        elif request.user.role == 'administrador':
            return redirect('administrador_dashboard')
    return redirect('login')

class LojasView(ListView):
    """
    View baseada em classe para listar todas as lojas cadastradas no sistema.
    """
    model = Loja
    template_name = 'lojas.html'
    context_object_name = 'lojas'

def register_user_view(request):
    """
    Permite o registro de novos usuários no sistema.
    Processa o formulário de registro e exibe mensagens de sucesso ou erro.
    """
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuário cadastrado com sucesso!')
            form = UserRegistrationForm() # Create a new empty form
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = UserRegistrationForm()
    
    lojas = Loja.objects.all()
    return render(request, 'register_user.html', {'form': form, 'lojas': lojas})

def logout_view(request):
    """
    Desloga o usuário atual e o redireciona para a página de login.
    """
    logout(request)
    return redirect('login')

class UserListView(ListView):
    """
    View baseada em classe para listar todos os usuários cadastrados.
    Organiza os usuários por loja e exibe aqueles sem loja associada.
    """
    model = User
    template_name = 'user_list.html'
    context_object_name = 'users'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lojas = Loja.objects.all()
        users_by_loja = {loja: [] for loja in lojas}
        users_sem_loja = []

        users = User.objects.all().order_by('loja__nome', 'username')
        
        for user in users:
            if user.loja:
                users_by_loja[user.loja].append(user)
            else:
                users_sem_loja.append(user)

        context['users_by_loja'] = users_by_loja
        context['users_sem_loja'] = users_sem_loja
        return context

def user_edit_view(request, pk):
    """
    Permite a edição do perfil de um usuário existente e a alteração de sua senha
    (apenas para administradores).
    """
    user_to_edit = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        # Check which form was submitted
        if 'update_profile' in request.POST:
            form = UserEditForm(request.POST, instance=user_to_edit)
            if form.is_valid():
                form.save()
                messages.success(request, 'Perfil do usuário atualizado com sucesso!')
                return redirect('user_edit', pk=user_to_edit.pk)
        
        elif 'update_password' in request.POST and request.user.role == 'administrador':
            password_form = SetPasswordForm(user=user_to_edit, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, f'A senha do usuário {user_to_edit.username} foi alterada com sucesso!')
                return redirect('user_edit', pk=user_to_edit.pk)
    
    # For GET request, initialize both forms
    form = UserEditForm(instance=user_to_edit)
    password_form = SetPasswordForm(user=user_to_edit)
    
    lojas = Loja.objects.all()
    context = {
        'form': form,
        'password_form': password_form,
        'user': user_to_edit,
        'lojas': lojas
    }
    return render(request, 'user_edit.html', context)

def user_deactivate_view(request, pk):
    """
    Desativa um usuário, tornando-o inativo no sistema.
    """
    user = get_object_or_404(User, pk=pk)
    user.is_active = False
    user.save()
    return redirect('user_list')

def user_activate_view(request, pk):
    """
    Ativa um usuário previamente desativado, tornando-o novamente ativo no sistema.
    """
    user = get_object_or_404(User, pk=pk)
    user.is_active = True
    user.save()
    return redirect('user_list')

@login_required
def consultor_dashboard(request):
    """
    Exibe o dashboard do consultor, mostrando orçamentos abertos e permitindo filtragem
    por mês, cliente, especificador, semana e status (termômetro).
    """
    # Base queryset for the logged-in user, excluding 'Fechada e Ganha'
    orcamentos = Orcamento.objects.filter(usuario=request.user).exclude(etapa='Fechada e Ganha')

    # Get filter parameters
    selected_month = request.GET.get('month')
    selected_cliente = request.GET.get('cliente')
    selected_especificador = request.GET.get('especificador')
    selected_semanas = request.GET.getlist('semana')
    selected_status = request.GET.get('status')

    # Apply filters
    if selected_month:
        orcamentos = orcamentos.filter(data_previsao_fechamento__month=selected_month)
    if selected_cliente:
        orcamentos = orcamentos.filter(nome_cliente__id=selected_cliente)
    if selected_especificador:
        orcamentos = orcamentos.filter(especificador__id=selected_especificador)
    if selected_semanas:
        orcamentos = orcamentos.filter(semana_previsao_fechamento__in=selected_semanas)
    if selected_status:
        orcamentos = orcamentos.filter(termometro=selected_status)

    # Custom ordering
    orcamentos = orcamentos.annotate(
        status_order=Case(
            When(termometro='Quente', then=Value(1)),
            When(termometro='Morno', then=Value(2)),
            When(termometro='Frio', then=Value(3)),
            default=Value(4),
            output_field=models.IntegerField()
        )
    ).order_by('status_order')

    # Get filter options
    available_months = Orcamento.objects.filter(usuario=request.user).dates('data_previsao_fechamento', 'month', order='ASC')
    all_clientes = Cliente.objects.filter(orcamento__usuario=request.user).distinct()
    all_especificadores = Especificador.objects.filter(orcamento__usuario=request.user).distinct()

    context = {
        'orcamentos': orcamentos,
        'available_months': available_months,
        'all_clientes': all_clientes,
        'all_especificadores': all_especificadores,
        'selected_month': selected_month,
        'selected_cliente': selected_cliente,
        'selected_especificador': selected_especificador,
        'selected_semanas': selected_semanas,
        'selected_status': selected_status,
    }
    return render(request, 'consultor_dashboard.html', context)

@login_required
def consultor_criar_orcamento(request):
    """
    Permite que um consultor crie um novo orçamento.
    Processa o formulário de criação e associa o orçamento ao usuário logado.
    """
    if request.method == 'POST':
        form = OrcamentoForm(request.POST)
        if form.is_valid():
            orcamento = form.save(commit=False)
            orcamento.usuario = request.user
            orcamento.save()
            return redirect('consultor_dashboard')
    else:
        form = OrcamentoForm()

    especificadores = Especificador.objects.all()
    clientes = Cliente.objects.all()
    category_choices = Orcamento.CATEGORY_CHOICES
    thermometer_choices = Orcamento.THERMOMETER_CHOICES
    stage_choices = Orcamento.STAGE_CHOICES
    context = {
        'form': form,
        'especificadores': especificadores,
        'clientes': clientes,
        'category_choices': category_choices,
        'thermometer_choices': thermometer_choices,
        'stage_choices': stage_choices,
    }
    return render(request, 'consultor_criar_orcamento.html', context)

from django.http import JsonResponse

def add_cliente(request):
    """
    Endpoint AJAX para adicionar um novo cliente rapidamente através de um formulário.
    Retorna os dados do cliente em formato JSON.
    """
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            return JsonResponse({'id': cliente.id, 'nome_completo': cliente.nome_completo})
    return JsonResponse({'error': 'Invalid request'}, status=400)

def add_especificador(request):
    """
    Endpoint AJAX para adicionar um novo especificador rapidamente através de um formulário.
    Retorna os dados do especificador em formato JSON.
    """
    if request.method == 'POST':
        form = EspecificadorForm(request.POST)
        if form.is_valid():
            especificador = form.save()
            return JsonResponse({'id': especificador.id, 'nome_completo': especificador.nome_completo})
        else:
            return JsonResponse({'error': 'Formulário inválido', 'errors': form.errors}, status=400)

@login_required
def edit_orcamento(request, pk):
    """
    Permite a edição de um orçamento existente.
    Carrega o orçamento pelo PK, processa o formulário de edição e salva as alterações.
    """
    orcamento = get_object_or_404(Orcamento, pk=pk)
    if request.method == 'POST':
        form = OrcamentoForm(request.POST, instance=orcamento)
        if form.is_valid():
            form.save()
            return redirect('consultor_dashboard')
    else:
        form = OrcamentoForm(instance=orcamento)

    especificadores = Especificador.objects.all()
    clientes = Cliente.objects.all()
    category_choices = Orcamento.CATEGORY_CHOICES
    thermometer_choices = Orcamento.THERMOMETER_CHOICES
    stage_choices = Orcamento.STAGE_CHOICES
    context = {
        'form': form,
        'orcamento': orcamento,
        'especificadores': especificadores,
        'clientes': clientes,
        'category_choices': category_choices,
        'thermometer_choices': thermometer_choices,
        'stage_choices': stage_choices,
    }
    return render(request, 'edit_orcamento.html', context)

@login_required
def gerente_dashboard(request):
    """
    Exibe o dashboard do gerente, com uma visão geral dos orçamentos da sua loja.
    Inclui métricas do mês, desempenho dos consultores e previsão de fechamento semanal.
    Permite filtrar por ano e mês.
    """
    # Get the current manager's loja
    gerente_loja = request.user.loja
    if not gerente_loja:
        # Redirect or show an error if the manager is not associated with a loja
        return redirect('home')

    # Get filter parameters from request
    selected_year = request.GET.get('year', str(datetime.now().year))
    selected_month = request.GET.get('month', str(datetime.now().month))

    # Base queryset for the manager's loja
    orcamentos_loja = Orcamento.objects.filter(usuario__loja=gerente_loja)

    # --- VISÃO GERAL ---
    orcamentos_geral = orcamentos_loja
    if selected_year:
        orcamentos_geral = orcamentos_geral.filter(data_previsao_fechamento__year=selected_year)
    if selected_month:
        orcamentos_geral = orcamentos_geral.filter(data_previsao_fechamento__month=selected_month)

    orcamentos_abertos = orcamentos_geral.exclude(etapa__in=['Fechada e Ganha', 'Perdida'])
    total_orcamento = orcamentos_abertos.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    total_orcamento_quantidade = orcamentos_abertos.count()

    orcamentos_quentes = orcamentos_abertos.filter(termometro='Quente').count()
    total_quentes_value = orcamentos_abertos.filter(termometro='Quente').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    orcamentos_mornos = orcamentos_abertos.filter(termometro='Morno').count()
    total_mornos_value = orcamentos_abertos.filter(termometro='Morno').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    orcamentos_frios = orcamentos_abertos.filter(termometro='Frio').count()
    total_frios_value = orcamentos_abertos.filter(termometro='Frio').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    orcamentos_ganhos = orcamentos_geral.filter(etapa='Fechada e Ganha')
    total_fechada_ganha_value = orcamentos_ganhos.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    total_fechada_ganha_quantidade = orcamentos_ganhos.count()

    orcamentos_perdidos = orcamentos_geral.filter(etapa='Perdida')
    total_perdido_mes_quantidade = orcamentos_perdidos.count()
    total_perdido_mes_valor = orcamentos_perdidos.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    # --- MÉTRICA DO MÊS ---
    orcamentos_mes = orcamentos_loja
    if selected_year:
        orcamentos_mes = orcamentos_mes.filter(data_solicitacao__year=selected_year)
    if selected_month:
        orcamentos_mes = orcamentos_mes.filter(data_solicitacao__month=selected_month)

    total_novos_orcamentos_mes_quantidade = orcamentos_mes.count()
    total_novos_orcamentos_mes_valor = orcamentos_mes.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    total_fechada_ganha_mes_quantidade = orcamentos_mes.filter(etapa='Fechada e Ganha').count()
    total_fechada_ganha_mes_valor = orcamentos_mes.filter(etapa='Fechada e Ganha').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    orcamentos_quentes_mes = orcamentos_mes.filter(termometro='Quente').count()
    total_quentes_mes_valor = orcamentos_mes.filter(termometro='Quente').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    orcamentos_mornos_mes = orcamentos_mes.filter(termometro='Morno').count()
    total_mornos_mes_valor = orcamentos_mes.filter(termometro='Morno').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    orcamentos_frios_mes = orcamentos_mes.filter(termometro='Frio').count()
    total_frios_mes_valor = orcamentos_mes.filter(termometro='Frio').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    # --- DESEMPENHO DOS CONSULTORES ---
    consultants = User.objects.filter(loja=gerente_loja, role='consultor')
    consultant_performance_data = []
    for consultant in consultants:
        orcamentos_consultant = orcamentos_geral.filter(usuario=consultant)
        total_carteira = orcamentos_consultant.exclude(etapa__in=['Fechada e Ganha', 'Perdida']).aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
        total_vendido = orcamentos_consultant.filter(etapa='Fechada e Ganha').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
        consultant_performance_data.append({
            'username': consultant.username,
            'total_carteira': total_carteira,
            'total_vendido': total_vendido,
        })
    consultant_performance = sorted(consultant_performance_data, key=lambda x: x['total_vendido'], reverse=True)

    # --- PREVISÃO DE FECHAMENTO POR SEMANA (Stacked Bar Chart) ---
    orcamentos_for_chart = orcamentos_geral.exclude(etapa__in=['Fechada e Ganha', 'Perdida'])
    weekly_forecast_data = orcamentos_for_chart.values('semana_previsao_fechamento', 'termometro').annotate(
        total_valor=Sum('valor_orcamento')
    ).order_by('semana_previsao_fechamento')

    weekly_labels = sorted(list(orcamentos_for_chart.values_list('semana_previsao_fechamento', flat=True).distinct()))
    quente_data = [0] * len(weekly_labels)
    morno_data = [0] * len(weekly_labels)
    frio_data = [0] * len(weekly_labels)

    for item in weekly_forecast_data:
        try:
            week_index = weekly_labels.index(item['semana_previsao_fechamento'])
            if item['termometro'] == 'Quente':
                quente_data[week_index] = float(item['total_valor']) if item['total_valor'] else 0
            elif item['termometro'] == 'Morno':
                morno_data[week_index] = float(item['total_valor']) if item['total_valor'] else 0
            elif item['termometro'] == 'Frio':
                frio_data[week_index] = float(item['total_valor']) if item['total_valor'] else 0
        except ValueError:
            pass

    # --- CONTEXT ---
    available_years = orcamentos_loja.dates('data_previsao_fechamento', 'year', order='DESC')
    months_choices = {
        '1': 'Janeiro', '2': 'Fevereiro', '3': 'Março', '4': 'Abril',
        '5': 'Maio', '6': 'Junho', '7': 'Julho', '8': 'Agosto',
        '9': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }

    context = {
        # Visão Geral
        'total_orcamento': total_orcamento,
        'total_orcamento_quantidade': total_orcamento_quantidade,
        'total_fechada_ganha_value': total_fechada_ganha_value,
        'total_fechada_ganha_quantidade': total_fechada_ganha_quantidade,
        'orcamentos_quentes': orcamentos_quentes,
        'total_quentes_value': total_quentes_value,
        'orcamentos_mornos': orcamentos_mornos,
        'total_mornos_value': total_mornos_value,
        'orcamentos_frios': orcamentos_frios,
        'total_frios_value': total_frios_value,
        'total_perdido_mes_quantidade': total_perdido_mes_quantidade,
        'total_perdido_mes_valor': total_perdido_mes_valor,
        # Métrica do Mês
        'total_novos_orcamentos_mes_quantidade': total_novos_orcamentos_mes_quantidade,
        'total_novos_orcamentos_mes_valor': total_novos_orcamentos_mes_valor,
        'total_fechada_ganha_mes_quantidade': total_fechada_ganha_mes_quantidade,
        'total_fechada_ganha_mes_valor': total_fechada_ganha_mes_valor,
        'orcamentos_quentes_mes': orcamentos_quentes_mes,
        'total_quentes_mes_valor': total_quentes_mes_valor,
        'orcamentos_mornos_mes': orcamentos_mornos_mes,
        'total_mornos_mes_valor': total_mornos_mes_valor,
        'orcamentos_frios_mes': orcamentos_frios_mes,
        'total_frios_mes_valor': total_frios_mes_valor,
        # Desempenho dos Consultores
        'consultant_performance': consultant_performance,
        # Previsão Semanal
        'weekly_labels': weekly_labels,
        'quente_data': quente_data,
        'morno_data': morno_data,
        'frio_data': frio_data,
        # Filtros
        'available_years': [d.year for d in available_years],
        'selected_year': selected_year,
        'months_choices': months_choices,
        'selected_month': selected_month,
    }

    return render(request, 'gerente_dashboard.html', context)

@login_required
def gerente_criar_orcamento(request):
    """
    Permite que um gerente crie um novo orçamento e o atribua a um consultor de sua loja.
    """
    if request.method == 'POST':
        form = OrcamentoForm(request.POST)
        consultor_id = request.POST.get('consultor')

        if not consultor_id:
            messages.error(request, 'Por favor, selecione um consultor.')
        elif form.is_valid():
            orcamento = form.save(commit=False)
            consultor = get_object_or_404(User, id=consultor_id)
            orcamento.usuario = consultor
            orcamento.save()
            messages.success(request, 'Orçamento criado com sucesso!')
            return redirect('gerente_dashboard')

    # If we are here, it's either a GET request or the form was invalid.
    form = OrcamentoForm(request.POST or None)
    consultores = User.objects.filter(role='consultor', loja=request.user.loja)
    especificadores = Especificador.objects.all()
    clientes = Cliente.objects.all()
    category_choices = Orcamento.CATEGORY_CHOICES
    thermometer_choices = Orcamento.THERMOMETER_CHOICES
    stage_choices = Orcamento.STAGE_CHOICES
    context = {
        'form': form,
        'consultores': consultores,
        'all_especificadores': especificadores,
        'all_clientes': clientes,
        'category_choices': category_choices,
        'thermometer_choices': thermometer_choices,
        'stage_choices': stage_choices,
    }
    return render(request, 'gerente_criar_orcamento.html', context)

@login_required
def administrador_criar_orcamento(request):
    """
    Permite que um administrador crie um novo orçamento, atribuindo-o a qualquer usuário.
    Utiliza um formulário de orçamento mais abrangente.
    """
    if request.method == 'POST':
        form = OrcamentoAdminForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('administrador_dashboard')
    else:
        form = OrcamentoAdminForm()

    especificadores = Especificador.objects.all()
    clientes = Cliente.objects.all()
    category_choices = Orcamento.CATEGORY_CHOICES
    thermometer_choices = Orcamento.THERMOMETER_CHOICES
    stage_choices = Orcamento.STAGE_CHOICES
    context = {
        'form': form,
        'especificadores': especificadores,
        'clientes': clientes,
        'category_choices': category_choices,
        'thermometer_choices': thermometer_choices,
        'stage_choices': stage_choices,
    }
    return render(request, 'administrador_criar_orcamento.html', context)


@login_required
def meus_clientes_view(request):
    """
    Exibe a lista de orçamentos (tratados como "meus clientes") do usuário logado,
    ou da loja (para gerentes), ou todos (para administradores).
    Permite filtrar os orçamentos por diversos critérios.
    """
    user = request.user
    if user.role == 'consultor':
        orcamentos = Orcamento.objects.filter(usuario=user)
        base_orcamentos_for_filters = orcamentos
    elif user.role == 'gerente':
        orcamentos = Orcamento.objects.filter(usuario__loja=user.loja)
        base_orcamentos_for_filters = orcamentos
    elif user.role == 'administrador':
        orcamentos = Orcamento.objects.all()
        base_orcamentos_for_filters = orcamentos
    else:
        orcamentos = Orcamento.objects.none()
        base_orcamentos_for_filters = orcamentos

    # Get filter parameters
    selected_year = request.GET.get('year')
    selected_month = request.GET.get('month')
    selected_especificador = request.GET.get('especificador')
    selected_cliente = request.GET.get('cliente')
    selected_etapa = request.GET.get('etapa')
    selected_termometro = request.GET.getlist('termometro')

    # Apply filters
    if selected_year:
        orcamentos = orcamentos.filter(data_previsao_fechamento__year=selected_year)
    if selected_month:
        orcamentos = orcamentos.filter(data_previsao_fechamento__month=selected_month)
    if selected_especificador:
        orcamentos = orcamentos.filter(especificador__id=selected_especificador)
    if selected_cliente:
        orcamentos = orcamentos.filter(nome_cliente__id=selected_cliente)
    if selected_etapa:
        orcamentos = orcamentos.filter(etapa=selected_etapa)
    if selected_termometro:
        orcamentos = orcamentos.filter(termometro__in=selected_termometro)

    # Get filter options
    available_years = base_orcamentos_for_filters.dates('data_previsao_fechamento', 'year', order='DESC')
    all_especificadores = Especificador.objects.all()
    all_clientes = Cliente.objects.filter(orcamento__in=base_orcamentos_for_filters).distinct()
    stage_choices = Orcamento.STAGE_CHOICES
    thermometer_choices = Orcamento.THERMOMETER_CHOICES

    orcamentos_list = list(orcamentos)

    for orcamento in orcamentos_list:
        jornada_completa = []
        if orcamento.jornada_cliente:
            naive_datetime = datetime.combine(orcamento.data_solicitacao, datetime.min.time())
            aware_datetime = timezone.make_aware(naive_datetime)
            jornada_completa.append({
                'usuario': orcamento.usuario,
                'data': aware_datetime,
                'comentario': orcamento.jornada_cliente,
            })
        for historico in orcamento.historico_jornada.all():
            jornada_completa.append({
                'usuario': historico.usuario,
                'data': historico.data_edicao,
                'comentario': historico.comentario,
            })
        orcamento.jornada_completa = sorted(jornada_completa, key=lambda x: x['data'], reverse=False)

    context = {
        'orcamentos': orcamentos_list,
        'available_years': [d.year for d in available_years],
        'all_especificadores': all_especificadores,
        'all_clientes': all_clientes,
        'stage_choices': stage_choices,
        'thermometer_choices': thermometer_choices,
        'selected_termometro': selected_termometro,
    }
    return render(request, 'meus_clientes.html', context)

@login_required
def todos_orcamentos_view(request):
    """
    Exibe uma lista de todos os orçamentos (ou orçamentos da loja, ou do consultor),
    com funcionalidades de filtragem avançadas por ano, mês, especificador, cliente,
    etapa, termômetro, loja e consultor.
    """
    user = request.user
    base_orcamentos = Orcamento.objects.all()

    if user.role == 'consultor':
        base_orcamentos = base_orcamentos.filter(usuario=user)
        todos_orcamentos_url_name = 'consultor_todos_orcamentos'
    elif user.role == 'gerente':
        base_orcamentos = base_orcamentos.filter(usuario__loja=user.loja)
        todos_orcamentos_url_name = 'todos_orcamentos_gerente'
    elif user.role == 'administrador':
        todos_orcamentos_url_name = 'todos_orcamentos_administrador'
    else:
        base_orcamentos = Orcamento.objects.none()
        todos_orcamentos_url_name = ''

    # Get filter parameters
    selected_year = request.GET.get('year')
    selected_month = request.GET.get('month')
    selected_especificador = request.GET.get('especificador')
    selected_cliente = request.GET.get('cliente')
    selected_etapa = request.GET.get('etapa')
    selected_termometro = request.GET.get('termometro')
    selected_lojas = request.GET.getlist('loja')
    selected_consultor = request.GET.get('consultor')

    # Apply filters
    orcamentos = base_orcamentos
    if selected_year:
        orcamentos = orcamentos.filter(data_previsao_fechamento__year=selected_year)
    if selected_month:
        orcamentos = orcamentos.filter(data_previsao_fechamento__month=selected_month)
    if selected_especificador:
        orcamentos = orcamentos.filter(especificador__id=selected_especificador)
    if selected_cliente:
        orcamentos = orcamentos.filter(nome_cliente__id=selected_cliente)
    if selected_etapa:
        orcamentos = orcamentos.filter(etapa=selected_etapa)
    if selected_termometro:
        orcamentos = orcamentos.filter(termometro=selected_termometro)
    if selected_lojas:
        orcamentos = orcamentos.filter(usuario__loja__id__in=selected_lojas)
    if selected_consultor:
        orcamentos = orcamentos.filter(usuario__id=selected_consultor)

    # Get selected objects for repopulating form
    selected_cliente_obj = None
    if selected_cliente:
        try:
            selected_cliente_obj = Cliente.objects.get(pk=selected_cliente)
        except Cliente.DoesNotExist:
            selected_cliente_obj = None

    selected_especificador_obj = None
    if selected_especificador:
        try:
            selected_especificador_obj = Especificador.objects.get(pk=selected_especificador)
        except Especificador.DoesNotExist:
            selected_especificador_obj = None

    # Get filter options
    available_years = base_orcamentos.dates('data_previsao_fechamento', 'year', order='DESC')
    all_especificadores = Especificador.objects.filter(orcamento__in=base_orcamentos).distinct()
    all_clientes = Cliente.objects.filter(orcamento__in=base_orcamentos).distinct()
    stage_choices = Orcamento.STAGE_CHOICES
    thermometer_choices = Orcamento.THERMOMETER_CHOICES
    all_lojas = Loja.objects.all()
    
    all_consultores = User.objects.filter(role='consultor')
    if user.role == 'gerente':
        all_consultores = all_consultores.filter(loja=user.loja)

    context = {
        'orcamentos': orcamentos,
        'todos_orcamentos_url_name': todos_orcamentos_url_name,
        'available_years': [d.year for d in available_years],
        'all_especificadores': all_especificadores,
        'all_clientes': all_clientes,
        'stage_choices': stage_choices,
        'thermometer_choices': thermometer_choices,
        'all_lojas': all_lojas,
        'all_consultores': all_consultores,
        'selected_lojas': [int(x) for x in selected_lojas],
        'selected_cliente_obj': selected_cliente_obj,
        'selected_especificador_obj': selected_especificador_obj,
    }
    return render(request, 'todos_orcamentos.html', context)

@login_required
def marcar_como_ganho(request, pk):
    """
    Marca um orçamento específico como 'Fechada e Ganha' e registra a data da alteração.
    Redireciona o usuário de volta para a página de onde veio.
    """
    orcamento = get_object_or_404(Orcamento, pk=pk)
    orcamento.etapa = 'Fechada e Ganha'
    orcamento.data_fechada_ganha = timezone.now().date()
    orcamento.save()
    return redirect(request.META.get('HTTP_REFERER', 'home'))

@login_required
def consultor_orcamentos_fechados_ganhos(request):
    """
    Exibe uma lista dos orçamentos marcados como 'Fechada e Ganha' para o consultor logado.
    """
    orcamentos = Orcamento.objects.filter(usuario=request.user, etapa='Fechada e Ganha')
    return render(request, 'consultor_orcamentos_fechados_ganhos.html', {'orcamentos': orcamentos})

@login_required
def reverter_orcamento_ganho(request, pk):
    """
    Reverte o status de um orçamento de 'Fechada e Ganha' para 'Follow-up'.
    Redireciona o usuário de volta para a página de onde veio.
    """
    orcamento = get_object_or_404(Orcamento, pk=pk)
    orcamento.etapa = 'Follow-up'
    orcamento.save()
    return redirect(request.META.get('HTTP_REFERER', 'home'))

from django.db.models import Sum, Count
from datetime import datetime

@login_required
def administrador_dashboard(request):
    """
    Exibe o dashboard do administrador, com uma visão abrangente de todos os orçamentos
    e métricas de desempenho em todas as lojas. Permite filtragem por ano, mês e lojas.
    Inclui análise de motivos de perda e ranking de especificadores.
    """
    selected_year = request.GET.get('year', str(datetime.now().year))
    selected_month = request.GET.get('month', str(datetime.now().month))
    selected_lojas = request.GET.getlist('loja')

    orcamentos_abertos = Orcamento.objects.exclude(etapa__in=['Fechada e Ganha', 'Perdida'])

    # Apply filters
    if selected_year:
        orcamentos_abertos = orcamentos_abertos.filter(data_previsao_fechamento__year=selected_year)
    if selected_month:
        orcamentos_abertos = orcamentos_abertos.filter(data_previsao_fechamento__month=selected_month)
    if selected_lojas:
        orcamentos_abertos = orcamentos_abertos.filter(usuario__loja__nome__in=selected_lojas)

    # Calculate metrics for open budgets
    total_orcamento = orcamentos_abertos.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    total_orcamento_quantidade = orcamentos_abertos.count()

    orcamentos_quentes = orcamentos_abertos.filter(termometro='Quente').count()
    total_quentes_value = orcamentos_abertos.filter(termometro='Quente').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    orcamentos_mornos = orcamentos_abertos.filter(termometro='Morno').count()
    total_mornos_value = orcamentos_abertos.filter(termometro='Morno').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    orcamentos_frios = orcamentos_abertos.filter(termometro='Frio').count()
    total_frios_value = orcamentos_abertos.filter(termometro='Frio').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    # Calculate metrics for "Fechada e Ganha"
    orcamentos_ganhos = Orcamento.objects.filter(etapa='Fechada e Ganha')
    if selected_year:
        orcamentos_ganhos = orcamentos_ganhos.filter(data_fechada_ganha__year=selected_year)
    if selected_month:
        orcamentos_ganhos = orcamentos_ganhos.filter(data_fechada_ganha__month=selected_month)
    if selected_lojas:
        orcamentos_ganhos = orcamentos_ganhos.filter(usuario__loja__nome__in=selected_lojas)

    total_fechada_ganha_value = orcamentos_ganhos.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    total_fechada_ganha_quantidade = orcamentos_ganhos.count()

    # Monthly metrics based on data_solicitacao
    orcamentos_mes = Orcamento.objects.all()
    if selected_year:
        orcamentos_mes = orcamentos_mes.filter(data_solicitacao__year=selected_year)
    if selected_month:
        orcamentos_mes = orcamentos_mes.filter(data_solicitacao__month=selected_month)
    if selected_lojas:
        orcamentos_mes = orcamentos_mes.filter(usuario__loja__nome__in=selected_lojas)

    orcamentos_perdidos = Orcamento.objects.filter(etapa='Perdida')
    if selected_year:
        orcamentos_perdidos = orcamentos_perdidos.filter(data_previsao_fechamento__year=selected_year)
    if selected_month:
        orcamentos_perdidos = orcamentos_perdidos.filter(data_previsao_fechamento__month=selected_month)
    if selected_lojas:
        orcamentos_perdidos = orcamentos_perdidos.filter(usuario__loja__nome__in=selected_lojas)

    total_perdido_mes_quantidade = orcamentos_perdidos.count()
    total_perdido_mes_valor = orcamentos_perdidos.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    total_novos_orcamentos_mes_quantidade = orcamentos_mes.count()
    total_novos_orcamentos_mes_valor = orcamentos_mes.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    total_fechada_ganha_mes_quantidade = orcamentos_mes.filter(etapa='Fechada e Ganha').count()
    total_fechada_ganha_mes_valor = orcamentos_mes.filter(etapa='Fechada e Ganha').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    orcamentos_quentes_mes = orcamentos_mes.filter(termometro='Quente').count()
    total_quentes_mes_valor = orcamentos_mes.filter(termometro='Quente').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    orcamentos_mornos_mes = orcamentos_mes.filter(termometro='Morno').count()
    total_mornos_mes_valor = orcamentos_mes.filter(termometro='Morno').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    orcamentos_frios_mes = orcamentos_mes.filter(termometro='Frio').count()
    total_frios_mes_valor = orcamentos_mes.filter(termometro='Frio').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    # Chart data
    orcamentos = Orcamento.objects.all()
    if selected_year:
        orcamentos = orcamentos.filter(data_previsao_fechamento__year=selected_year)
    if selected_month:
        orcamentos = orcamentos.filter(data_previsao_fechamento__month=selected_month)
    if selected_lojas:
        orcamentos = orcamentos.filter(usuario__loja__nome__in=selected_lojas)

    # Exclude 'Fechada e Ganha' from the weekly forecast chart
    orcamentos_for_chart = orcamentos.exclude(etapa='Fechada e Ganha')

    consultants = User.objects.filter(role='consultor')
    if selected_lojas:
        consultants = consultants.filter(loja__nome__in=selected_lojas)

    consultant_performance_data = []
    for consultant in consultants:
        orcamentos_consultant = orcamentos.filter(usuario=consultant)
        total_carteira = orcamentos_consultant.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
        total_vendido = orcamentos_consultant.filter(etapa='Fechada e Ganha').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
        consultant_performance_data.append({
            'username': consultant.username,
            'total_carteira': total_carteira,
            'total_vendido': total_vendido,
        })

    consultant_performance = sorted(consultant_performance_data, key=lambda x: x['total_vendido'], reverse=True)

    # New logic for weekly forecast chart
    weekly_forecast_data = orcamentos_for_chart.values('semana_previsao_fechamento', 'termometro').annotate(
        total_valor=Sum('valor_orcamento')
    ).order_by('semana_previsao_fechamento')

    weekly_labels = sorted(list(orcamentos_for_chart.values_list('semana_previsao_fechamento', flat=True).distinct()))
    
    quente_data = [0] * len(weekly_labels)
    morno_data = [0] * len(weekly_labels)
    frio_data = [0] * len(weekly_labels)

    for item in weekly_forecast_data:
        try:
            week_index = weekly_labels.index(item['semana_previsao_fechamento'])
            if item['termometro'] == 'Quente':
                quente_data[week_index] = float(item['total_valor']) if item['total_valor'] else 0
            elif item['termometro'] == 'Morno':
                morno_data[week_index] = float(item['total_valor']) if item['total_valor'] else 0
            elif item['termometro'] == 'Frio':
                frio_data[week_index] = float(item['total_valor']) if item['total_valor'] else 0
        except ValueError:
            # This can happen if a week has no orcamentos
            pass

    especificadores_filter = models.Q(orcamento__etapa='Fechada e Ganha')
    if selected_year:
        especificadores_filter &= models.Q(orcamento__data_fechada_ganha__year=selected_year)
    if selected_month:
        especificadores_filter &= models.Q(orcamento__data_fechada_ganha__month=selected_month)
    if selected_lojas:
        especificadores_filter &= models.Q(orcamento__usuario__loja__nome__in=selected_lojas)

    especificadores_ranking = Especificador.objects.annotate(
        total_comprado=Sum('orcamento__valor_orcamento', filter=especificadores_filter)
    ).order_by('-total_comprado')

    # Desempenho da Loja
    lojas_all = Loja.objects.all()
    loja_performance = []
    for loja in lojas_all:
        # Base queryset for the store
        orcamentos_loja_base = Orcamento.objects.filter(usuario__loja=loja)

        # Apply filters for 'carteira'
        orcamentos_carteira = orcamentos_loja_base
        if selected_year:
            orcamentos_carteira = orcamentos_carteira.filter(data_previsao_fechamento__year=selected_year)
        if selected_month:
            orcamentos_carteira = orcamentos_carteira.filter(data_previsao_fechamento__month=selected_month)
        
        total_carteira = orcamentos_carteira.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

        # Apply filters for 'vendido'
        orcamentos_vendido = orcamentos_loja_base.filter(etapa='Fechada e Ganha')
        if selected_year:
            orcamentos_vendido = orcamentos_vendido.filter(data_fechada_ganha__year=selected_year)
        if selected_month:
            orcamentos_vendido = orcamentos_vendido.filter(data_fechada_ganha__month=selected_month)

        total_vendido = orcamentos_vendido.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
        
        percentual_vendido = (total_vendido / total_carteira * 100) if total_carteira > 0 else 0
        
        # Generate initials
        initials = "".join(part[0] for part in loja.nome.split()).upper()

        loja_performance.append({
            'nome': loja.nome,
            'total_carteira': total_carteira,
            'total_vendido': total_vendido,
            'percentual_vendido': round(percentual_vendido, 2),
            'initials': initials,
        })

    # Sort by name
    loja_performance = sorted(loja_performance, key=lambda x: x['nome'])

    # Filter options
    available_years = Orcamento.objects.dates('data_previsao_fechamento', 'year', order='DESC')
    months_choices = {
        '1': 'Janeiro', '2': 'Fevereiro', '3': 'Março', '4': 'Abril',
        '5': 'Maio', '6': 'Junho', '7': 'Julho', '8': 'Agosto',
        '9': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }
    lojas = Loja.objects.values_list('nome', flat=True)

    context = {
        'total_orcamento': total_orcamento,
        'total_orcamento_quantidade': total_orcamento_quantidade,
        'total_fechada_ganha_value': total_fechada_ganha_value,
        'total_fechada_ganha_quantidade': total_fechada_ganha_quantidade,
        'orcamentos_quentes': orcamentos_quentes,
        'total_quentes_value': total_quentes_value,
        'orcamentos_mornos': orcamentos_mornos,
        'total_mornos_value': total_mornos_value,
        'orcamentos_frios': orcamentos_frios,
        'total_frios_value': total_frios_value,
        'total_perdido_mes_quantidade': total_perdido_mes_quantidade,
        'total_perdido_mes_valor': total_perdido_mes_valor,
        'total_novos_orcamentos_mes_quantidade': total_novos_orcamentos_mes_quantidade,
        'total_novos_orcamentos_mes_valor': total_novos_orcamentos_mes_valor,
        'total_fechada_ganha_mes_quantidade': total_fechada_ganha_mes_quantidade,
        'total_fechada_ganha_mes_valor': total_fechada_ganha_mes_valor,
        'orcamentos_quentes_mes': orcamentos_quentes_mes,
        'total_quentes_mes_valor': total_quentes_mes_valor,
        'orcamentos_mornos_mes': orcamentos_mornos_mes,
        'total_mornos_mes_valor': total_mornos_mes_valor,
        'orcamentos_frios_mes': orcamentos_frios_mes,
        'total_frios_mes_valor': total_frios_mes_valor,
        'consultant_performance': consultant_performance,
        'weekly_labels': weekly_labels,
        'quente_data': quente_data,
        'morno_data': morno_data,
        'frio_data': frio_data,
        'especificadores_ranking': especificadores_ranking,
        'loja_performance': loja_performance,
        'available_years': [d.year for d in available_years],
        'selected_year': selected_year,
        'months_choices': months_choices,
        'selected_month': selected_month,
        'lojas': lojas,
        'selected_lojas': selected_lojas,
    }

    return render(request, 'administrador_dashboard.html', context)

@login_required
def add_jornada_cliente_comment(request, pk):
    """
    Adiciona um novo comentário ao histórico de jornada de um orçamento específico.
    """
    orcamento = get_object_or_404(Orcamento, pk=pk)
    if request.method == 'POST':
        form = JornadaClienteHistoricoForm(request.POST)
        if form.is_valid():
            historico = form.save(commit=False)
            historico.orcamento = orcamento
            historico.usuario = request.user
            historico.save()
    
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required
def add_cliente_full(request):
    """
    Permite adicionar um cliente completo através de um formulário.
    Pode ser usado via requisição POST (AJAX) ou para renderizar a página do formulário.
    """
    if request.method == 'POST':
        form = ClienteFullForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            return JsonResponse({'id': cliente.id, 'nome_completo': cliente.nome_completo})
        else:
            return JsonResponse({'error': 'Formulário inválido', 'errors': form.errors}, status=400)
    return render(request, 'add_cliente_full.html', {'form': ClienteFullForm()})

from django.core.paginator import Paginator

@login_required
def clientes_cadastrados(request):
    """
    Exibe uma lista paginada de todos os clientes cadastrados.
    Permite a busca de clientes por nome completo.
    """
    query = request.GET.get('q')
    if query:
        clientes_list = Cliente.objects.filter(nome_completo__icontains=query).order_by('nome_completo')
    else:
        clientes_list = Cliente.objects.all().order_by('nome_completo')

    paginator = Paginator(clientes_list, 12) # 12 clients per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'clientes_cadastrados.html', {'page_obj': page_obj, 'query': query})

@login_required
def cliente_add_view(request):
    """
    Permite adicionar um novo cliente através de um formulário completo.
    """
    if request.method == 'POST':
        form = ClienteFullForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('clientes_cadastrados')
    else:
        form = ClienteFullForm()
    return render(request, 'cliente_edit.html', {'form': form})

@login_required
def cliente_edit_view(request, pk):
    """
    Permite editar as informações de um cliente existente.
    """
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteFullForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('clientes_cadastrados')
    else:
        form = ClienteFullForm(instance=cliente)
    return render(request, 'cliente_edit.html', {'form': form})

@login_required
def especificadores_cadastrados(request):
    """
    Exibe uma lista paginada de todos os especificadores cadastrados.
    Permite a busca de especificadores por nome completo.
    """
    query = request.GET.get('q')
    if query:
        especificadores_list = Especificador.objects.filter(nome_completo__icontains=query).order_by('nome_completo')
    else:
        especificadores_list = Especificador.objects.all().order_by('nome_completo')

    paginator = Paginator(especificadores_list, 12) # 12 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'especificadores_cadastrados.html', {'page_obj': page_obj, 'query': query})

@login_required
def especificador_add_view(request):
    """
    Permite adicionar um novo especificador. Apenas administradores e gerentes têm permissão.
    """
    if request.user.role not in ['administrador', 'gerente']:
        messages.error(request, 'Você não tem permissão para adicionar especificadores.')
        return redirect('especificadores_cadastrados')
    
    if request.method == 'POST':
        form = EspecificadorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Especificador adicionado com sucesso.')
            return redirect('especificadores_cadastrados')
    else:
        form = EspecificadorForm()
    return render(request, 'especificador_edit.html', {'form': form})

@login_required
def especificador_edit_view(request, pk):
    """
    Permite editar as informações de um especificador existente. Apenas administradores e gerentes têm permissão.
    """
    if request.user.role not in ['administrador', 'gerente']:
        messages.error(request, 'Você não tem permissão para editar especificadores.')
        return redirect('especificadores_cadastrados')

    especificador = get_object_or_404(Especificador, pk=pk)
    if request.method == 'POST':
        form = EspecificadorForm(request.POST, instance=especificador)
        if form.is_valid():
            form.save()
            messages.success(request, 'Especificador atualizado com sucesso.')
            return redirect('especificadores_cadastrados')
    else:
        form = EspecificadorForm(instance=especificador)
    return render(request, 'especificador_edit.html', {'form': form})

@login_required
def download_template_view(request):
    """
    Permite que administradores baixem um template de planilha Excel
    para importação de orçamentos, pré-preenchido com usuários.
    """
    if request.user.role != 'administrador':
        return redirect('home')

    required_columns = [
        'usuario', 'data_solicitracao', 'especificador', 'categoria', 'nome_cliente',
        'numero_orcamento', 'data_envio', 'valor_orcamento', 'termometro',
        'data_previsao_fechamento', 'semana_previsao_fechamento', 'etapa', 'jornada_cliente'
    ]
    
    users = User.objects.all().values_list('username', flat=True)
    user_df = pd.DataFrame(users, columns=['usuario'])
    
    # Create a DataFrame with all required columns, but only the 'usuario' column filled
    df = pd.DataFrame(columns=required_columns)
    df['usuario'] = user_df['usuario']

    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    writer.close()
    output.seek(0)
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="template_orcamentos.xlsx"'
    
    return response

@login_required
def importar_orcamentos(request):
    """
    Permite que administradores importem orçamentos de um arquivo .xlsx.
    Processa o arquivo, cria ou atualiza orçamentos, clientes e especificadores.
    """
    if request.user.role != 'administrador':
        return redirect('home')

    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, 'Nenhum arquivo selecionado.')
            return redirect('importar_orcamentos')

        file = request.FILES['file']
        if not file.name.endswith('.xlsx'):
            messages.error(request, 'Arquivo inválido. Por favor, selecione um arquivo .xlsx')
            return redirect('importar_orcamentos')

        try:
            df = pd.read_excel(file)
            required_columns = [
                'data_solicitracao', 'especificador', 'categoria', 'nome_cliente',
                'numero_orcamento', 'data_envio', 'valor_orcamento', 'termometro',
                'data_previsao_fechamento', 'semana_previsao_fechamento', 'etapa', 'usuario'
            ]
            if not all(col in df.columns for col in required_columns):
                messages.error(request, f'A planilha deve conter as seguintes colunas: {required_columns}')
                return redirect('importar_orcamentos')

            for index, row in df.iterrows():
                # Get or create related objects
                especificador, _ = Especificador.objects.get_or_create(nome_completo=row['especificador'])
                cliente, _ = Cliente.objects.get_or_create(nome_completo=row['nome_cliente'])
                try:
                    user = User.objects.get(username=row['usuario'])
                except User.DoesNotExist:
                    messages.error(request, f"Usuário '{row['usuario']}' não encontrado. O orçamento da linha {index + 2} não foi importado.")
                    continue

                # Check if orcamento already exists
                if Orcamento.objects.filter(numero_orcamento=row['numero_orcamento']).exists():
                    messages.warning(request, f"Orçamento com número '{row['numero_orcamento']}' já existe. Linha {index + 2} não foi importada.")
                    continue

                Orcamento.objects.create(
                    data_solicitacao=row['data_solicitracao'],
                    especificador=especificador,
                    categoria=row['categoria'],
                    nome_cliente=cliente,
                    numero_orcamento=row['numero_orcamento'],
                    data_envio=row.get('data_envio'),
                    valor_orcamento=row['valor_orcamento'],
                    termometro=row['termometro'],
                    data_previsao_fechamento=row['data_previsao_fechamento'],
                    semana_previsao_fechamento=row['semana_previsao_fechamento'],
                    etapa=row['etapa'],
                    usuario=user,
                )
            messages.success(request, 'Orçamentos importados com sucesso!')

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao processar o arquivo: {e}')

        return redirect('importar_orcamentos')

    return render(request, 'importar_orcamentos.html')

@login_required
def orcamentos_fechados_view(request):
    """
    Exibe uma lista de orçamentos fechados e ganhos, com opções de filtragem
    por cliente, consultor, loja, mês, ano e especificador.
    Disponível para gerentes e administradores.
    """
    user = request.user
    if user.role not in ['gerente', 'administrador']:
        return redirect('home')

    orcamentos = Orcamento.objects.filter(etapa='Fechada e Ganha')

    # Get filter parameters
    selected_cliente = request.GET.get('cliente')
    selected_consultor = request.GET.get('consultor')
    selected_loja = request.GET.get('loja')
    selected_month = request.GET.get('month')
    selected_year = request.GET.get('year')
    selected_especificador = request.GET.get('especificador')

    # Apply filters
    if selected_cliente:
        orcamentos = orcamentos.filter(nome_cliente__id=selected_cliente)
    if selected_consultor:
        orcamentos = orcamentos.filter(usuario__id=selected_consultor)
    if selected_loja:
        orcamentos = orcamentos.filter(usuario__loja__id=selected_loja)
    if selected_month:
        orcamentos = orcamentos.filter(data_fechada_ganha__month=selected_month)
    if selected_year:
        orcamentos = orcamentos.filter(data_fechada_ganha__year=selected_year)
    if selected_especificador:
        orcamentos = orcamentos.filter(especificador__id=selected_especificador)

    # Get filter options
    all_clientes = Cliente.objects.filter(orcamento__in=orcamentos).distinct()
    all_consultores = User.objects.filter(role='consultor', orcamento__in=orcamentos).distinct()
    all_especificadores = Especificador.objects.filter(orcamento__in=orcamentos).distinct()
    all_lojas = Loja.objects.all() # Show all stores for filtering
    available_months = Orcamento.objects.filter(etapa='Fechada e Ganha').dates('data_fechada_ganha', 'month', order='ASC')
    available_years = Orcamento.objects.filter(etapa='Fechada e Ganha').dates('data_fechada_ganha', 'year', order='DESC')
    
    months_choices = {
        '1': 'Janeiro', '2': 'Fevereiro', '3': 'Março', '4': 'Abril',
        '5': 'Maio', '6': 'Junho', '7': 'Julho', '8': 'Agosto',
        '9': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }

    context = {
        'orcamentos': orcamentos,
        'all_clientes': all_clientes,
        'all_consultores': all_consultores,
        'all_especificadores': all_especificadores,
        'all_lojas': all_lojas,
        'available_months': available_months,
        'available_years': [d.year for d in available_years],
        'months_choices': months_choices,
        'selected_cliente': selected_cliente,
        'selected_consultor': selected_consultor,
        'selected_loja': selected_loja,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'selected_especificador': selected_especificador,
    }
    return render(request, 'orcamentos_fechados.html', context)

def search_clientes(request):
    """
    Endpoint AJAX para buscar clientes por nome completo.
    Retorna uma lista de clientes que correspondem à query para uso em campos de seleção dinâmica.
    """
    query = request.GET.get('q', '')
    clientes = Cliente.objects.filter(nome_completo__icontains=query)[:10]
    results = [{'id': cliente.id, 'text': cliente.nome_completo} for cliente in clientes]
    return JsonResponse({'results': results})

def search_especificadores(request):
    """
    Endpoint AJAX para buscar especificadores por nome completo.
    Retorna uma lista de especificadores que correspondem à query para uso em campos de seleção dinâmica.
    """
    query = request.GET.get('q', '')
    especificadores = Especificador.objects.filter(nome_completo__icontains=query)[:10]
    results = [{'id': esp.id, 'text': esp.nome_completo} for esp in especificadores]
    return JsonResponse({'results': results})

@login_required
def notifications_view(request):
    """
    Exibe as notificações do usuário logado e as marca como lidas.
    """
    notifications = Notification.objects.filter(recipient=request.user)
    # Mark notifications as read when the user views them
    notifications.update(is_read=True)
    return render(request, 'notifications.html', {'notifications': notifications})

@login_required
def gerente_forecast_view(request):
    """
    Exibe a página de forecast para gerentes, mostrando orçamentos elegíveis
    e orçamentos já no forecast de sua loja. Permite filtrar e gerenciar.
    """
    if request.user.role != 'gerente':
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('home')

    gerente_loja = request.user.loja
    if not gerente_loja:
        messages.error(request, 'Você não está associado a nenhuma loja.')
        return redirect('home')

    # Get filter parameters
    source = request.GET.get('source')
    selected_year = request.GET.get('year')
    selected_month = request.GET.get('month')
    selected_especificador = request.GET.get('especificador')
    selected_cliente = request.GET.get('cliente')
    selected_etapa = request.GET.get('etapa')
    selected_termometro = request.GET.get('termometro')

    # Base querysets
    base_orcamentos = Orcamento.objects.filter(usuario__loja=gerente_loja)
    orcamentos_in_forecast = base_orcamentos.filter(is_forecast=True).order_by('-data_previsao_fechamento')
    orcamentos_elegiveis = base_orcamentos.filter(is_forecast=False, etapa__in=['Especificação', 'Follow-up', 'Em Negociação'])

    # Apply filters based on the source
    if source == 'elegiveis':
        if selected_year:
            orcamentos_elegiveis = orcamentos_elegiveis.filter(data_previsao_fechamento__year=selected_year)
        if selected_month:
            orcamentos_elegiveis = orcamentos_elegiveis.filter(data_previsao_fechamento__month=selected_month)
        if selected_especificador:
            orcamentos_elegiveis = orcamentos_elegiveis.filter(especificador__id=selected_especificador)
        if selected_cliente:
            orcamentos_elegiveis = orcamentos_elegiveis.filter(nome_cliente__id=selected_cliente)
        if selected_etapa:
            orcamentos_elegiveis = orcamentos_elegiveis.filter(etapa=selected_etapa)
        if selected_termometro:
            orcamentos_elegiveis = orcamentos_elegiveis.filter(termometro=selected_termometro)
    elif source == 'forecast':
        if selected_year:
            orcamentos_in_forecast = orcamentos_in_forecast.filter(data_previsao_fechamento__year=selected_year)
        if selected_month:
            orcamentos_in_forecast = orcamentos_in_forecast.filter(data_previsao_fechamento__month=selected_month)
        if selected_especificador:
            orcamentos_in_forecast = orcamentos_in_forecast.filter(especificador__id=selected_especificador)
        if selected_cliente:
            orcamentos_in_forecast = orcamentos_in_forecast.filter(nome_cliente__id=selected_cliente)
        if selected_etapa:
            orcamentos_in_forecast = orcamentos_in_forecast.filter(etapa=selected_etapa)
        if selected_termometro:
            orcamentos_in_forecast = orcamentos_in_forecast.filter(termometro=selected_termometro)

    # Get filter options from the base queryset to show all possibilities
    available_years = base_orcamentos.dates('data_previsao_fechamento', 'year', order='DESC')
    all_especificadores = Especificador.objects.filter(orcamento__in=base_orcamentos).distinct()
    all_clientes = Cliente.objects.filter(orcamento__in=base_orcamentos).distinct()
    stage_choices = Orcamento.STAGE_CHOICES
    thermometer_choices = Orcamento.THERMOMETER_CHOICES
    months_choices = {
        '1': 'Janeiro', '2': 'Fevereiro', '3': 'Março', '4': 'Abril',
        '5': 'Maio', '6': 'Junho', '7': 'Julho', '8': 'Agosto',
        '9': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }

    context = {
        'orcamentos_in_forecast': orcamentos_in_forecast,
        'orcamentos_elegiveis': orcamentos_elegiveis.order_by('-data_previsao_fechamento'),
        'available_years': [d.year for d in available_years],
        'months_choices': months_choices,
        'all_especificadores': all_especificadores,
        'all_clientes': all_clientes,
        'stage_choices': stage_choices,
        'thermometer_choices': thermometer_choices,
        'selected_year': int(selected_year) if selected_year else None,
        'selected_month': int(selected_month) if selected_month else None,
        'selected_especificador': selected_especificador,
        'selected_cliente': selected_cliente,
        'selected_etapa': selected_etapa,
        'selected_termometro': selected_termometro,
    }
    return render(request, 'gerente_forecast.html', context)

@login_required
def admin_forecast_dashboard_view(request):
    """
    Exibe o dashboard de forecast para administradores, consolidando dados de forecast
    de todas as lojas. Inclui análise de motivos de perda e permite filtros.
    """
    if request.user.role != 'administrador':
        messages.error(request, 'Você não tem permissão para acessar esta página.')
        return redirect('home')

    # Get filter parameters from request
    selected_year = request.GET.get('year', str(datetime.now().year))
    selected_month = request.GET.get('month', str(datetime.now().month))
    selected_week = request.GET.get('week')

    lojas = Loja.objects.all()
    dashboard_data = []
    grand_total_forecast = 0

    # Base queryset for all forecast budgets
    base_forecast_orcamentos = Orcamento.objects.filter(is_forecast=True).select_related('nome_cliente', 'especificador')

    # Apply filters to the base queryset
    if selected_year:
        base_forecast_orcamentos = base_forecast_orcamentos.filter(data_previsao_fechamento__year=selected_year)
    if selected_month:
        base_forecast_orcamentos = base_forecast_orcamentos.filter(data_previsao_fechamento__month=selected_month)
    if selected_week:
        base_forecast_orcamentos = base_forecast_orcamentos.filter(semana_previsao_fechamento=selected_week)

    for loja in lojas:
        # Get the filtered forecast budgets for the specific store
        forecast_orcamentos = base_forecast_orcamentos.filter(usuario__loja=loja)
        
        valor_total_carteira = forecast_orcamentos.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
        orcamentos_count = forecast_orcamentos.count()
        grand_total_forecast += valor_total_carteira

        dashboard_data.append({
            'loja_id': loja.id,
            'loja_nome': loja.nome,
            'valor_total_carteira': valor_total_carteira,
            'orcamentos_count': orcamentos_count,
            'orcamentos': forecast_orcamentos,
        })

    # Análise de motivos de perda (geral, não por loja e não filtrado por data do forecast)
    motivos_perda = Orcamento.objects.filter(etapa='Perdida').exclude(motivo_perda__isnull=True).exclude(motivo_perda__exact='').values('motivo_perda').annotate(
        count=Count('id')
    ).order_by('-count')

    # Filter options
    available_years = Orcamento.objects.filter(is_forecast=True).dates('data_previsao_fechamento', 'year', order='DESC')
    months_choices = {
        '1': 'Janeiro', '2': 'Fevereiro', '3': 'Março', '4': 'Abril',
        '5': 'Maio', '6': 'Junho', '7': 'Julho', '8': 'Agosto',
        '9': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }
    available_weeks = Orcamento.objects.filter(is_forecast=True).values_list('semana_previsao_fechamento', flat=True).distinct().order_by('semana_previsao_fechamento')

    context = {
        'dashboard_data': dashboard_data,
        'grand_total_forecast': grand_total_forecast,
        'motivos_perda': motivos_perda,
        'available_years': [d.year for d in available_years],
        'months_choices': months_choices,
        'available_weeks': available_weeks,
        'selected_year': int(selected_year) if selected_year else None,
        'selected_month': int(selected_month) if selected_month else None,
        'selected_week': selected_week,
    }
    return render(request, 'admin_forecast_dashboard.html', context)

@login_required
def get_orcamento_details(request, pk):
    """
    Endpoint AJAX para retornar detalhes de um orçamento específico.
    Utilizado para preencher modais de edição ou visualização de detalhes.
    """
    try:
        orcamento = get_object_or_404(Orcamento, pk=pk)

        # Manually build the dictionary to ensure correct serialization
        orcamento_data = {
            'id': orcamento.id,
            'numero_orcamento': orcamento.numero_orcamento,
            'valor_orcamento': str(orcamento.valor_orcamento),
            'data_solicitacao': orcamento.data_solicitacao.strftime('%Y-%m-%d') if orcamento.data_solicitacao else '',
            'data_envio': orcamento.data_envio.strftime('%Y-%m-%d') if orcamento.data_envio else '',
            'data_previsao_fechamento': orcamento.data_previsao_fechamento.strftime('%Y-%m-%d') if orcamento.data_previsao_fechamento else '',
            'etapa': orcamento.etapa,
            'termometro': orcamento.termometro,
            'categoria': orcamento.categoria,
            'motivo_perda': orcamento.motivo_perda,
            # Handle ForeignKey fields by sending their ID
            'nome_cliente': orcamento.nome_cliente.id if orcamento.nome_cliente else None,
            'especificador': orcamento.especificador.id if orcamento.especificador else None,
        }

        # Get choices for select fields in a more JS-friendly format
        choices = {
            'etapa': [{'value': c[0], 'label': c[1]} for c in Orcamento.STAGE_CHOICES],
            'termometro': [{'value': c[0], 'label': c[1]} for c in Orcamento.THERMOMETER_CHOICES],
            'categoria': [{'value': c[0], 'label': c[1]} for c in Orcamento.CATEGORY_CHOICES],
            'motivo_perda': [{'value': c[0], 'label': c[1]} for c in Orcamento.MOTIVO_PERDA_CHOICES],
        }

        # Get related data for dropdowns
        related_data = {
            'clientes': list(Cliente.objects.values('id', 'nome_completo')),
            'especificadores': list(Especificador.objects.values('id', 'nome_completo')),
        }

        data = {
            'orcamento': orcamento_data,
            'choices': choices,
            'related_data': related_data,
        }
        return JsonResponse(data)
    except Exception as e:
        # Log the error for debugging and return a proper error response
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
def update_orcamento_details(request, pk):
    """
    Endpoint AJAX para atualizar detalhes de um orçamento específico.
    Processa dados JSON, valida com OrcamentoForm e salva as alterações.
    """
    try:
        orcamento = get_object_or_404(Orcamento, pk=pk)
        data = json.loads(request.body)

        # Use a form to validate and save the data
        form = OrcamentoForm(data, instance=orcamento)
        
        if form.is_valid():
            updated_orcamento = form.save()

            # Prepare data to send back to the frontend for UI update
            updated_data = {
                'id': updated_orcamento.id,
                'valor_orcamento': str(updated_orcamento.valor_orcamento),
                'nome_cliente_nome': updated_orcamento.nome_cliente.nome_completo if updated_orcamento.nome_cliente else '-',
                'especificador_nome': updated_orcamento.especificador.nome_completo if updated_orcamento.especificador else '',
                'etapa': updated_orcamento.etapa,
            }
            return JsonResponse({'status': 'success', 'updated_data': updated_data})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
def update_forecast_status(request):
    """
    Endpoint AJAX para atualizar o status 'is_forecast' de um orçamento.
    Disponível apenas para gerentes, com verificação de permissão.
    """
    if request.user.role != 'gerente':
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

    try:
        data = json.loads(request.body)
        orcamento_id = data.get('orcamento_id')
        status = data.get('status')

        if orcamento_id is None or status is None:
            return JsonResponse({'status': 'error', 'message': 'Missing parameters.'}, status=400)

        orcamento = get_object_or_404(Orcamento, id=orcamento_id)

        # Security check: ensure the budget belongs to the manager's store
        if orcamento.usuario.loja != request.user.loja:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized.'}, status=403)

        orcamento.is_forecast = status
        orcamento.save()

        return JsonResponse({'status': 'success', 'message': 'Forecast status updated.'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)