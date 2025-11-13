from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from .models import Orcamento, Loja, User, Cliente, Especificador, JornadaClienteHistorico
from django.shortcuts import get_object_or_404
from django import forms
from .models import User, Orcamento, Cliente, Especificador, JornadaClienteHistorico
import pandas as pd
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count
import io
from datetime import datetime
from django.db import models
from django.utils import timezone

class UserRegistrationForm(forms.ModelForm):
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
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'role', 'loja']

class OrcamentoForm(forms.ModelForm):
    class Meta:
        model = Orcamento
        exclude = ['usuario']

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = '__all__'

class EspecificadorForm(forms.ModelForm):
    class Meta:
        model = Especificador
        fields = '__all__'

class JornadaClienteHistoricoForm(forms.ModelForm):
    class Meta:
        model = JornadaClienteHistorico
        fields = ['comentario']

class ClienteFullForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = '__all__'

@login_required
def home_view(request):
    if request.user.is_authenticated:
        if request.user.role == 'consultor':
            return redirect('consultor_dashboard')
        elif request.user.role == 'gerente':
            return redirect('gerente_dashboard')
        elif request.user.role == 'administrador':
            return redirect('administrador_dashboard')
    return redirect('login')

class LojasView(ListView):
    model = Loja
    template_name = 'lojas.html'
    context_object_name = 'lojas'

def register_user_view(request):
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
    logout(request)
    return redirect('login')

class UserListView(ListView):
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
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('user_list')
    else:
        form = UserEditForm(instance=user)
    
    lojas = Loja.objects.all()
    return render(request, 'user_edit.html', {'form': form, 'user': user, 'lojas': lojas})

def user_deactivate_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.is_active = False
    user.save()
    return redirect('user_list')

def user_activate_view(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.is_active = True
    user.save()
    return redirect('user_list')

@login_required
def consultor_dashboard(request):
    orcamentos = Orcamento.objects.filter(usuario=request.user)

    # Get filter parameters
    selected_month = request.GET.get('month')
    selected_cliente = request.GET.get('cliente')
    selected_especificador = request.GET.get('especificador')
    selected_semanas = request.GET.getlist('semana')

    # Apply filters
    if selected_month:
        orcamentos = orcamentos.filter(data_previsao_fechamento__month=selected_month)
    if selected_cliente:
        orcamentos = orcamentos.filter(nome_cliente__id=selected_cliente)
    if selected_especificador:
        orcamentos = orcamentos.filter(especificador__id=selected_especificador)
    if selected_semanas:
        orcamentos = orcamentos.filter(semana_previsao_fechamento__in=selected_semanas)

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
    }
    return render(request, 'consultor_dashboard.html', context)

@login_required
def consultor_criar_orcamento(request):
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
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            return JsonResponse({'id': cliente.id, 'nome_completo': cliente.nome_completo})
    return JsonResponse({'error': 'Invalid request'}, status=400)

def add_especificador(request):
    if request.method == 'POST':
        form = EspecificadorForm(request.POST)
        if form.is_valid():
            especificador = form.save()
            return JsonResponse({'id': especificador.id, 'nome_completo': especificador.nome_completo})
        else:
            return JsonResponse({'error': 'Formulário inválido', 'errors': form.errors}, status=400)

@login_required
def edit_orcamento(request, pk):
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
    if 'debug' in request.GET:
        gerente_loja = request.user.loja
        orcamentos = Orcamento.objects.filter(usuario__loja=gerente_loja)
        consultant_performance = orcamentos.values('usuario__username').annotate(
            total_carteira=Sum('valor_orcamento'),
            total_vendido=Sum('valor_orcamento', filter=models.Q(etapa='Fechada e Ganha'))
            ).order_by('-total_vendido')
        
        consultant_labels = [item['usuario__username'] for item in consultant_performance]
        consultant_carteira = [item['total_carteira'] for item in consultant_performance]
        consultant_vendido = [item['total_vendido'] for item in consultant_performance]
        weekly_forecast = orcamentos.values('semana_previsao_fechamento').annotate(
            total_valor=Sum('valor_orcamento'),
            count=Count('id')
        ).order_by('semana_previsao_fechamento')
        weekly_forecast_labels = [item['semana_previsao_fechamento'] for item in weekly_forecast]
        weekly_forecast_values = [item['total_valor'] for item in weekly_forecast]
        weekly_forecast_counts = [item['count'] for item in weekly_forecast]
        debug_data = {
            'gerente_loja': gerente_loja.nome if gerente_loja else None,
            'orcamentos_count': orcamentos.count(),
            'consultant_labels': consultant_labels,
            'consultant_carteira': [float(c) if c else 0 for c in consultant_carteira],
            'consultant_vendido': [float(v) if v else 0 for v in consultant_vendido],
            'weekly_forecast_labels': weekly_forecast_labels,
            'weekly_forecast_values': [float(v) if v else 0 for v in weekly_forecast_values],
            'weekly_forecast_counts': weekly_forecast_counts,
        }
        return JsonResponse(debug_data)

    # Get the current manager's loja
    gerente_loja = request.user.loja

    # Get filter parameters from request
    selected_year = request.GET.get('year', str(datetime.now().year))
    selected_month = request.GET.get('month', str(datetime.now().month))

    # Start with orcamentos from the manager's loja
    orcamentos = Orcamento.objects.filter(usuario__loja=gerente_loja)

    # Apply filters
    if selected_year:
        orcamentos = orcamentos.filter(data_previsao_fechamento__year=selected_year)
    if selected_month:
        orcamentos = orcamentos.filter(data_previsao_fechamento__month=selected_month)

    # Calculate metrics for open budgets
    orcamentos_abertos = orcamentos.exclude(etapa__in=['Fechada e Ganha', 'Perdida'])
    total_orcamento = orcamentos_abertos.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    total_orcamento_quantidade = orcamentos_abertos.count()

    orcamentos_quentes = orcamentos_abertos.filter(termometro='Quente').count()
    total_quentes_value = orcamentos_abertos.filter(termometro='Quente').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    orcamentos_mornos = orcamentos_abertos.filter(termometro='Morno').count()
    total_mornos_value = orcamentos_abertos.filter(termometro='Morno').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    orcamentos_frios = orcamentos_abertos.filter(termometro='Frio').count()
    total_frios_value = orcamentos_abertos.filter(termometro='Frio').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    # Calculate metrics for "Fechada e Ganha"
    orcamentos_ganhos = orcamentos.filter(etapa='Fechada e Ganha')
    total_fechada_ganha_value = orcamentos_ganhos.aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0
    total_fechada_ganha_quantidade = orcamentos_ganhos.count()

    # Monthly metrics
    total_perdido_mes_quantidade = orcamentos.filter(etapa='Perdida').count()
    total_perdido_mes_valor = orcamentos.filter(etapa='Perdida').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

    # Chart data
    consultants = User.objects.filter(loja=gerente_loja, role='consultor')
    
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

    consultant_labels = [item['username'] for item in consultant_performance]
    consultant_carteira = [float(item['total_carteira']) for item in consultant_performance]
    consultant_vendido = [float(item['total_vendido']) for item in consultant_performance]

    weekly_forecast = orcamentos.values('semana_previsao_fechamento').annotate(
        total_valor=Sum('valor_orcamento'),
        count=Count('id')
    ).order_by('semana_previsao_fechamento')

    weekly_forecast_labels = [item['semana_previsao_fechamento'] for item in weekly_forecast]
    weekly_forecast_values = [float(item['total_valor']) if item['total_valor'] else 0 for item in weekly_forecast]
    weekly_forecast_counts = [item['count'] for item in weekly_forecast]
    
    available_years = Orcamento.objects.filter(usuario__loja=gerente_loja).dates('data_previsao_fechamento', 'year', order='DESC')
    months_choices = {
        '1': 'Janeiro', '2': 'Fevereiro', '3': 'Março', '4': 'Abril',
        '5': 'Maio', '6': 'Junho', '7': 'Julho', '8': 'Agosto',
        '9': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }

    context = {
        'orcamentos': orcamentos,
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
        'consultant_labels': consultant_labels,
        'consultant_carteira': consultant_carteira,
        'consultant_vendido': consultant_vendido,
        'weekly_forecast_labels': weekly_forecast_labels,
        'weekly_forecast_values': weekly_forecast_values,
        'weekly_forecast_counts': weekly_forecast_counts,
        'available_years': [d.year for d in available_years],
        'selected_year': selected_year,
        'months_choices': months_choices,
        'selected_month': selected_month,
    }

    return render(request, 'gerente_dashboard.html', context)

@login_required
def gerente_criar_orcamento(request):
    if request.method == 'POST':
        form = OrcamentoForm(request.POST)
        if form.is_valid():
            orcamento = form.save(commit=False)
            orcamento.usuario = request.user
            orcamento.save()
            return redirect('gerente_dashboard')
    else:
        form = OrcamentoForm()
    return render(request, 'gerente_criar_orcamento.html', {'form': form})

@login_required
def meus_clientes_view(request):
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
    selected_termometro = request.GET.get('termometro')

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
        orcamentos = orcamentos.filter(termometro=selected_termometro)

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
        orcamento.jornada_completa = sorted(jornada_completa, key=lambda x: x['data'], reverse=True)

    context = {
        'orcamentos': orcamentos_list,
        'available_years': [d.year for d in available_years],
        'all_especificadores': all_especificadores,
        'all_clientes': all_clientes,
        'stage_choices': stage_choices,
        'thermometer_choices': thermometer_choices,
    }
    return render(request, 'meus_clientes.html', context)

@login_required
def todos_orcamentos_view(request):
    user = request.user
    base_orcamentos = Orcamento.objects.all()

    if user.role == 'gerente':
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

    context = {
        'orcamentos': orcamentos,
        'todos_orcamentos_url_name': todos_orcamentos_url_name,
        'available_years': [d.year for d in available_years],
        'all_especificadores': all_especificadores,
        'all_clientes': all_clientes,
        'stage_choices': stage_choices,
        'thermometer_choices': thermometer_choices,
        'all_lojas': all_lojas,
        'selected_lojas': [int(x) for x in selected_lojas],
        'selected_cliente_obj': selected_cliente_obj,
        'selected_especificador_obj': selected_especificador_obj,
    }
    return render(request, 'todos_orcamentos.html', context)

@login_required
def marcar_como_ganho(request, pk):
    orcamento = get_object_or_404(Orcamento, pk=pk)
    orcamento.etapa = 'Fechada e Ganha'
    orcamento.data_fechada_ganha = timezone.now().date()
    orcamento.save()
    return redirect(request.META.get('HTTP_REFERER', 'home'))

@login_required
def consultor_orcamentos_fechados_ganhos(request):
    orcamentos = Orcamento.objects.filter(usuario=request.user, etapa='Fechada e Ganha')
    return render(request, 'consultor_orcamentos_fechados_ganhos.html', {'orcamentos': orcamentos})

@login_required
def reverter_orcamento_ganho(request, pk):
    orcamento = get_object_or_404(Orcamento, pk=pk)
    orcamento.etapa = 'Follow-up'
    orcamento.save()
    return redirect(request.META.get('HTTP_REFERER', 'home'))

from django.db.models import Sum, Count
from datetime import datetime

@login_required
def administrador_dashboard(request):
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

    total_perdido_mes_quantidade = Orcamento.objects.filter(etapa='Perdida').count()
    total_perdido_mes_valor = Orcamento.objects.filter(etapa='Perdida').aggregate(Sum('valor_orcamento'))['valor_orcamento__sum'] or 0

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
    ).order_by('-total_comprado')[:10]

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
    if request.method == 'POST':
        form = ClienteFullForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            return JsonResponse({'id': cliente.id, 'nome_completo': cliente.nome_completo})
        else:
            return JsonResponse({'error': 'Formulário inválido', 'errors': form.errors}, status=400)
    return render(request, 'add_cliente_full.html', {'form': ClienteFullForm()})

@login_required
def clientes_cadastrados(request):
    query = request.GET.get('q')
    if query:
        clientes = Cliente.objects.filter(nome_completo__icontains=query)
    else:
        clientes = Cliente.objects.all()

    return render(request, 'clientes_cadastrados.html', {'page_obj': clientes, 'query': query})

@login_required
def cliente_edit_view(request, pk):
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
def download_template_view(request):
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
    user = request.user
    if user.role not in ['gerente', 'administrador']:
        return redirect('home')

    orcamentos = Orcamento.objects.filter(etapa='Fechada e Ganha')

    # Apply role-based filtering first
    if user.role == 'gerente':
        orcamentos = orcamentos.filter(usuario__loja=user.loja)

    # Get filter parameters
    selected_cliente = request.GET.get('cliente')
    selected_consultor = request.GET.get('consultor')
    selected_loja = request.GET.get('loja')
    selected_month = request.GET.get('month')
    selected_year = request.GET.get('year')

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

    # Get filter options
    all_clientes = Cliente.objects.filter(orcamento__in=orcamentos).distinct()
    all_consultores = User.objects.filter(role='consultor', orcamento__in=orcamentos).distinct()
    all_lojas = Loja.objects.filter(user__orcamento__in=orcamentos).distinct()
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
        'all_lojas': all_lojas,
        'available_months': available_months,
        'available_years': [d.year for d in available_years],
        'months_choices': months_choices,
        'selected_cliente': selected_cliente,
        'selected_consultor': selected_consultor,
        'selected_loja': selected_loja,
        'selected_month': selected_month,
        'selected_year': selected_year,
    }
    return render(request, 'orcamentos_fechados.html', context)

def search_clientes(request):
    query = request.GET.get('q', '')
    clientes = Cliente.objects.filter(nome_completo__icontains=query)[:10]
    results = [{'id': cliente.id, 'text': cliente.nome_completo} for cliente in clientes]
    return JsonResponse({'results': results})

def search_especificadores(request):
    query = request.GET.get('q', '')
    especificadores = Especificador.objects.filter(nome_completo__icontains=query)[:10]
    results = [{'id': esp.id, 'text': esp.nome_completo} for esp in especificadores]
    return JsonResponse({'results': results})
