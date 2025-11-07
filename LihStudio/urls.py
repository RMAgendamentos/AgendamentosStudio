from django.urls import path
from . import views
from django.contrib.auth.decorators import login_required
from .views import only_admin
from django.contrib.auth.views import LoginView, LogoutView

urlpatterns = [
    path('', views.home, name='home'),
    path('home/', views.home, name='home'),
    path('agendar/', views.agendar_servico, name='agendar_servico'),
    path('sucesso/', views.sucesso_view, name='sucesso'),
    
    # Autenticação
    path('login/', views.login_view, name='login'),
    
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),

    # PAINEL FUNCIONARIOS
    path('painel-funcionario/', views.painel_funcionario, name='painel_funcionario'),
    # Painel administrativo
    path('painel/', only_admin(views.painel_dona), name='painel_dona'),
    path('clientes/', views.lista_cliente, name='lista_clientes'),
    path('clientes/historico/', views.historico_cliente, name='historico_cliente'),
    path('clientes/exportar/', views.exportar_clientes_pdf, name='exportar_clientes_pdf'),
    path('adicionar_horario/', only_admin(views.adicionar_horario), name='adicionar_horario'),
    path('gerar-horarios/', only_admin(views.gerar_horarios_semanais), name='gerar_horarios'),
    path('agendar-manual-admin/', only_admin(views.agendar_manual_admin), name='agendar_manual_admin'),
    # PAINEL ADMIN PARA CRIAR SERVIÇOS
    path('pagina-admin/', views.pagina_administrador, name='pagina_admin'),
    path('pagina-admin/servico/editar/<int:servico_id>/', views.editar_servico, name='editar_servico'),
    path('pagina-admin/servico/excluir/<int:servico_id>/', views.excluir_servico, name='excluir_servico'),
    # Páginas Legais (LGPD)
    path('termos-uso/', views.termos_uso, name='termos_uso'),
    path('politica-privacidade/', views.politica_privacidade, name='politica_privacidade'),
    # SOBRE Módulo de Faturamento
    path('faturamento/', only_admin(views.relatorio_faturamento), name='relatorio_faturamento'),
    path('faturamento/exportar/', only_admin(views.exportar_faturamento_pdf), name='exportar_faturamento_pdf'),
    # SOBRE Exclusao de Horarios
    path('excluir-horario/<int:horario_id>/', only_admin(views.excluir_horario), name='excluir_horario'),
    path('excluir-todos-horarios/', only_admin(views.excluir_todos_horarios), name='excluir_todos_horarios'),
    path('excluir_horarios_passados/', only_admin(views.excluir_horarios_passados), name='excluir_horarios_passados'),
    path('excluir_horarios_periodo/', views.excluir_horarios_periodo, name='excluir_horarios_periodo'),
    # SOBRE Confirmaçao e Cancelamento
    path('concluir-agendamento/<int:agendamento_id>/', only_admin(views.concluir_agendamento), name='concluir_agendamento'),
    path('confirmar/<int:agendamento_id>/', only_admin(views.confirmar_agendamento), name='confirmar_agendamento'),
    path('cancelar-agendamento/<int:agendamento_id>/', only_admin(views.cancelar_agendamento), name='cancelar_agendamento'),
    path('cancelar/<int:agendamento_id>/<uuid:token>/', views.cancelar_agendamento_cliente, name='cancelar_agendamento_cliente'),
    # Area de Pagamentos Mercado PAGO
    path('pagamento/<int:agendamento_id>/', views.criar_pagamento_agendamento, name='criar_pagamento_agendamento'),
    path('pagamento/sucesso/', views.pagamento_sucesso, name='pagamento_sucesso'),
    path('pagamento/falha/', views.pagamento_falha, name='pagamento_falha'),
    path('pagamento/pendente/', views.pagamento_pendente, name='pagamento_pendente'),
    path('webhook/mercadopago/', views.webhook_mercadopago, name='webhook_mercadopago'),
]