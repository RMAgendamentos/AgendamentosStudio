from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, date, timedelta
from django.db.models import F, Q
from django.core.mail import send_mail
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from .forms import AgendamentoForm, HorarioDisponivelForm, AgendamentoAdminForm
from .models import HorarioDisponivel, Agendamento, Profissional, Servico
from .forms import (
    AgendamentoForm, 
    HorarioDisponivelForm, 
    AgendamentoAdminForm, 
    ServicoForm
)
from django.core.mail import EmailMultiAlternatives
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.db import models
from django.utils.dateparse import parse_date
import json

def index(request):
    """Renderiza a nova landing page (index.html)"""
    return render(request, 'LihStudio/index.html')

# --- NOVO DECORATOR ---
def only_staff(view_func):
    """
    Decorator que restringe o acesso a usuários que são, no mínimo, 'staff'.
    Isso inclui 'staff' e 'superusuários'.
    """
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Você precisa fazer login para acessar esta área.')
            return redirect('login')
        # AQUI ESTÁ A MUDANÇA: de 'is_superuser' para 'is_staff'
        if not request.user.is_staff:
            messages.error(request, 'Acesso restrito à equipe do studio.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# ------------------------- VIEWS PÚBLICAS -------------------------

def home(request):
    return render(request, 'LihStudio/home.html')

def sucesso_view(request):
    return render(request, 'LihStudio/sucesso.html')

def agendar_servico(request):
    # -------------------------------------------------------------
    # 1.  Pega o slug do profissional e a data vindos da URL (?profissional=...&data=...)
    # -------------------------------------------------------------
    prof_slug = request.GET.get("profissional")        # ex.: 'elisama'
    data_str  = request.GET.get("data")                # ex.: '2025-06-05'

    # Converte slug → objeto ou None
    profissional_obj = (
        Profissional.objects.filter(slug=prof_slug, ativo=True).first()
        if prof_slug else None
    )

    # -------------------------------------------------------------
    # 2.  POST  → grava o agendamento
    # -------------------------------------------------------------
    if request.method == "POST":
        form = AgendamentoForm(request.POST)

        if form.is_valid():
            ag = form.save(commit=False)

            # --- INÍCIO DA CORREÇÃO (Versão Segura para SQLite) ---
            try:
                with transaction.atomic():
                    # 1. Tenta "capturar" o horário de forma atômica.
                    #    Este comando .update() só funciona se o horário
                    #    for encontrado E "disponivel" for True.
                    updated_rows = HorarioDisponivel.objects.filter(
                        id=ag.hora.id,
                        disponivel=True
                    ).update(disponivel=False)

                    # 2. Se 'updated_rows' for 0, significa que o horário
                    #    ou não existe ou JÁ ESTAVA 'disponivel=False'
                    #    (ou seja, outra pessoa pegou 1ms antes).
                    if updated_rows == 0:
                        messages.error(request, "Este horário já foi reservado por outra pessoa.")
                        return redirect(request.path)

                    # 3. Se 'updated_rows' == 1: NÓS VENCEMOS.
                    #    O horário é nosso. Podemos salvar o agendamento.
                    if not ag.valor_total and ag.servico:
                        ag.valor_total = ag.servico.preco
                    
                    ag.contabilizar = True
                    ag.save() 
                
                # 4. Fim da transação.
            
            except HorarioDisponivel.DoesNotExist:
                messages.error(request, "Ocorreu um erro ao reservar o horário. Tente novamente.")
                return redirect(request.path)
            # --- FIM DA CORREÇÃO ---

            # --- e-mail (mantive seu conteúdo) -------------------
            subject = "✅ Sua Solicitação de Agendamento no RM Studio Foi Recebida!"
            text_content = f"""
            Olá, {ag.nome}!

            Agradecemos muito por agendar conosco no RM Studio!

            Seu agendamento foi recebido e está em análise. Em breve, entraremos em contato para confirmar sua reserva.

            📅 Detalhes da sua solicitação:
            Data: {ag.hora.data.strftime('%d/%m/%Y')}
            Horário: {ag.hora.hora.strftime('%H:%M')}
            Serviço: {ag.get_servico_display()}

            Fique de olho na sua caixa de entrada para a confirmação!

            Caso precise alterar ou cancelar, por favor, responda este e-mail ou entre em contato pelos nossos canais.

            Atenciosamente,
            Equipe RM Studio
            ✉️ contato@rmstudio.com
            📞 (83) 99999-9999
            """

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: 'Arial', sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4; }}
                    .container {{ background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                    .header {{ background-color: #d63384; color: white; padding: 25px 20px; text-align: center; }}
                    .header h1 {{ margin: 0; font-size: 28px; }}
                    .header p {{ margin: 5px 0 0; font-size: 16px; opacity: 0.9; }}
                    .content {{ padding: 30px; }}
                    .content h2 {{ color: #d63384; margin-top: 0; font-size: 22px; }}
                    .details {{ background-color: #fff0f6; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 5px solid #d63384; }}
                    .details p {{ margin: 8px 0; font-size: 15px; }}
                    .details strong {{ color: #d63384; }}
                    .button-container {{ text-align: center; margin: 30px 0; }}
                    
                    .button {{ 
                        display: inline-block; 
                        background-color: #d63384; 
                        color: white; 
                        padding: 12px 25px; 
                        text-decoration: none; 
                        border-radius: 25px; 
                        font-weight: bold; 
                        font-size: 16px; 
                        transition: background-color 0.3s ease; 
                        margin: 5px; /* <-- Adicionado espaçamento */
                    }}
                    .button:hover {{ background-color: #c02b73; }}
                    
                    /* Style Botao Mercado Pago */
                    .button-payment {{ background-color: #009ee3; /* Azul do Mercado Pago */ color: white; }}
                    .button-payment:hover {{ background-color: #007eb5; }}
                    .footer {{ text-align: center; font-size: 0.85em; color: #666; padding: 20px; background-color: #f0f0f0; border-top: 1px solid #eee; }}
                    .footer p {{ margin: 5px 0; }}
                    .footer a {{ color: #d63384; text-decoration: none; margin: 0 8px; }}
                    .footer a:hover {{ text-decoration: underline; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>RM Studio</h1>
                        <p>Sua Beleza em Nossas Mãos</p>
                    </div>
                    
                    <div class="content">
                        <h2>Olá, {ag.nome}!</h2>
                        <p>Agradecemos muito por agendar conosco no RM Studio!</p>
                        <p>Sua solicitação foi recebida e está em análise. Em breve, entraremos em contato para confirmar sua reserva.</p>
                        
                        <div class="details">
                            <h3 style="margin-top: 0; color: #d63384;">📋 Detalhes da sua Solicitação</h3>
                            <p><strong>📅 Data:</strong> {ag.hora.data.strftime('%d/%m/%Y')}</p>
                            <p><strong>⏰ Horário:</strong> {ag.hora.hora.strftime('%H:%M')}</p>
                            <p><strong>💅 Serviço:</strong> {ag.get_servico_display()}</p>
                        </div>

                        <p>Fique de olho na sua caixa de entrada para a confirmação!</p>
                        
                        <div class="button-container">
                            <a href="{request.build_absolute_uri(reverse('criar_pagamento_agendamento', args=[ag.id]))}" 
                                class="button button-payment" target="_blank">
                                💳 Pagar Agora
                            </a>
                            <a href="httpsa://wa.me/5583999999999" class="button">💬 Falar no WhatsApp</a>
                        </div>
                        
                        <p style="font-size: 0.9em; text-align: center;">Caso precise alterar ou cancelar, responda este e-mail ou entre em contato pelos nossos canais.</p>
                    </div>
                    
                    <div class="footer">
                        <p><strong>RM Studio</strong> - Transformando sua beleza em arte</p>
                        <p>✉️ contato@rmstudio.com | 📞 (83) 99999-9999</p>
                        <div>
                            <a href="httpsa://www.instagram.com/rmstudio" target="_blank">Instagram</a> | 
                            <a href="httpsa://www.facebook.com/rmstudio" target="_blank">Facebook</a> | 
                            <a href="{settings.SITE_URL}" target="_blank">Site Oficial</a>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Enviar e-mail com ambas as versões
            msg = EmailMultiAlternatives(
                subject, text_content, "RM Studio <rmcredpb@gmail.com>", [ag.email]
            )
            msg.attach_alternative(html_content, "text/html")
            try:
                msg.send()
            except Exception as e:
                print("Falha ao enviar e-mail:", e)

            return redirect("sucesso")

    if profissional_obj:
        datas_disponiveis = (
            HorarioDisponivel.objects.filter(disponivel=True, profissional=profissional_obj)
            .values_list("data", flat=True)
            .distinct()
            .order_by("data")
        )
    else:
        datas_disponiveis = []

    form = AgendamentoForm()
    form.fields['data'].widget.input_type = 'hidden'

    
    datas_disponiveis = (
        HorarioDisponivel.objects
        .filter(
            disponivel=True,
            profissional=profissional_obj,
            data__gte=timezone.now().date()  # só hoje em diante
        )
        .values_list('data', flat=True)
        .distinct()
        .order_by('data')
    )

    # Filtra horários por data e profissional
    # Horários do dia escolhido
    if data_str and profissional_obj:
        horas_do_dia = HorarioDisponivel.objects.filter(
            disponivel=True,
            data=parse_date(data_str),
            profissional=profissional_obj
        ).order_by("hora")
    else:
        horas_do_dia = HorarioDisponivel.objects.none()

    # Formulário já vem com data + profissional como *initial*
    initial = {}
    if data_str:
        initial["data"] = data_str
    if profissional_obj:
        initial["profissional"] = profissional_obj.id

    form = AgendamentoForm(initial=initial)
    form.fields["data"].widget.input_type = "hidden"
    form.fields["profissional"].widget.input_type = "hidden"
    form.fields["hora"].queryset = horas_do_dia

    return render(
        request,
        "LihStudio/agendar.html",
        {
            "profissionais": Profissional.objects.filter(ativo=True),  # p/ <select>
            "profissional_selecionada": prof_slug,
            "datas_disponiveis": datas_disponiveis,
            "data_selecionada": data_str,
            "form": form,
        },
    )

# ------------------------- AUTENTICAÇÃO -------------------------

# Em LihStudio/views.py

def login_view(request):
    if request.user.is_authenticated:
        # Se já está logado, manda para o painel correto
        if request.user.is_superuser:
            return redirect('painel_dona')
        elif request.user.is_staff:
            return redirect('painel_funcionario')
        else:
            return redirect('home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            # --- INÍCIO DA LÓGICA DE REDIRECIONAMENTO ---
            if user is not None:
                login(request, user)
                messages.success(request, f'Login realizado com sucesso, {user.username}!')
                
                # 1. É Superusuário? Painel completo.
                if user.is_superuser:
                    return redirect('painel_dona')
                
                # 2. É só Funcionário (Staff)? Painel lite.
                elif user.is_staff:
                    return redirect('painel_funcionario')
                
                # 3. É um cliente comum? (se você implementar isso no futuro)
                else:
                    return redirect('home')
            # --- FIM DA LÓGICA ---
            else:
                messages.error(request, 'Credenciais inválidas.')
        else:
            messages.error(request, 'Credenciais inválidas.')
    else:
        form = AuthenticationForm()
    
    return render(request, 'LihStudio/login_adm.html', {'form': form})

def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, 'Você foi desconectado com sucesso.')
    return redirect('home')

# ------------------------- DECORATOR DE PROTEÇÃO -------------------------

def only_admin(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Você precisa fazer login para acessar esta área.')
            return redirect('login')
        if not request.user.is_superuser:
            messages.error(request, 'Acesso restrito a administradores.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# ------------------------- VIEWS ADMINISTRATIVAS -------------------------

@only_admin
def painel_dona(request):
    hoje = date.today()
    
    agendamentos_hoje = Agendamento.objects.filter(data=hoje).exclude(status='cancelado') \
        .select_related('hora', 'profissional', 'servico') \
        .order_by('hora__hora')
    agendamentos_confirmados = Agendamento.objects.filter(status='confirmado')
    agendamentos_pendentes = Agendamento.objects.filter(status='pendente')
    agendamentos_cancelados = Agendamento.objects.filter(status='cancelado')
    total_clientes = Agendamento.objects.values('nome', 'telefone').distinct().count()
    agendamentos_futuros = Agendamento.objects.filter(data__gte=hoje).exclude(data=hoje).exclude(status='cancelado').order_by('data', 'hora__hora')
    
    # Agendamentos com pagamento pendente
    agendamentos_pagamento_pendente = Agendamento.objects.filter(
        status='pendente', 
        pagamento_status='pendente'
    )

    agendamentos_passados_pendentes = Agendamento.objects.filter(
    data__lt=hoje,
    status__in=['pendente', 'confirmado']
    ).select_related('hora', 'profissional', 'servico').order_by('-data')
    
    return render(request, 'LihStudio/painel_dona.html', {
        'agendamentos_hoje': agendamentos_hoje,
        'agendamentos_confirmados': agendamentos_confirmados,
        'agendamentos_pendentes': agendamentos_pendentes,
        'agendamentos_cancelados': agendamentos_cancelados,
        'agendamentos_futuros': agendamentos_futuros,
        'agendamentos_pagamento_pendente': agendamentos_pagamento_pendente,
        'total_clientes': total_clientes,
        'hoje': hoje,
        'agendamentos_passados_pendentes': agendamentos_passados_pendentes,
    })

def cancelar_agendamento_cliente(request, agendamento_id, token):
    ag = get_object_or_404(Agendamento, id=agendamento_id)

    # Verificar se o token é válido
    if str(ag.token) != str(token):
        return render(request, 'LihStudio/mensagem.html', {
            'titulo': "Link inválido ou expirado",
            'mensagem': "O link que você usou não é válido ou já expirou. Se tiver dúvidas, entre em contato conosco."
        }, status=404)

    # 🚫 Bloquear cancelamento se o agendamento já foi concluído ou cancelado
    if ag.status in ['concluido', 'cancelado']:
        return render(request, 'LihStudio/mensagem.html', {
            'titulo': "Cancelamento não disponível",
            'mensagem': "Este agendamento já foi concluído ou cancelado e não pode mais ser alterado."
        }, status=403)
    
    if request.method == 'POST':
        # Marcar como cancelado em vez de deletar
        ag.status = 'cancelado'
        ag.save()
        
        # Liberar horário se existir
        if ag.hora:
            ag.hora.disponivel = True
            ag.hora.save()

        if ag.hora:
            # Se tem um slot de horário, usa ele
            data_cancelada = ag.hora.data.strftime('%d/%m/%Y')
            hora_cancelada = ag.hora.hora.strftime('%H:%M')
        else:
            # Senão, usa os campos de backup (agendamento manual)
            data_cancelada = ag.data.strftime('%d/%m/%Y') if ag.data else "[Data não registrada]"
            hora_cancelada = ag.hora_backup.strftime('%H:%M') if ag.hora_backup else "[Hora não registrada]"
        
        # Enviar email de confirmação de cancelamento
        subject = '😔 Seu Agendamento Foi Cancelado - RM Studio'
        text_content = f"""
        Olá, {ag.nome},

        Confirmamos o cancelamento do seu agendamento no RM Studio.

        📅 Detalhes do agendamento cancelado:
        Data: {data_cancelada}
        Horário: {hora_cancelada}
        Serviço: {ag.get_servico_display()}

        Sentiremos sua falta! Se desejar reagendar em outra ocasião, estamos à disposição.

        Para agendar novamente ou tirar dúvidas, acesse nosso site ou entre em contato.

        Atenciosamente,
        Equipe RM Studio
        ✉️ contato@rmstudio.com
        📞 (83) 99999-9999
        """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Arial', sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4; }}
                .container {{ background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .header {{ background-color: #d63384; color: white; padding: 25px 20px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 5px 0 0; font-size: 16px; opacity: 0.9; }}
                .content {{ padding: 30px; }}
                .content h2 {{ color: #d63384; margin-top: 0; font-size: 22px; }}
                .details {{ background-color: #ffebeb; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 5px solid #ff0000; }}
                .details p {{ margin: 8px 0; font-size: 15px; }}
                .details strong {{ color: #d63384; }}
                .button-container {{ text-align: center; margin: 30px 0; }}
                .button {{ display: inline-block; background-color: #d63384; color: white; padding: 12px 25px; text-decoration: none; border-radius: 25px; font-weight: bold; font-size: 16px; transition: background-color 0.3s ease; }}
                .button:hover {{ background-color: #c02b73; }}
                .footer {{ text-align: center; font-size: 0.85em; color: #666; padding: 20px; background-color: #f0f0f0; border-top: 1px solid #eee; }}
                .footer p {{ margin: 5px 0; }}
                .footer a {{ color: #d63384; text-decoration: none; margin: 0 8px; }}
                .footer a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>RM Studio</h1>
                    <p>Agendamento Cancelado</p>
                </div>
                
                <div class="content">
                    <h2>Olá, {ag.nome}!</h2>
                    <p>Confirmamos o cancelamento do seu agendamento em nosso sistema.</p>
                    
                    <div class="details">
                        <h3 style="margin-top: 0; color: #d63384;">❌ Detalhes do Agendamento Cancelado</h3>
                        <p><strong>📅 Data:</strong> {data_cancelada}</p>
                        <p><strong>⏰ Horário:</strong> {hora_cancelada}</p>
                        <p><strong>💅 Serviço:</strong> {ag.get_servico_display()}</p>
                    </div>
                    
                    <p>Sentimos muito que você não possa comparecer. Se precisar reagendar em outra data, estaremos à disposição!</p>
                    
                    <div class="button-container">
                        <a href="{settings.SITE_URL}/agendar/" class="button">📅 Agendar Novo Horário</a>
                    </div>
                    
                    <p style="font-size: 0.9em; text-align: center;">Para dúvidas, entre em contato conosco.</p>
                </div>
                
                <div class="footer">
                    <p><strong>RM Studio</strong> - Transformando sua beleza em arte</p>
                    <p>✉️ {settings.EMAIL_HOST_USER} | 📞 (83) 99999-9999</p>
                    <div>
                        <a href="https://www.instagram.com/rmstudio" target="_blank">Instagram</a> | 
                        <a href="https://www.facebook.com/rmstudio" target="_blank">Facebook</a> | 
                        <a href="{settings.SITE_URL}" target="_blank">Site Oficial</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            f'RM Studio <{settings.EMAIL_HOST_USER}>',
            [ag.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        return render(request, 'LihStudio/agendamento_cancelado.html')
    
    return render(request, 'LihStudio/confirmar_cancelamento.html', {
        'agendamento': ag,
        'horario': f"{ag.hora.data.strftime('%d/%m/%Y')} às {ag.hora.hora.strftime('%H:%M')}" if ag.hora else ""
    })

@only_staff
def confirmar_agendamento(request, agendamento_id):
    ag = get_object_or_404(Agendamento, id=agendamento_id)
    ag.confirmado = True
    ag.status = 'confirmado'
    ag.save()

    if ag.hora:
        ag.hora.disponivel = False
        ag.hora.save()

    # Gerar link para Google Agenda
    data_evento = ag.hora.data if ag.hora else ag.data
    hora_evento = ag.hora.hora if ag.hora else ag.hora_backup

    data_formatada = data_evento.strftime('%d/%m/%Y')
    hora_formatada = hora_evento.strftime('%H:%M')

    if data_evento and hora_evento:
        start_time = datetime.combine(data_evento, hora_evento)
        end_time = start_time + timedelta(hours=1)
        calendar_link = (
            "https://calendar.google.com/calendar/render?action=TEMPLATE&"
            f"text=Agendamento+RM+Studio&dates={start_time.strftime('%Y%m%dT%H%M%S')}/"
            f"{end_time.strftime('%Y%m%dT%H%M%S')}&details=Serviço:+{ag.get_servico_display()}"
        )
    else:
        # Se mesmo com o backup não tiver dados suficientes, usa um link genérico.
        calendar_link = "https://calendar.google.com/"
    
    # Gerar link de cancelamento
    cancel_link = request.build_absolute_uri(
        reverse('cancelar_agendamento_cliente', args=[ag.id, ag.token])
    )

    subject = '✨ Seu Agendamento no RM Studio Está Confirmado!'
    text_content = f"""
    Olá, {ag.nome}!

    Seu agendamento no RM Studio foi confirmado com sucesso! Estamos ansiosos para te receber.

    🗓 Detalhes do seu agendamento:
    Data: {data_formatada}
    Horário: {hora_formatada}
    Serviço: {ag.get_servico_display()}

    Adicione ao seu calendário para não esquecer: {calendar_link}

    📌 Informações Importantes:
    - Por favor, chegue 10 minutos antes do horário marcado para seu atendimento.
    - Tenha este e-mail (ou comprovante) em mãos para facilitar seu check-in.
    - Lembre-se: cancelamentos com menos de 24 horas de antecedência podem estar sujeitos a uma taxa.

    Estamos prontos para cuidar da sua beleza!

    Com carinho,
    Equipe RM Studio
    ✉️ contato@lihstudio.com
    📞 (83) 99999-9999
    """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Arial', sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4; }}
            .container {{ background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .header {{ background-color: #d63384; color: white; padding: 25px 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .header p {{ margin: 5px 0 0; font-size: 16px; opacity: 0.9; }}
            .content {{ padding: 30px; }}
            .content h2 {{ color: #d63384; margin-top: 0; font-size: 22px; }}
            .details {{ background-color: #fff0f6; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 5px solid #d63384; }}
            .details p {{ margin: 8px 0; font-size: 15px; }}
            .details strong {{ color: #d63384; }}
            .button-group {{ text-align: center; margin: 30px 0; }}
            .button {{ display: inline-block; padding: 12px 25px; text-decoration: none; border-radius: 25px; font-weight: bold; font-size: 16px; margin: 5px; transition: background-color 0.3s ease; }}
            .button-primary {{ background-color: #d63384; color: white; }}
            .button-primary:hover {{ background-color: #c02b73; }}
            .button-whatsapp {{ background-color: #25D366; color: white; }}
            .button-whatsapp:hover {{ background-color: #1DA851; }}
            .button-cancel {{ background-color: #FF0000; color: white; }}
            .button-cancel:hover {{ background-color: #CC0000; }}
            .important-info {{ background-color: #fef7e6; border: 1px solid #fbdc8b; padding: 15px; border-radius: 8px; margin-top: 25px; }}
            .important-info h3 {{ color: #d63384; margin-top: 0; font-size: 18px; }}
            .important-info ul {{ margin: 0; padding-left: 20px; }}
            .important-info li {{ margin-bottom: 5px; }}
            .footer {{ text-align: center; font-size: 0.85em; color: #666; padding: 20px; background-color: #f0f0f0; border-top: 1px solid #eee; }}
            .footer p {{ margin: 5px 0; }}
            .footer a {{ color: #d63384; text-decoration: none; margin: 0 8px; }}
            .footer a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>RM Studio</h1>
                <p>Seu Agendamento Confirmado!</p>
            </div>
            
            <div class="content">
                <h2>Olá, {ag.nome}!</h2>
                <p>Seu agendamento foi confirmado com sucesso! Estamos preparando tudo com carinho para te receber.</p>
                
                <div class="details">
                    <h3 style="margin-top: 0; color: #d63384;">📋 Detalhes do Seu Agendamento</h3>
                    <p><strong>📅 Data:</strong> {data_formatada}</p>
                    <p><strong>⏰ Horário:</strong> {hora_formatada}</p>
                    <p><strong>💅 Serviço:</strong> {ag.get_servico_display()}</p>
                </div>
                
                <div class="button-group">
                    <a href="{calendar_link}" class="button button-primary" target="_blank">📅 Adicionar ao Calendário</a>
                    <a href="https://wa.me/5583999999999" class="button button-whatsapp" target="_blank">💬 Falar no WhatsApp</a>
                    <a href="{cancel_link}" class="button button-cancel" target="_blank">❌ Cancelar Agendamento</a>
                </div>

                <div class="important-info">
                    <h3>📌 Informações Importantes</h3>
                    <ul>
                        <li>Por favor, chegue <strong>10 minutos antes</strong> do horário marcado para seu atendimento.</li>
                        <li>Tenha este e-mail (ou comprovante) em mãos para facilitar seu check-in.</li>
                        <li>Lembre-se: cancelamentos com menos de 24 horas de antecedência podem estar sujeitos a uma taxa.</li>
                    </ul>
                </div>
                
                <p style="text-align: center; margin-top: 30px;">Estamos ansiosos para te receber no RM Studio!</p>
            </div>
            
            <div class="footer">
                <p><strong>RM Studio</strong> - Transformando sua beleza em arte</p>
                <p>✉️ contato@lihstudio.com | 📞 (83) 99999-9999</p>
                <div>
                    <a href="https://www.instagram.com/rmstudio" target="_blank">Instagram</a> | 
                    <a href="https://www.facebook.com/rmstudio" target="_blank">Facebook</a> | 
                    <a href="{settings.SITE_URL}" target="_blank">Site Oficial</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        'RM Studio <rmcredpb@gmail.com>',
        [ag.email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    
    messages.success(request, 'Agendamento confirmado com sucesso!')

    if request.user.is_superuser:
        return redirect('painel_dona')
    else:
        return redirect('painel_funcionario')

# ------------------------- VIEWS MERCADO PAGO -------------------------

import mercadopago
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

# Configuração do Mercado Pago

@csrf_exempt
def criar_pagamento_agendamento(request, agendamento_id):
    """
    Cria uma preferência de pagamento no Mercado Pago para um agendamento específico
    """
    agendamento = get_object_or_404(Agendamento, id=agendamento_id)

    # Validações de status
    if agendamento.status in ['confirmado', 'cancelado', 'concluido']:
        messages.error(request, "Este agendamento já foi processado e não pode ser pago.")
        return redirect('home')

    if agendamento.pagamento_status == 'aprovado':
        messages.info(request, "Este agendamento já foi pago e confirmado.")
        return redirect('home')

    # Inicialização do SDK com tratamento de erro
    try:
        sdk = mercadopago.SDK(access_token=settings.MERCADOPAGO_ACCESS_TOKEN)
    except Exception as e:
        print(f"Erro ao inicializar SDK Mercado Pago: {e}")
        messages.error(request, "Erro na configuração do pagamento. Tente novamente.")
        return redirect('home')

    # Obter preço do serviço
    preco = agendamento.servico.preco if agendamento.servico else Decimal('100.00')

    # URLs de retorno - Usando build_absolute_uri para URLs completas
    success_url = request.build_absolute_uri(reverse('pagamento_sucesso'))
    failure_url = request.build_absolute_uri(reverse('pagamento_falha'))  
    pending_url = request.build_absolute_uri(reverse('pagamento_pendente'))
    
    # URL do webhook (deve estar configurada no settings.py)
    notification_url = getattr(settings, 'MERCADOPAGO_WEBHOOK_URL', None)

    # Configuração da preferência de pagamento
    preference_data = {
        "items": [
            {
                "title": f"{agendamento.get_servico_display()} - {agendamento.profissional.nome}",
                "quantity": 1,
                "unit_price": float(preco),
                "currency_id": "BRL",
                "description": f"Agendamento #{agendamento.id} - {agendamento.nome}"
            }
        ],
        "payer": {
            "name": agendamento.nome,
            "email": agendamento.email,
        },
        "back_urls": {
            "success": success_url,
            "failure": failure_url,
            "pending": pending_url,
        },
        # "auto_return": "approved",  # Retorno automático quando aprovado
        "external_reference": str(agendamento.id),
        "statement_descriptor": "RM STUDIO",
        "expires": True,  # Preferência expira
        "expiration_date_from": None,
        "expiration_date_to": None,
    }

    # Adicionar notification_url apenas se estiver configurada
    if notification_url:
        preference_data["notification_url"] = notification_url

    try:
        # Criar preferência no Mercado Pago
        preference_response = sdk.preference().create(preference_data)
        
        # Log para debug
        print("Resposta do Mercado Pago:")
        print(json.dumps(preference_response, indent=2))
        
        # Verificar se a criação foi bem-sucedida
        if preference_response.get("status") != 201:
            error_msg = preference_response.get("response", {}).get("message", "Erro desconhecido")
            print(f"Erro ao criar preferência: {error_msg}")
            messages.error(request, f"Erro ao criar pagamento: {error_msg}")
            return redirect('home')
        
        preference = preference_response.get("response")
        if not preference or "id" not in preference:
            print("Resposta inválida do Mercado Pago")
            messages.error(request, "Erro na resposta do Mercado Pago")
            return redirect('home')
        
        preference_id = preference["id"]
        init_point = preference["init_point"]
        
        # Salvar dados do pagamento no agendamento
        agendamento.pagamento_id = preference_id
        agendamento.pagamento_status = "pendente"
        agendamento.save()

        print(f"✅ Preferência criada: {preference_id}")
        
        # Renderizar página de pagamento
        return render(request, "LihStudio/pagamento.html", {
            "agendamento": agendamento,
            "preco": preco,
            "preference_id": preference_id,
            "public_key": settings.MERCADOPAGO_PUBLIC_KEY,
            "init_point": init_point,
        })

    except Exception as e:
        print(f"❌ Exceção ao criar pagamento: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, "Erro inesperado ao processar pagamento. Tente novamente.")
        return redirect('home')


@csrf_exempt
def webhook_mercadopago(request):
    """
    Webhook para receber notificações do Mercado Pago - VERSÃO CORRIGIDA
    """
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    try:
        # Inicializar SDK
        sdk = mercadopago.SDK(access_token=settings.MERCADOPAGO_ACCESS_TOKEN)
        
        # Obter dados do webhook
        data = json.loads(request.body.decode('utf-8'))
        print(f"Webhook recebido: {json.dumps(data, indent=2)}")

        # Extrair informações do webhook
        topic = data.get("topic") or data.get("type")
        
        if topic != "payment":
            print(f"Tópico não tratado: {topic}")
            return HttpResponse("OK", status=200)

        resource_id = data.get("data", {}).get("id") or data.get("id")
        if not resource_id:
            print("Pagamento sem ID")
            return HttpResponse("OK", status=200)

        print(f"Processando {topic} - ID: {resource_id}")

        # Buscar informações do pagamento
        payment_info = sdk.payment().get(resource_id)
        
        if payment_info.get("status") != 200:
            print(f"Erro ao buscar pagamento: {payment_info}")
            return HttpResponse("Error fetching payment", status=400)
            
        payment_data = payment_info.get("response", {})
        
        # Extrair dados importantes
        payment_status = payment_data.get("status")
        external_reference = payment_data.get("external_reference")
        payment_id = payment_data.get("id")
        
        print(f"Status: {payment_status}, Referência: {external_reference}, ID: {payment_id}")

        if not external_reference:
            print("Pagamento sem referência externa")
            return HttpResponse("OK", status=200)

        # Buscar agendamento
        try:
            agendamento = Agendamento.objects.get(id=int(external_reference))
            print(f"Agendamento encontrado: {agendamento.id}")
        except (Agendamento.DoesNotExist, ValueError):
            print(f"Agendamento não encontrado para ID: {external_reference}")
            return HttpResponse("OK", status=200)

        # Salvar status anterior para comparação
        old_status = agendamento.pagamento_status
        
        # Atualizar status conforme o status do pagamento
        if payment_status == "approved":

            # --- INÍCIO DA CORREÇÃO 2: WEBHOOK RACE CONDITION ---
            if agendamento.status not in ['pendente', 'confirmado']:
                # O admin já cancelou ou concluiu este agendamento.
                # Apenas registramos o pagamento, mas não mudamos o status.
                print(f"Webhook: Pagamento {payment_id} aprovado, mas agendamento {agendamento.id} está {agendamento.status}. Ignorando mudança de status.")
                
                agendamento.pagamento_status = "aprovado"
                agendamento.pagamento_id = str(payment_id)
                agendamento.save()
                
                # Retorna OK, pois o pagamento foi processado,
                # mas o status do agendamento não foi alterado.
                return HttpResponse("OK (Ignorado, status não pendente)", status=200)
            # --- FIM DA CORREÇÃO 2 ---

            # Se chegou aqui, o status é 'pendente' (ou 'confirmado', webhook duplicado)
            agendamento.status = "confirmado"
            agendamento.confirmado = True
            agendamento.pagamento_status = "aprovado"
            agendamento.pagamento_id = str(payment_id)
            
            # Bloquear horário
            if agendamento.hora:
                agendamento.hora.disponivel = False
                agendamento.hora.save()
                
            # Enviar email apenas se mudou de status
            if old_status != "aprovado":
                try:
                    enviar_email_confirmacao_automatica(agendamento)
                except Exception as e:
                    print(f"Erro ao enviar email: {e}")
                    
        elif payment_status == "rejected":
            agendamento.pagamento_status = "rejeitado"
            agendamento.pagamento_id = str(payment_id)
            
            # Liberar horário se rejeitado
            if agendamento.hora:
                agendamento.hora.disponivel = True
                agendamento.hora.save()

        elif payment_status in ["in_process", "pending"]:
            if agendamento.pagamento_status == 'pendente':
                agendamento.pagamento_status = "processando"
                agendamento.pagamento_id = str(payment_id)
            else:
                print(f"Webhook: 'pending' recebido, mas status já é {agendamento.pagamento_status}. Ignorando.")

        elif payment_status in ["cancelled", "refunded", "charged_back"]:
            agendamento.pagamento_status = "rejeitado"
            agendamento.pagamento_id = str(payment_id)
            
            # Liberar horário
            if agendamento.hora:
                agendamento.hora.disponivel = True
                agendamento.hora.save()

        agendamento.save()
        print(f"Status atualizado: {old_status} → {agendamento.pagamento_status}")
        
        return HttpResponse("OK", status=200)

    except json.JSONDecodeError:
        print("Erro ao decodificar JSON do webhook")
        return HttpResponse("Invalid JSON", status=400)
        
    except Exception as e:
        print(f"Erro no webhook Mercado Pago: {str(e)}")
        import traceback
        traceback.print_exc()
        return HttpResponse("Internal Server Error", status=500)


def pagamento_sucesso(request):
    """
    Página de retorno quando o pagamento é aprovado
    """
    payment_id = request.GET.get('payment_id')
    external_reference = request.GET.get('external_reference')
    status = request.GET.get('status')
    
    print(f"🔍 Retorno de sucesso - Payment ID: {payment_id}, Status: {status}, Ref: {external_reference}")
    
    agendamento = None
    if external_reference:
        try:
            agendamento = Agendamento.objects.get(id=int(external_reference))
            
            # Se o status ainda está pendente, atualizar manualmente
            if status == 'approved' and agendamento.pagamento_status == 'pendente':
                agendamento.status = "confirmado"
                agendamento.confirmado = True
                agendamento.pagamento_status = "aprovado"
                agendamento.pagamento_id = payment_id or agendamento.pagamento_id
                agendamento.save()
                
                # Bloquear horário
                if agendamento.hora:
                    agendamento.hora.disponivel = False
                    agendamento.hora.save()
                
                # Enviar email de confirmação
                try:
                    enviar_email_confirmacao_automatica(agendamento)
                except Exception as e:
                    print(f"Erro ao enviar email: {e}")
                
                messages.success(request, "Pagamento confirmado com sucesso! Você receberá um email de confirmação.")
            else:
                messages.info(request, "Seu pagamento está sendo processado. Você receberá uma confirmação em breve.")
                
        except (Agendamento.DoesNotExist, ValueError):
            messages.error(request, "Agendamento não encontrado.")
    else:
        messages.info(request, "Pagamento processado. Verifique seu email para confirmação.")
    
    return render(request, 'LihStudio/pagamento_sucesso.html', {
        'agendamento': agendamento,
        'payment_id': payment_id,
        'status': status
    })


def pagamento_falha(request):
    """
    Página de retorno quando o pagamento falha
    """
    payment_id = request.GET.get('payment_id')
    external_reference = request.GET.get('external_reference')
    
    print(f"❌ Retorno de falha - Payment ID: {payment_id}, Ref: {external_reference}")
    
    # Liberar horário se houve falha
    if external_reference:
        try:
            agendamento = Agendamento.objects.get(id=int(external_reference))
            agendamento.pagamento_status = "rejeitado"
            agendamento.save()
            
            if agendamento.hora:
                agendamento.hora.disponivel = True
                agendamento.hora.save()
                
        except Agendamento.DoesNotExist:
            pass
    
    messages.error(request, "Falha no processamento do pagamento. O horário foi liberado. Tente novamente.")
    return render(request, 'LihStudio/pagamento_falha.html')


def pagamento_pendente(request):
    """
    Página de retorno quando o pagamento fica pendente
    """
    payment_id = request.GET.get('payment_id')
    external_reference = request.GET.get('external_reference')
    
    print(f"⏳ Retorno pendente - Payment ID: {payment_id}, Ref: {external_reference}")
    
    if external_reference:
        try:
            agendamento = Agendamento.objects.get(id=int(external_reference))
            agendamento.pagamento_status = "processando"
            agendamento.pagamento_id = payment_id or agendamento.pagamento_id
            agendamento.save()
        except Agendamento.DoesNotExist:
            pass
    
    messages.info(request, "Seu pagamento está sendo processado. Você receberá uma confirmação em breve.")
    return render(request, 'LihStudio/pagamento_pendente.html')

# ------------------------- VIEWS ENVIO EMAIL -------------------------

def enviar_email_confirmacao_automatica(agendamento):
    """
    Função auxiliar para enviar email de confirmação automática
    CORRIGIDA - removido parâmetro request desnecessário
    """
    from django.core.mail import EmailMultiAlternatives
    from django.urls import reverse
    
    # Para gerar URLs absolutas sem request
    site_url = settings.SITE_URL
    
    # Gerar links para o email
    cancel_link = f"{site_url}/cancelar/{agendamento.id}/{agendamento.token}/"
    calendar_link = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={agendamento.get_servico_display()}&dates={agendamento.data.strftime('%Y%m%d')}/{agendamento.data.strftime('%Y%m%d')}&details=Agendamento confirmado no RM Studio"
    
    subject = 'Pagamento Confirmado - Seu Agendamento no RM Studio!'
    
    text_content = f"""
    Olá, {agendamento.nome}!

    Seu pagamento foi confirmado e seu agendamento está garantido!

    Detalhes do Seu Agendamento:
    Data: {agendamento.data.strftime('%d/%m/%Y')}
    Horário: {agendamento.hora.hora.strftime('%H:%M') if agendamento.hora else 'A definir'}
    Serviço: {agendamento.get_servico_display()}
    Profissional: {agendamento.profissional.nome}

    Estamos ansiosos para te receber!

    Atenciosamente,
    Equipe RM Studio
    """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #27ae60; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .details {{ background-color: #e8f5e8; padding: 15px; margin: 20px 0; border-radius: 8px; }}
            .button {{ display: inline-block; background-color: #27ae60; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 5px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Pagamento Confirmado!</h1>
            <p>Seu agendamento está garantido</p>
        </div>
        
        <div class="content">
            <h2>Olá, {agendamento.nome}!</h2>
            <p>Seu pagamento foi confirmado e seu agendamento está garantido!</p>
            
            <div class="details">
                <h3>Detalhes do Seu Agendamento</h3>
                <p><strong>Data:</strong> {agendamento.data.strftime('%d/%m/%Y')}</p>
                <p><strong>Horário:</strong> {agendamento.hora.hora.strftime('%H:%M') if agendamento.hora else 'A definir'}</p>
                <p><strong>Serviço:</strong> {agendamento.get_servico_display()}</p>
                <p><strong>Profissional:</strong> {agendamento.profissional.nome}</p>
            </div>
            
            <div style="text-align: center;">
                <a href="{calendar_link}" class="button">Adicionar ao Calendário</a>
                <a href="https://wa.me/5583999999999" class="button">WhatsApp</a>
            </div>
            
            <p style="text-align: center;">Estamos ansiosos para te receber no RM Studio!</p>
        </div>
    </body>
    </html>
    """
    
    try:
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            f'RM Studio <{settings.EMAIL_HOST_USER}>',
            [agendamento.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        print(f"Email de confirmação enviado para {agendamento.email}")
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

@only_staff
def concluir_agendamento(request, agendamento_id):
    ag = get_object_or_404(Agendamento, id=agendamento_id)
    
    # Verificar se está cancelado
    if ag.status == 'cancelado':
        messages.error(request, 'Não é possível concluir um agendamento cancelado!')
        # --- MUDANÇA NO REDIRECIONAMENTO ---
        if request.user.is_superuser:
            return redirect('painel_dona')
        else:
            return redirect('painel_funcionario')
    
    ag.status = 'concluido'

    if ag.pagamento_status == 'pendente':
        ag.pagamento_status = 'aprovado'

    ag.save()

    # Enviar e-mail de confirmação de conclusão
    subject = '🌟 Seu Serviço no RM Studio Foi Concluído!'
    text_content = f"""
    Olá, {ag.nome}!

    Obrigada por escolher o RM Studio! Seu serviço foi concluído com sucesso e esperamos que tenha gostado do resultado.

    Serviço Realizado: {ag.get_servico_display()}
    Data do Atendimento: {ag.data.strftime('%d/%m/%Y')}

    Sua opinião é muito importante para nós! Ajude-nos a melhorar avaliando sua experiência:
    [Link para pesquisa de satisfação]

    Esperamos te ver em breve para mais um momento de beleza e cuidado!

    Atenciosamente,
    Equipe RM Studio
    ✉️ contato@lihstudio.com
    📞 (83) 99999-9999
    """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Arial', sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4; }}
            .container {{ background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .header {{ background-color: #d63384; color: white; padding: 25px 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .header p {{ margin: 5px 0 0; font-size: 16px; opacity: 0.9; }}
            .content {{ padding: 30px; }}
            .content h2 {{ color: #d63384; margin-top: 0; font-size: 22px; }}
            .details {{ background-color: #f0f8ff; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 5px solid #d63384; }}
            .details p {{ margin: 8px 0; font-size: 15px; }}
            .details strong {{ color: #d63384; }}
            .button-container {{ text-align: center; margin: 30px 0; }}
            .button {{ display: inline-block; background-color: #d63384; color: white; padding: 12px 25px; text-decoration: none; border-radius: 25px; font-weight: bold; font-size: 16px; transition: background-color 0.3s ease; }}
            .button:hover {{ background-color: #c02b73; }}
            .footer {{ text-align: center; font-size: 0.85em; color: #666; padding: 20px; background-color: #f0f0f0; border-top: 1px solid #eee; }}
            .footer p {{ margin: 5px 0; }}
            .footer a {{ color: #d63384; text-decoration: none; margin: 0 8px; }}
            .footer a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>RM Studio</h1>
                <p>Serviço Concluído</p>
            </div>
            <div class="content">
                <h2>Olá, {ag.nome}!</h2>
                <p>Obrigada por escolher o RM Studio! Seu serviço foi concluído com sucesso e esperamos que tenha gostado do resultado.</p>
                
                <div class="details">
                    <h3 style="margin-top: 0; color: #d63384;">✅ Detalhes do Serviço</h3>
                    <p><strong>💅 Serviço Realizado:</strong> {ag.get_servico_display()}</p>
                    <p><strong>📅 Data do Atendimento:</strong> {ag.data.strftime('%d/%m/%Y')}</p>
                </div>
                
                <p style="text-align: center;">Sua opinião é muito importante para nós! Ajude-nos a melhorar avaliando sua experiência:</p>
                
                <div class="button-container">
                    <a href="[Link para pesquisa de satisfação]" class="button">🌟 Avaliar Serviço</a>
                </div>
                
                <p style="text-align: center; margin-top: 30px;">Esperamos te ver em breve para mais um momento de beleza e cuidado!</p>
            </div>
            
            <div class="footer">
                <p><strong>RM Studio</strong> - Transformando sua beleza em arte</p>
                <p>✉️ contato@lihstudio.com | 📞 (83) 99999-9999</p>
                <div>
                    <a href="https://www.instagram.com/rmstudio" target="_blank">Instagram</a> | 
                    <a href="https://www.facebook.com/rmstudio" target="_blank">Facebook</a> | 
                    <a href="{settings.SITE_URL}" target="_blank">Site Oficial</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    msg = EmailMultiAlternatives(
        subject,
        text_content,
        'RM Studio <rmcredpb@gmail.com>',
        [ag.email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    messages.success(request, 'Serviço marcado como concluído e e-mail enviado!')

    if request.user.is_superuser:
        return redirect('painel_dona')
    else:
        return redirect('painel_funcionario')

@only_admin
def cancelar_agendamento(request, agendamento_id):
    ag = get_object_or_404(Agendamento, id=agendamento_id)
    
    # Verificar se já está cancelado
    if ag.status == 'cancelado':
        messages.warning(request, 'Este agendamento já estava cancelado.')
        return redirect('painel_dona')
    
    # Guarda os dados para o e-mail ANTES de modificar
    email = ag.email
    nome = ag.nome

    # --- INÍCIO DA CORREÇÃO ---
    
    # 1. Apenas mudamos o status.
    ag.status = 'cancelado'
    
    # 2. Verificamos se existe um horário ONLINE (ag.hora) para liberar.
    #    Se for um agendamento manual (como o seu), 'ag.hora' será None, 
    #    e este 'if' será pulado.
    if ag.hora:
        # Libera o horário online
        ag.hora.disponivel = True
        ag.hora.save()
        ag.hora = None  # Remove a referência ao slot de horário
    
    ag.save() # Salva as alterações (status e/ou ag.hora=None)

    # O resto da função (enviar e-mail) continua igual...
    subject = '⚠️ Informação Importante: Seu Agendamento no RM Studio Foi Cancelado'
    text_content = f"""
    Olá, {nome}!

    Gostaríamos de informar que seu agendamento no RM Studio foi cancelado.

    Se foi um engano, ou se você deseja remarcar, por favor, entre em contato conosco o mais breve possível. Estamos à disposição para ajudar a encontrar um novo horário que se encaixe na sua agenda.

    📞 Nossos Canais de Atendimento:
    ✉️ E-mail: {settings.EMAIL_HOST_USER}
    📞 Telefone: (83) 99999-9999
    💬 WhatsApp: (83) 99999-9999

    Você também pode verificar os horários disponíveis e agendar online em: www.rmstudio.com/agendar

    Esperamos ter a oportunidade de te atender em breve!

    Atenciosamente,
    Equipe RM Studio
    """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Arial', sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f4f4f4; }}
            .container {{ background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .header {{ background-color: #d63384; color: white; padding: 25px 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 28px; }}
            .header p {{ margin: 5px 0 0; font-size: 16px; opacity: 0.9; }}
            .content {{ padding: 30px; }}
            .content h2 {{ color: #d63384; margin-top: 0; font-size: 22px; }}
            .info-box {{ background-color: #ffebee; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 5px solid #ff0000; }}
            .info-box p {{ margin: 8px 0; font-size: 15px; }}
            .button-group {{ text-align: center; margin: 30px 0; }}
            .button {{ display: inline-block; padding: 12px 25px; text-decoration: none; border-radius: 25px; font-weight: bold; font-size: 16px; margin: 5px; transition: background-color 0.3s ease; }}
            .button-primary {{ background-color: #d63384; color: white; }}
            .button-primary:hover {{ background-color: #c02b73; }}
            .button-whatsapp {{ background-color: #25D366; color: white; }}
            .button-whatsapp:hover {{ background-color: #1DA851; }}
            .button-phone {{ background-color: #4285F4; color: white; }}
            .button-phone:hover {{ background-color: #3367D6; }}
            .footer {{ text-align: center; font-size: 0.85em; color: #666; padding: 20px; background-color: #f0f0f0; border-top: 1px solid #eee; }}
            .footer p {{ margin: 5px 0; }}
            .footer a {{ color: #d63384; text-decoration: none; margin: 0 8px; }}
            .footer a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>RM Studio</h1>
                <p>Agendamento Cancelado</p>
            </div>
            
            <div class="content">
                <h2>Olá, {nome}!</h2>
                <p>Gostaríamos de informar que seu agendamento no RM Studio foi cancelado.</p>
                
                <div class="info-box">
                    <h3 style="margin-top: 0; color: #ff0000;">❗ Atenção</h3>
                    <p>Se foi um engano, ou se você deseja remarcar, por favor, entre em contato conosco o mais breve possível. Estamos à disposição para ajudar a encontrar um novo horário que se encaixe na sua agenda.</p>
                </div>
                
                <div class="button-group">
                    <a href="{settings.SITE_URL}/agendar/" class="button button-primary" target="_blank">📅 Agendar Novo Horário</a>
                    <a href="https://wa.me/5583999999999" class="button button-whatsapp" target="_blank">💬 Falar no WhatsApp</a>
                    <a href="tel:+5583999999999" class="button button-phone">📞 Ligar para o RM Studio</a>
                </div>
                
                <p style="text-align: center; margin-top: 30px;">Esperamos ter a oportunidade de te atender em breve!</p>
            </div>
            
            <div class="footer">
                <p><strong>RM Studio</strong> - Transformando sua beleza em arte</p>
                <p>✉️ {settings.EMAIL_HOST_USER} | 📞 (83) 99999-9999</p>
                <div>
                    <a href="https://www.instagram.com/rmstudio" target="_blank">Instagram</a> | 
                    <a href="https://www.facebook.com/rmstudio" target="_blank">Facebook</a> | 
                    <a href="{settings.SITE_URL}" target="_blank">Site Oficial</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        f'RM Studio <{settings.EMAIL_HOST_USER}>',
        [email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    
    messages.error(request, 'Agendamento cancelado com sucesso! Um e-mail foi enviado ao cliente.')
    return redirect('painel_dona')

# ------------------------- VIEWS ADICIONAR HORARIO -------------------------

@only_admin
def adicionar_horario(request):
    if request.method == 'POST':
        data = request.POST.get('data')
        hora = request.POST.get('hora')
        profissional_slug = request.POST.get('profissional')
        
        if not data or not hora or not profissional_slug:
            messages.error(request, 'Preencha todos os campos obrigatórios!')
            return redirect('adicionar_horario')

        try:
            if profissional_slug == 'ambas':
                # Cria para TODAS as profissionais ativas
                profissionais = Profissional.objects.filter(ativo=True)
                for prof in profissionais:
                    HorarioDisponivel.objects.create(
                        data=data,
                        hora=hora,
                        profissional=prof,
                        disponivel=True
                    )
                messages.success(request, 'Horários adicionados para todas as profissionais com sucesso!')
            else:
                profissional_obj = Profissional.objects.get(slug=profissional_slug)
                HorarioDisponivel.objects.create(
                    data=data,
                    hora=hora,
                    profissional=profissional_obj,
                    disponivel=True
                )
                messages.success(request, f'Horário adicionado para {profissional_obj.nome} com sucesso!')

            return redirect('adicionar_horario')

        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao adicionar o horário: {str(e)}')
            return redirect('adicionar_horario')

    horarios = HorarioDisponivel.objects.all().order_by('data', 'hora')
    profissionais = Profissional.objects.filter(ativo=True)
    return render(request, 'LihStudio/adicionar_horario.html', {
        'horarios': horarios,
        'profissionais': profissionais
    })

@only_admin
def excluir_horario(request, horario_id):
    horario = get_object_or_404(HorarioDisponivel, id=horario_id)
    horario.delete()
    messages.success(request, 'Horário excluído com sucesso!')
    return redirect('adicionar_horario')

@only_admin
def gerar_horarios_semanais(request):
    if request.method == "POST":
        # Dados do formulário
        dias_selecionados = request.POST.getlist("dias", [])          # ['1', '3', '5']
        inicio_str        = request.POST.get("horario_inicio", "09:00")
        fim_str           = request.POST.get("horario_fim", "18:00")
        intervalo         = int(request.POST.get("intervalo", 30))    # em minutos
        prof_slug         = request.POST.get("profissional")          # 'elisama' | 'alana' | 'ambas'

        # 1. Pegar as novas datas do formulário
        data_inicio_str = request.POST.get("data_inicio_auto")
        data_fim_str    = request.POST.get("data_fim_auto")

        # 2. Define a lista de profissionais alvo (lógica original)
        if not prof_slug or prof_slug == "ambas":
            profissionais = Profissional.objects.filter(ativo=True)   # todas
        else:
            profissionais = Profissional.objects.filter(slug=prof_slug, ativo=True)

        if not profissionais.exists():
            messages.error(request, "Profissional não encontrada.")
            return redirect("adicionar_horario")

        # 3. Converte strings de hora → objetos time (lógica original)
        try:
            inicio_time = datetime.strptime(inicio_str, "%H:%M").time()
            fim_time    = datetime.strptime(fim_str, "%H:%M").time()
        except ValueError:
            messages.error(request, "Horários inválidos.")
            return redirect("adicionar_horario")

        if inicio_time >= fim_time:
            messages.error(request, "Horário de início deve ser antes do horário de fim.")
            return redirect("adicionar_horario")

        # 4. Valida e converte as datas de INÍCIO e FIM
        try:
            # A data de início é sempre obrigatória
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "Data de início inválida.")
            return redirect("adicionar_horario")

        # Agora, validamos a data de fim
        if not data_fim_str:
            data_fim = data_inicio + timedelta(days=6)
            
        else:
            # Se a data fim FOI PREENCHIDA, apenas converte
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                messages.error(request, "A Data de Fim preenchida é inválida.")
                return redirect("adicionar_horario")
        
        # A verificação de 'data_inicio > data_fim' continua igual e funciona para os dois casos
        if data_inicio > data_fim:
            messages.error(request, "A data de início não pode ser maior que a data de fim.")
            return redirect("adicionar_horario")
        
        # Calcula o número de dias para o loop
        total_dias = (data_fim - data_inicio).days + 1


        # 5.  Gera horários para o PERÍODO selecionado (substitui o range(7))
        horarios_criados = 0
        for prof in profissionais:
            
            # Loop dinâmico baseado no total de dias
            for offset in range(total_dias):
                data = data_inicio + timedelta(days=offset) # dia analisado
                
                # A verificação do dia da semana continua a mesma
                if str(data.isoweekday()) not in dias_selecionados:
                    continue                                # pula dias fora da seleção

                # Lógica interna do loop (é a mesma que você já tinha)
                inicio_dt = datetime.combine(data, inicio_time)
                fim_dt    = datetime.combine(data, fim_time)

                hora_atual = inicio_dt
                while hora_atual <= fim_dt:
                    # Usamos get_or_create para não duplicar horários
                    obj, created = HorarioDisponivel.objects.get_or_create(
                        profissional=prof,
                        data=hora_atual.date(),
                        hora=hora_atual.time(),
                        defaults={"disponivel": True},
                    )
                    if created:
                        horarios_criados += 1 # Conta apenas os horários realmente novos
                    
                    hora_atual += timedelta(minutes=intervalo)
        
        # Mensagem de sucesso melhorada
        if horarios_criados > 0:
            messages.success(request, f"{horarios_criados} novos horários gerados com sucesso no período selecionado!")
        else:
            messages.info(request, "Nenhum horário novo foi criado (provavelmente já existiam).")
            
        return redirect("adicionar_horario")

    profissionais = Profissional.objects.filter(ativo=True)
    return render(request, "LihStudio/gerar_horarios.html", {"profissionais": profissionais})

@only_admin
def excluir_todos_horarios(request):
    if request.method == 'POST':
        # Primeiro liberar os horários nos agendamentos
        agendamentos_com_horario = Agendamento.objects.filter(hora__isnull=False)
        for ag in agendamentos_com_horario:
            ag.hora = None  # Remove a referência ao horário
            ag.save()
        
        # Depois deletar todos os horários
        count = HorarioDisponivel.objects.all().count()
        HorarioDisponivel.objects.all().delete()
        
        messages.success(request, f"Todos os {count} horários foram excluídos com sucesso!")
        return redirect('adicionar_horario')
    
    return redirect('adicionar_horario')

@only_admin
def excluir_horarios_passados(request):
    if request.method == 'POST':
        hoje = timezone.now().date()
        horarios_passados = HorarioDisponivel.objects.filter(data__lt=hoje)
        count = horarios_passados.count()
        horarios_passados.delete()
        
        messages.success(request, f'{count} horários passados foram excluídos com sucesso!')
        return redirect('adicionar_horario')
    
    return redirect('adicionar_horario')

def excluir_horarios_periodo(request):
    if request.method == 'GET':
        data_inicio = request.GET.get('inicio')
        data_fim = request.GET.get('fim')
        
        try:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
            
            if data_inicio > data_fim:
                messages.error(request, 'A data de início não pode ser maior que a data de fim!')
                return redirect('adicionar_horario')
            
            horarios_periodo = HorarioDisponivel.objects.filter(data__gte=data_inicio, data__lte=data_fim)
            count = horarios_periodo.count()
            horarios_periodo.delete()
            
            messages.success(request, f'{count} horários no período selecionado foram excluídos com sucesso!')
            return redirect('adicionar_horario')
            
        except (ValueError, TypeError):
            messages.error(request, 'Datas inválidas! Por favor, selecione um período válido.')
            return redirect('adicionar_horario')
    
    return redirect('adicionar_horario')

# ------------------------- VIEWS LISTA DE CLIENTES -------------------------

from django.db.models import Count, Max, Sum, DecimalField, ExpressionWrapper
from decimal import Decimal

@only_admin
def lista_cliente(request):
    # Inicia com todos os agendamentos
    agendamentos = Agendamento.objects.filter()

    # Aplicar filtros
    nome = request.GET.get('nome')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    status_filtro = request.GET.get('status')
    profissional_filtro = request.GET.get('profissional')
    servico_filtro_id = request.GET.get('servico')
    
    if nome:
        agendamentos = agendamentos.filter(nome__icontains=nome)
    if data_inicio:
        agendamentos = agendamentos.filter(data__gte=data_inicio)
    if data_fim:
        agendamentos = agendamentos.filter(data__lte=data_fim)
    if servico_filtro_id:
        agendamentos = agendamentos.filter(servico__id=servico_filtro_id)
    if status_filtro:
        agendamentos = agendamentos.filter(status=status_filtro)
    if profissional_filtro:
        agendamentos = agendamentos.filter(profissional__slug=profissional_filtro)
    
    
    # --- INÍCIO DA CORREÇÃO ---
    
    # 1. Criamos a base da subconsulta
    subquery_agendamentos = Agendamento.objects.filter(
        nome=models.OuterRef('nome'),
        telefone=models.OuterRef('telefone')
    )

    # 2. Aplicamos os MESMOS filtros da consulta principal na subconsulta
    #    (O filtro 'nome' não é necessário aqui, pois já está no OuterRef)
    if data_inicio:
        subquery_agendamentos = subquery_agendamentos.filter(data__gte=data_inicio)
    if data_fim:
        subquery_agendamentos = subquery_agendamentos.filter(data__lte=data_fim)
    if servico_filtro_id:
        subquery_agendamentos = subquery_agendamentos.filter(servico__id=servico_filtro_id)
    if status_filtro:
        subquery_agendamentos = subquery_agendamentos.filter(status=status_filtro)
    if profissional_filtro:
        subquery_agendamentos = subquery_agendamentos.filter(profissional__slug=profissional_filtro)

    # 3. Criamos as anotações usando a subconsulta JÁ FILTRADA
    clientes = agendamentos.values('nome', 'telefone').annotate(
        
        # O total de visitas SÓ considera os filtros, está correto
        total_visitas=Count('id', filter=Q(status='concluido')),
        
        # A última visita SÓ considera os filtros, está correto
        ultima_visita=Max('data'),
        
        # Agora as subconsultas também respeitam os filtros
        ultimo_profissional=models.Subquery(
            subquery_agendamentos.order_by('-data', '-hora_backup').values('profissional__nome')[:1]
        ),
        ultimo_servico=models.Subquery(
            subquery_agendamentos.order_by('-data', '-hora_backup').values('servico__nome')[:1]
        )
    ).order_by('nome')
    
    # --- FIM DA CORREÇÃO ---

    # Renomear o campo profissional__nome para profissional
    clientes = [{
        'nome': c['nome'],
        'telefone': c['telefone'],
        'profissional': c['ultimo_profissional'],
        'total_visitas': c['total_visitas'],
        'ultima_visita': c['ultima_visita'],
        'ultimo_servico': c['ultimo_servico']
    } for c in clientes]
    
    # Obter choices de serviços para o filtro
    servicos = Servico.objects.filter(ativo=True).order_by('ordem', 'nome')
    profissionais = Profissional.objects.filter(ativo=True)
    
    return render(request, 'LihStudio/clientes.html', {
        'clientes': clientes,
        'servicos': servicos,
        'profissionais': profissionais
    })

@only_admin
def historico_cliente(request):
    nome = request.GET.get('nome')
    telefone = request.GET.get('telefone')
    
    historico = Agendamento.objects.filter(
        nome=nome,
        telefone=telefone
    ).order_by('-data', '-hora_backup')  # Ordena pelo backup se hora for None
    
    return render(request, 'LihStudio/historico_cliente.html', {
        'historico': historico,
        'cliente_nome': nome,
        'cliente_telefone': telefone
    })

from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from itertools import groupby

@only_admin
def exportar_clientes_pdf(request):
    # --- INÍCIO DA CORREÇÃO ---
    # Renomeamos as variáveis de filtro para evitar conflito
    nome_filtro = request.GET.get('nome')
    servico_filtro_id = request.GET.get('servico')
    data_inicio_filtro = request.GET.get('data_inicio')
    data_fim_filtro = request.GET.get('data_fim')
    profissional_filtro_slug = request.GET.get('profissional')
    status_filtro = request.GET.get('status')
    
    agendamentos = Agendamento.objects.all()
    
    # Aplicar filtros usando as novas variáveis
    if nome_filtro:
        agendamentos = agendamentos.filter(nome__icontains=nome_filtro)
    if servico_filtro_id:
        agendamentos = agendamentos.filter(servico=servico_filtro_id)
    if data_inicio_filtro and data_fim_filtro:
        agendamentos = agendamentos.filter(data__range=[data_inicio_filtro, data_fim_filtro])
    elif data_inicio_filtro:
        agendamentos = agendamentos.filter(data__gte=data_inicio_filtro)
    elif data_fim_filtro:
        agendamentos = agendamentos.filter(data__lte=data_fim_filtro)
    if profissional_filtro_slug:
        agendamentos = agendamentos.filter(profissional__slug=profissional_filtro_slug)
    if status_filtro:
        agendamentos = agendamentos.filter(status=status_filtro)
    
    # Agrupar por cliente e preparar dados para o template
    clientes_data = []
    for nome, group in groupby(
        agendamentos.order_by('nome', '-data', '-hora__hora'),
        key=lambda x: (x.nome, x.telefone)
    ):
        ags = list(group)
        ultimo = ags[0]
        
        clientes_data.append({
            'nome': ultimo.nome,
            'telefone': ultimo.telefone,
            'profissional': ultimo.profissional.nome if ultimo.profissional else '',
            'ultima_visita': ultimo.data,
            'ultimo_servico': ultimo.get_servico_display(),
            'status': ultimo.status,
            'total_visitas': sum(1 for a in ags if a.status == 'concluido')
        })
    
    # Construir string de filtros usando as variáveis corretas
    filtros = []
    if nome_filtro: 
        filtros.append(f"Nome: {nome_filtro}") # ⬅️ CORRIGIDO
    if servico_filtro_id: 
        try:
            servico_obj = Servico.objects.get(id=servico_filtro_id)
            servico_display = servico_obj.nome
        except Servico.DoesNotExist:
            servico_display = f"ID {servico_filtro_id} (desconhecido)"
        filtros.append(f"Serviço: {servico_display}") # ⬅️ CORRIGIDO
    if profissional_filtro_slug:
        profissional = Profissional.objects.filter(slug=profissional_filtro_slug).first()
        if profissional:
            filtros.append(f"Profissional: {profissional.nome}") # ⬅️ CORRIGIDO
    if status_filtro: 
        status_display = dict(Agendamento.STATUS_CHOICES).get(status_filtro, status_filtro)
        filtros.append(f"Status: {status_display}") # ⬅️ CORRIGIDO
    if data_inicio_filtro or data_fim_filtro:
        periodo = []
        if data_inicio_filtro:
            periodo.append(f"de {data_inicio_filtro}")
        if data_fim_filtro:
            periodo.append(f"até {data_fim_filtro}")
        filtros.append(f"Período: {' '.join(periodo)}") # ⬅️ CORRIGIDO
    
    # Contexto
    context = {
        'clientes': clientes_data,
        'filtros_aplicados': ' • '.join(filtros) if filtros else "Nenhum filtro aplicado",
        'request': request
    }
    
    template = get_template('LihStudio/clientes_pdf.html')
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="relatorio_clientes.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Erro ao gerar PDF', status=500)
    return response

def pagina_erro_404(request, exception=None):
    return render(request, 'LihStudio/404.html', status=404)

def termos_uso(request):
    """Página de Termos de Uso"""
    return render(request, 'LihStudio/termos_uso.html')

def politica_privacidade(request):
    """Página de Política de Privacidade"""
    return render(request, 'LihStudio/politica_privacidade.html')

# ------------------------- VIEWS FATURAMENTO -------------------------

@only_admin
def relatorio_faturamento(request):
    hoje = timezone.now().date()
    
    # NOVOS FILTROS
    mes_filtro = request.GET.get('mes')
    ano_filtro = request.GET.get('ano')
    prof_slug_filtro = request.GET.get('profissional')

    mes_atual = int(mes_filtro) if mes_filtro else hoje.month
    ano_atual = int(ano_filtro) if ano_filtro else hoje.year

    # Query base: Apenas agendamentos CONCLUÍDOS, com valor E MARCADOS PARA CONTABILIZAR
    faturamento_base = Agendamento.objects.filter(
        status='concluido',
        valor_total__isnull=False,
        contabilizar=True  # ⬅️ NOVA CONDIÇÃO AQUI
    )
    
    # Aplicar filtro de Mês e Ano
    faturamento_mes_query = faturamento_base.filter(
        data__year=ano_atual,
        data__month=mes_atual
    )
    
    # Aplicar filtro de Profissional, se houver
    if prof_slug_filtro and prof_slug_filtro != 'todos':
        faturamento_mes_query = faturamento_mes_query.filter(profissional__slug=prof_slug_filtro)

    # 1. Estatísticas Gerais (Total)
    faturamento_total_bruto = faturamento_base.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')

    # 2. Estatísticas do Período Filtrado
    faturamento_mes_aggr = faturamento_mes_query.aggregate(
        total_bruto=Sum('valor_total'),
        total_servicos=Count('id')
    )
    
    total_bruto_mes = faturamento_mes_aggr['total_bruto'] or Decimal('0.00')
    total_servicos_mes = faturamento_mes_aggr['total_servicos']
    total_comissao_mes = total_bruto_mes * Decimal('0.30')
    
    # 3. Análise por Profissional (para a tabela)
    analise_profissionais = faturamento_mes_query.values(
        'profissional__nome', 
        'profissional__slug'
    ).annotate(
        total_servicos=Count('id'),
        faturamento_bruto=Sum('valor_total'),
        comissao_prof=ExpressionWrapper(
            Sum('valor_total') * Decimal('0.30'), 
            output_field=DecimalField()
        ) 
    ).order_by('-faturamento_bruto')
    
    # Obter nome do mês
    meses = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}
    mes_nome = meses.get(mes_atual, "")
    
    context = {
        'faturamento_total_bruto': faturamento_total_bruto,
        'total_bruto_mes': total_bruto_mes,
        'total_servicos_mes': total_servicos_mes,
        'total_comissao_mes': total_comissao_mes,
        'analise_profissionais': analise_profissionais,
        'profissionais': Profissional.objects.filter(ativo=True), # Para o filtro
        
        # Variáveis de filtro para manter o estado
        'mes_atual': mes_atual,
        'ano_atual': ano_atual,
        'prof_slug_filtro': prof_slug_filtro,
        'mes_nome': mes_nome,
        'hoje': hoje,
    }
    return render(request, 'LihStudio/faturamento.html', context)

@only_admin
def exportar_faturamento_pdf(request):
    hoje = timezone.now().date()
    agora = timezone.now()
    
    # 1. COPIAMOS EXATAMENTE A MESMA LÓGICA DE FILTRO DA OUTRA VIEW
    mes_filtro = request.GET.get('mes')
    ano_filtro = request.GET.get('ano')
    prof_slug_filtro = request.GET.get('profissional')

    mes_atual = int(mes_filtro) if mes_filtro else hoje.month
    ano_atual = int(ano_filtro) if ano_filtro else hoje.year

    faturamento_base = Agendamento.objects.filter(
        status='concluido',
        valor_total__isnull=False,
        contabilizar=True
    )
    
    faturamento_mes_query = faturamento_base.filter(
        data__year=ano_atual,
        data__month=mes_atual
    )
    
    if prof_slug_filtro and prof_slug_filtro != 'todos':
        faturamento_mes_query = faturamento_mes_query.filter(profissional__slug=prof_slug_filtro)

    # 2. COPIAMOS OS CÁLCULOS
    faturamento_total_bruto = faturamento_base.aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')
    
    faturamento_mes_aggr = faturamento_mes_query.aggregate(
        total_bruto=Sum('valor_total'),
        total_servicos=Count('id')
    )
    
    total_bruto_mes = faturamento_mes_aggr['total_bruto'] or Decimal('0.00')
    total_servicos_mes = faturamento_mes_aggr['total_servicos']
    total_comissao_mes = total_bruto_mes * Decimal('0.30')
    
    analise_profissionais = faturamento_mes_query.values(
        'profissional__nome', 
        'profissional__slug'
    ).annotate(
        total_servicos=Count('id'),
        faturamento_bruto=Sum('valor_total'),
        comissao_prof=ExpressionWrapper(
            Sum('valor_total') * Decimal('0.30'), 
            output_field=DecimalField()
        ) 
    ).order_by('-faturamento_bruto')
    
    meses = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}
    mes_nome = meses.get(mes_atual, "")
    # 3. [NOVO] BUSCAMOS OS AGENDAMENTOS DETALHADOS (necessário para o PDF)
    agendamentos_detalhados = faturamento_mes_query.select_related(
        'hora', 'profissional', 'servico'
    ).order_by('data', 'hora_backup') # Usar 'hora_backup' é mais seguro
    
    # 4. MONTAMOS O CONTEXTO COMPLETO PARA O TEMPLATE PDF
    context = {
        'faturamento_total_bruto': faturamento_total_bruto,
        'total_bruto_mes': total_bruto_mes,
        'total_servicos_mes': total_servicos_mes,
        'total_comissao_mes': total_comissao_mes,
        'analise_profissionais': analise_profissionais,
        'agendamentos_detalhados': agendamentos_detalhados, # ⬅️ Novo
        'mes_atual': mes_atual,
        'ano_atual': ano_atual,
        'prof_slug_filtro': prof_slug_filtro,
        'mes_nome': mes_nome,
        'hoje': agora,
    }
    
    # 5. RENDERIZAMOS O PDF
    template = get_template('LihStudio/faturamento_pdf.html') #
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="faturamento_{mes_nome}_{ano_atual}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Erro ao gerar PDF', status=500)
    return response

# ------------------------- VIEWS PAGINA ADMIN -------------------------

@only_admin
def agendar_manual_admin(request):
    if request.method == "POST":
        form = AgendamentoAdminForm(request.POST)
        if form.is_valid():
            agendamento = form.save()
            messages.success(request, f"Agendamento criado com sucesso para {agendamento.nome}!")
            return redirect('painel_dona')  # Redireciona para o painel após sucesso
        else:
            messages.error(request, "Erro ao criar agendamento. Verifique os campos.")
    else:
        form = AgendamentoAdminForm()

    context = {
        'form': form
    }
    return render(request, 'LihStudio/agendar_manual_admin.html', context)

@only_admin 
def pagina_administrador(request):
    """
    View customizada para Gerenciar (Listar e Criar) Serviços.
    """
    # Lógica para CRIAR (POST)
    if request.method == 'POST':
        form = ServicoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Serviço salvo com sucesso!')
            # Redireciona para a mesma página (para limpar o form)
            return redirect('pagina_admin') 
        else:
            # Se o formulário for inválido, ele será re-renderizado com os erros
            messages.error(request, 'Erro ao salvar o serviço. Verifique os campos.')
    else:
        # Formulário vazio para adicionar novo
        form = ServicoForm() 
    
    # Lógica para LER (GET) - sempre executa
    servicos = Servico.objects.all().order_by('ordem', 'nome')
    
    context = {
        'servicos': servicos, # A lista de serviços para a tabela
        'form': form         # O formulário de "Adicionar Novo"
    }
    # Renderiza o seu template
    return render(request, 'LihStudio/pagina_admin.html', context)

@only_admin
def editar_servico(request, servico_id):
    """
    View para EDITAR um serviço existente.
    """
    # Busca o serviço pelo ID ou retorna 404
    servico = get_object_or_404(Servico, id=servico_id)
    
    if request.method == 'POST':
        # Preenche o formulário com os dados enviados (request.POST)
        # e vincula ao objeto 'servico' (instance=servico)
        form = ServicoForm(request.POST, instance=servico)
        if form.is_valid():
            form.save()
            messages.success(request, f'Serviço "{servico.nome}" atualizado com sucesso!')
            return redirect('pagina_admin')
        else:
            messages.error(request, 'Erro ao atualizar o serviço. Verifique os campos.')
    else:
        # Se for GET, apenas exibe o formulário preenchido com
        # os dados atuais do serviço (instance=servico)
        form = ServicoForm(instance=servico)
        
    context = {
        'form': form,
        'servico': servico
    }
    # Reutilizaremos o formulário em um novo template
    return render(request, 'LihStudio/editar_servico.html', context)

@only_admin
def excluir_servico(request, servico_id):
    """
    View para EXCLUIR ou DESATIVAR um serviço de forma inteligente.
    ✅ CORRIGIDO: Com snapshots, permite exclusão mesmo com histórico
    """
    servico = get_object_or_404(Servico, id=servico_id)
    nome_servico = servico.nome

    if request.method == 'POST':
        # 1. VERIFICAR se há agendamentos ATIVOS (pendentes/confirmados)
        agendamentos_ativos = servico.agendamentos.filter(
            status__in=['pendente', 'confirmado']
        )

        if agendamentos_ativos.exists():
            # ❌ BLOQUEIA: Não pode excluir se houver agendamentos ativos
            count = agendamentos_ativos.count()
            servico.ativo = False
            servico.save()
            messages.error(
                request, 
                f'❌ Não é possível excluir "{nome_servico}". '
                f'Existem {count} agendamento(s) pendente(s) ou confirmado(s). '
                f'Cancele-os primeiro ou aguarde sua conclusão.'
            )
            return redirect('pagina_admin')

        # 2. VERIFICAR se há histórico (concluído/cancelado)
        agendamentos_historicos = servico.agendamentos.filter(
            status__in=['concluido', 'cancelado']
        )

        if agendamentos_historicos.exists():
            # ✅ PODE EXCLUIR porque os agendamentos têm snapshot
            count = agendamentos_historicos.count()
            
            # Alterar o on_delete para SET_NULL temporariamente
            try:
                servico.delete()
                messages.success(
                    request, 
                    f'✅ Serviço "{nome_servico}" excluído com sucesso! '
                    f'{count} agendamento(s) no histórico foram preservados com os dados originais.'
                )
            except models.ProtectedError:
                # Se der erro (on_delete=PROTECT), explica e desativa
                servico.ativo = False
                servico.save()
                messages.warning(
                    request, 
                    f'⚠️ O serviço "{nome_servico}" foi DESATIVADO (não excluído) '
                    f'para garantir a integridade dos {count} agendamento(s) no histórico. '
                    f'Para permitir exclusão, altere o "on_delete" do campo "servico" em models.py.'
                )
        else:
            # 3. Sem histórico: exclusão segura
            servico.delete()
            messages.success(
                request, 
                f'✅ Serviço "{nome_servico}" excluído permanentemente (sem histórico associado).'
            )

    return redirect('pagina_admin')

# ------------------------- VIEWS FUNCIONARIOS -------------------------
# --- NOVA VIEW PARA FUNCIONÁRIOS ---
@only_staff  # Protegida pelo NOVO decorator
def painel_funcionario(request):
    """
    View "lite" para funcionários, mostrando apenas a agenda do dia e futura.
    """
    hoje = date.today()
    
    agendamentos_hoje = Agendamento.objects.filter(data=hoje).exclude(status='cancelado') \
        .select_related('hora', 'profissional', 'servico') \
        .order_by('hora__hora')
    agendamentos_futuros = Agendamento.objects.filter(
        data__gte=hoje
    ).exclude(data=hoje).exclude(status='cancelado').order_by('data', 'hora__hora')
    
    context = {
        'agendamentos_hoje': agendamentos_hoje,
        'agendamentos_futuros': agendamentos_futuros,
        'hoje': hoje,
        'is_superuser': request.user.is_superuser # Para exibir links de admin se for a dona
    }
    
    # Superusuários veem o painel completo
    if request.user.is_superuser:
        return redirect('painel_dona') # Se for a dona, manda pro painel completo
    
    # Funcionários comuns veem o painel lite
    return render(request, 'LihStudio/painel_funcionario.html', context)