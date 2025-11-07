from django import forms
from django.utils.dateparse import parse_date
from django.utils import timezone
from .models import PRECOS_SERVICOS

from .models import Agendamento, HorarioDisponivel, Profissional, Servico


class HorarioDisponivelForm(forms.ModelForm):
    class Meta:
        model = HorarioDisponivel
        fields = ["profissional", "data", "hora"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "hora": forms.TimeInput(attrs={"type": "time"}),
        }


class AgendamentoForm(forms.ModelForm):
    class Meta:
        model = Agendamento
        fields = [
            "nome",
            "telefone",
            "email",
            "servico",
            "data",
            "hora",
            "observacoes",
            "profissional",
        ]
        widgets = {
            "data": forms.HiddenInput(),
            "profissional": forms.HiddenInput(),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtra o queryset do campo 'servico' para mostrar apenas os ativos
        self.fields['servico'].queryset = Servico.objects.filter(
            ativo=True
        ).order_by('ordem', 'nome')
        
        # Define o 'empty_label' (texto inicial)
        self.fields['servico'].empty_label = "Selecione um serviço"

        # restringe horas exibidas de acordo com a data
        data_str = self.data.get("data") or self.initial.get("data")
        if data_str:
            data = parse_date(data_str)
            if data:
                self.fields["hora"].queryset = (
                    HorarioDisponivel.objects.filter(data=data, disponivel=True)
                    .order_by("hora")
                )

    def clean(self):
        cleaned = super().clean()
        data = cleaned.get("data")
        hora = cleaned.get("hora")
        profissional = cleaned.get("profissional")

        if not hora:
            raise forms.ValidationError("Horário não selecionado.")

        # confirma se o horário pertence ao profissional escolhido
        if hora.profissional != profissional:
            raise forms.ValidationError(
                "O horário selecionado não pertence à profissional escolhida."
            )

        # datas passadas
        if data and data < timezone.now().date():
            raise forms.ValidationError("Não é possível agendar para datas passadas.")

        # horários passados (hoje)
        if data == timezone.now().date() and hora.hora < timezone.now().time():
            raise forms.ValidationError("Não é possível agendar para horários passados.")

        return cleaned
    
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.forms import BooleanField, DateField, TimeField, NumberInput
from datetime import datetime

class AgendamentoAdminForm(forms.ModelForm):
    data_manual = DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Data do Agendamento",
        help_text="Selecione a data para o agendamento."
    )
    hora_manual = TimeField(
        widget=forms.TimeInput(attrs={"type": "time"}),
        label="Hora do Agendamento",
        help_text="Selecione a hora para o agendamento."
    )
    contabilizar = BooleanField(
        required=False,
        label="Contabilizar no Faturamento",
        help_text="Marque se este agendamento deve ser incluído nos relatórios de faturamento."
    )

    class Meta:
        model = Agendamento
        fields = [
            "nome", "telefone", "email",
            "servico", "profissional",
            "status", "pagamento_status", "valor_total",
            "observacoes", "contabilizar"
        ]
        widgets = {
            "observacoes": forms.Textarea(attrs={"rows": 3}),
            "valor_total": NumberInput(attrs={"step": "0.01"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        data_manual = cleaned_data.get('data_manual')
        hora_manual = cleaned_data.get('hora_manual')
        status = cleaned_data.get('status')
        
        # Só validar data futura se o status for "pendente" ou "confirmado"
        if status in ['pendente', 'confirmado']:
            if data_manual and hora_manual:
                agora = timezone.now()
                data_hora_agendamento = timezone.make_aware(
                    datetime.combine(data_manual, hora_manual)
                )
                
                if data_hora_agendamento < agora:
                    raise ValidationError(
                        "Não é possível criar agendamento futuro para data/hora no passado."
                    )
        
        if not data_manual:
            self.add_error('data_manual', 'A data é obrigatória.')
        
        if not hora_manual:
            self.add_error('hora_manual', 'A hora é obrigatória.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.data = self.cleaned_data["data_manual"]
        instance.hora_backup = self.cleaned_data["hora_manual"]

        # Define valor_total baseado no serviço se não preenchido (assumindo PRECOS_SERVICOS no model ou view)
        if not instance.valor_total and instance.servico:
            instance.valor_total = instance.servico.preco

        if commit:
            instance.save()
            # Bloqueia o horário se existir
            if instance.hora:
                instance.hora.disponivel = False
                instance.hora.save()
        return instance
    
class ServicoForm(forms.ModelForm):
    """
    Formulário para criar e editar o modelo Servico.
    """
    class Meta:
        model = Servico
        # Campos que virão do models.py
        fields = ['nome', 'preco', 'descricao', 'ativo', 'ordem']
        
        # Adicionamos 'widgets' para bater com o design do seu pagina_admin.html
        widgets = {
            'nome': forms.TextInput(attrs={
                'placeholder': 'Ex: Manicure Completa', 
                'required': True
            }),
            'preco': forms.NumberInput(attrs={
                'step': '0.01', 
                'placeholder': 'Ex: 45.00', 
                'required': True
            }),
            'descricao': forms.Textarea(attrs={
                'placeholder': 'Descrição opcional do serviço...', 
                'rows': 3
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'checkbox' # Pode ser útil
            }),
            'ordem': forms.NumberInput(attrs={
                'placeholder': '0'
            }),
        }
        # Textos de ajuda que vêm do models.py
        help_texts = {
            'nome': 'Nome que aparecerá no formulário de agendamento',
            'preco': 'Valor cobrado pelo serviço',
            'descricao': 'Informações adicionais sobre o serviço',
            'ativo': 'Serviços inativos não aparecem no agendamento',
            'ordem': 'Ordem de exibição (menor = primeiro)',
        }