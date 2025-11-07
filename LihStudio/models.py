from django.db import models
from django.utils import timezone
from uuid import uuid4
from django.core.exceptions import ValidationError
from decimal import Decimal

class Servico(models.Model):
    nome = models.CharField("Nome do Serviço", max_length=100, unique=True)
    preco = models.DecimalField("Preço (R$)", max_digits=8, decimal_places=2)
    descricao = models.TextField("Descrição", blank=True, help_text="Descrição opcional do serviço")
    ativo = models.BooleanField("Ativo", default=True, help_text="Serviços inativos não aparecem no agendamento")
    ordem = models.IntegerField("Ordem de Exibição", default=0, help_text="Ordem de exibição (menor = primeiro)")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'nome']
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"

    def __str__(self):
        return f"{self.nome} - R$ {self.preco}"
    
    def pode_ser_excluido(self):
        """Verifica se o serviço pode ser excluído permanentemente"""
        return not self.agendamentos.exists()
    
    def tem_agendamentos_ativos(self):
        """Verifica se há agendamentos pendentes ou confirmados"""
        return self.agendamentos.filter(status__in=['pendente', 'confirmado']).exists()


PRECOS_SERVICOS = {}


class Profissional(models.Model):
    nome = models.CharField("Nome", max_length=50)
    slug = models.SlugField("Slug", unique=True, help_text="Identificador sem espaços – ex.: NOME")
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Profissional"
        verbose_name_plural = "Profissionais"

    def __str__(self):
        return self.nome


class HorarioDisponivel(models.Model):
    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE, related_name="horarios")
    data = models.DateField()
    hora = models.TimeField()
    disponivel = models.BooleanField(default=True)

    class Meta:
        unique_together = ("profissional", "data", "hora")
        ordering = ["data", "hora"]

    def __str__(self):
        dispon = "Disponível" if self.disponivel else "Indisponível"
        data_fmt = self.data.strftime("%d/%m/%Y")
        hora_fmt = self.hora.strftime("%H:%M")
        return f"{self.profissional} - {data_fmt} às {hora_fmt} - {dispon}"


class Agendamento(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("confirmado", "Confirmado"),
        ("cancelado", "Cancelado"),
        ("concluido", "Concluído"),
    ]

    # Campos de pagamento
    pagamento_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID do Pagamento")
    pagamento_status = models.CharField(max_length=20, default="pendente", choices=[
        ("pendente", "Pendente"),
        ("aprovado", "Aprovado"),
        ("rejeitado", "Rejeitado"),
        ("processando", "Processando"),
    ], verbose_name="Status do Pagamento")

    contabilizar = models.BooleanField(
        default=False,
        verbose_name="Contabilizar no Faturamento",
        help_text="Marque se este agendamento deve ser incluído nos relatórios de faturamento."
    )

    valor_total = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name="Valor Total (R$)"
    )

    profissional = models.ForeignKey(Profissional, on_delete=models.PROTECT, related_name="agendamentos")
    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20)
    email = models.EmailField()
    
    # ⚠️ ForeignKey para o serviço (pode ser editado/excluído)
    # SET_NULL permite exclusão; snapshots preservam os dados
    servico = models.ForeignKey(
        'Servico',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agendamentos',
        verbose_name="Serviço"
    )
    
    # ✅ NOVO: Campos de snapshot (histórico imutável)
    servico_nome_snapshot = models.CharField(
        "Nome do Serviço (Snapshot)",
        max_length=100,
        blank=True,
        help_text="Nome do serviço no momento do agendamento (não muda)"
    )
    servico_preco_snapshot = models.DecimalField(
        "Preço do Serviço (Snapshot)",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Preço do serviço no momento do agendamento (não muda)"
    )
    
    data = models.DateField()
    hora = models.ForeignKey(HorarioDisponivel, on_delete=models.SET_NULL, null=True, blank=True)
    observacoes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pendente", verbose_name="Status do Agendamento")
    manutencao_lembrada = models.BooleanField(
        default=False,
        verbose_name="Lembrete de manutenção enviado?",
        help_text="Marcar se o lembrete de manutenção foi enviado após 15 dias"
    )
    confirmado = models.BooleanField(default=False)
    token = models.UUIDField(default=uuid4, editable=False, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    hora_backup = models.TimeField(null=True, blank=True, verbose_name="Hora (backup)")

    @property
    def SERVICOS(self):
        """Retorna choices dinâmicos dos serviços ativos"""
        return [(s.nome, s.nome) for s in Servico.objects.filter(ativo=True)]

    def clean(self):
        if self.data:
            if self.data < timezone.now().date():
                raise ValidationError("Não é possível agendar para datas passadas.")

            if (
                self.data == timezone.now().date()
                and self.hora
                and self.hora.hora < timezone.now().time()
            ):
                raise ValidationError("Não é possível agendar para horários passados.")

    def save(self, *args, **kwargs):
        # ✅ CAPTURAR SNAPSHOT ao criar/salvar
        if self.servico and not self.servico_nome_snapshot:
            self.servico_nome_snapshot = self.servico.nome
            self.servico_preco_snapshot = self.servico.preco
        
        # Auto-preencher valor_total se não definido
        if not self.valor_total and self.servico:
            self.valor_total = self.servico.preco
            
        if self.hora:
            self.hora_backup = self.hora.hora
        
        # Sincronia status ↔ confirmado
        self.confirmado = self.status == "confirmado"
        super().save(*args, **kwargs)

    @property
    def status_class(self):
        return {
            "pendente": "pending",
            "confirmado": "confirmed",
            "cancelado": "canceled",
            "concluido": "completed",
        }.get(self.status, "pending")
    
    def get_servico_display(self):
        """
        ✅ CORRIGIDO: Retorna o snapshot se existir, senão o nome atual
        Isso garante que o histórico não mude quando o serviço for editado
        """
        if self.servico_nome_snapshot:
            return self.servico_nome_snapshot
        return self.servico.nome if self.servico else "Serviço não definido"
    
    def get_servico_preco_original(self):
        """Retorna o preço original do serviço no momento do agendamento"""
        if self.servico_preco_snapshot:
            return self.servico_preco_snapshot
        return self.servico.preco if self.servico else Decimal('0.00')

    def __str__(self):
        hora_txt = self.hora.hora.strftime("%H:%M") if self.hora else "--:--"
        return f"{self.nome} - {self.get_servico_display()} ({hora_txt} {self.data})"