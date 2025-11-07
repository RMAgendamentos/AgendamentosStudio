# LihStudio/tests.py
from django.test import TestCase
from django.utils import timezone
from datetime import date, time, timedelta
from decimal import Decimal # Importe o Decimal para preços
from django.core.exceptions import ValidationError

# Importe TODOS os modelos que você vai precisar
from .models import HorarioDisponivel, Agendamento, Profissional, Servico

class AgendamentoModelTest(TestCase):
    
    # setUp é executado ANTES de cada teste
    def setUp(self):
        """
        Configura o ambiente de teste criando os objetos
        necessários (Profissional, Servico, etc.)
        """
        # 1. Criar um Profissional para os testes
        self.profissional = Profissional.objects.create(
            nome="Test Profissional", 
            slug="test-pro"
        )
        
        # 2. Criar um Servico para os testes
        self.servico = Servico.objects.create(
            nome="Test Servico", 
            preco=Decimal("100.00"), 
            ativo=True
        )
        
        # 3. Criar datas e horas
        self.future_date = timezone.now().date() + timedelta(days=5)
        self.future_time = time(14, 0)
        
        # 4. Criar o HorarioDisponivel (agora CORRETO, com profissional)
        self.horario_disponivel = HorarioDisponivel.objects.create(
            profissional=self.profissional, # <-- CORREÇÃO
            data=self.future_date,
            hora=self.future_time,
            disponivel=True
        )

    def test_agendamento_creation(self):
        """Testa a criação de um agendamento válido."""
        agendamento = Agendamento.objects.create(
            profissional=self.profissional, # <-- CORREÇÃO (passa o objeto)
            servico=self.servico,           # <-- CORREÇÃO (passa o objeto)
            nome="Test Client",
            telefone="11999999999",
            email="test@example.com",
            data=self.future_date,
            hora=self.horario_disponivel,
            status="pendente"
        )
        self.assertEqual(agendamento.nome, "Test Client")
        self.assertEqual(agendamento.servico, self.servico) # Compara os objetos
        self.assertEqual(agendamento.hora, self.horario_disponivel)
        self.assertEqual(agendamento.status, "pendente")
        
        # Testar lógicas do seu models.py (save)
        self.assertEqual(agendamento.valor_total, Decimal("100.00"))
        self.assertEqual(agendamento.hora_backup, self.future_time)

    def test_agendamento_past_date_validation(self):
        """Testa a falha ao agendar em data passada (validação do 'clean')."""
        past_date = timezone.now().date() - timedelta(days=1)
        
        agendamento = Agendamento(
            profissional=self.profissional,
            servico=self.servico,
            nome="Client Past",
            telefone="11988888888",
            email="past@example.com",
            data=past_date,
            hora=self.horario_disponivel # Hora é futura, mas data não
        )
        
        # Testa a validação do model (método clean)
        with self.assertRaises(ValidationError, msg="Não levantou ValidationError para data passada."):
            agendamento.full_clean() 

    def test_agendamento_past_time_today_validation(self):
        """Testa a falha ao agendar em horário passado no dia de hoje."""
        today = timezone.now().date()
        # Garante que o time está no passado (mesmo que rode 00:00)
        past_time = (timezone.now() - timedelta(minutes=30)).time()
        
        past_horario = HorarioDisponivel.objects.create(
            profissional=self.profissional,
            data=today,
            hora=past_time,
            disponivel=True
        )
        
        agendamento = Agendamento(
            profissional=self.profissional,
            servico=self.servico,
            nome="Client Past Time",
            telefone="11977777777",
            email="pasttime@example.com",
            data=today,
            hora=past_horario
        )
        
        with self.assertRaises(ValidationError, msg="Não levantou ValidationError para hora passada."):
            agendamento.full_clean()