from django.contrib import admin
from .models import Profissional, HorarioDisponivel, Agendamento


@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display  = ("nome", "slug", "ativo")
    list_editable = ("ativo",)
    search_fields = ("nome",)
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(HorarioDisponivel)
class HorarioDisponivelAdmin(admin.ModelAdmin):
    list_display = ("profissional", "data_formatada", "hora_formatada", "disponivel")
    list_filter  = ("profissional", "data")
    search_fields = ("profissional__nome",)

    def data_formatada(self, obj):
        return obj.data.strftime("%d/%m/%Y")
    data_formatada.short_description = "Data"

    def hora_formatada(self, obj):
        return obj.hora.strftime("%H:%M")
    hora_formatada.short_description = "Hora"


@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display  = ("nome", "profissional", "servico", "data_formatada", "hora_formatada", "status")
    list_filter   = ("profissional", "servico", "status")
    search_fields = ("nome", "telefone", "email")

    def data_formatada(self, obj):
        return obj.data.strftime("%d/%m/%Y")
    data_formatada.short_description = "Data"

    def hora_formatada(self, obj):
        return obj.hora_backup.strftime("%H:%M") if obj.hora_backup else ""
    hora_formatada.short_description = "Hora"