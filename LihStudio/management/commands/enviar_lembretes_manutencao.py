from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives # Importar EmailMultiAlternatives
from LihStudio.models import Agendamento

class Command(BaseCommand):
    help = "Envia lembretes de manutenção entre 15-20 dias após serviço concluído"

    def handle(self, *args, **options):
        # Configuração da janela de dias
        data_inicio = date.today() - timedelta(days=20)
        data_fim = date.today() - timedelta(days=15)
        
        # Serviços que precisam de manutenção (apenas cílios)
        SERVICOS_MANUTENCAO = [
            "Cílios Fio a Fio",
            "Volume Russo", 
            "Cílios Híbrido"
        ]

        # Query ajustada
        agendamentos = Agendamento.objects.filter(
            data__range=(data_inicio, data_fim),
            status="concluido",
            manutencao_lembrada=False,
            servico__in=SERVICOS_MANUTENCAO
        ).order_by('data')

        total = agendamentos.count()
        self.stdout.write(f"🔍 Procurando agendamentos entre {data_inicio} e {data_fim}...")
        self.stdout.write(f"🔍 Encontrados {total} agendamentos para lembrete")

        if total == 0:
            self.stdout.write("ℹ️ Motivos possíveis:")
            self.stdout.write("- Nenhum agendamento concluído na janela de 15-20 dias")
            self.stdout.write("- Lembretes já foram enviados (manutencao_lembrada=True)")
            self.stdout.write("- Serviços não são de cílios (cursos/design)")
            return

        for ag in agendamentos:
            try:
                # Debug: mostrar dados do agendamento
                self.stdout.write(f"\n📝 Processando: {ag.nome}")
                self.stdout.write(f"   Serviço: {ag.get_servico_display()}")
                self.stdout.write(f"   Data original: {ag.data}")
                self.stdout.write(f"   Dias passados: {(date.today() - ag.data).days} dias")
                
                # Versão texto simples do lembrete de manutenção
                text_content = f"""
Olá, {ag.nome.split()[0]}!

Já se passaram {(date.today() - ag.data).days} dias desde seu {ag.get_servico_display().lower()} conosco. Para manter seus cílios impecáveis e sua beleza em dia, recomendamos agendar uma manutenção!

Não deixe sua beleza para depois! Agende agora mesmo para garantir seu horário:
📅 Agende agora: https://LihStudio.com/agendar

Estamos esperando você para renovar seu olhar! ✨

Com carinho,
Equipe Lih Studio
✉️ contato@lihstudio.com
📞 (83) 99999-9999
                """

                # Versão HTML do lembrete de manutenção (mesmo HTML que padronizamos antes)
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
        .highlight-box {{ background-color: #fff0f6; padding: 20px; border-radius: 8px; margin: 25px 0; border-left: 5px solid #d63384; text-align: center; }}
        .highlight-box p {{ margin: 8px 0; font-size: 15px; }}
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
            <h1>Lih Studio</h1>
            <p>É Hora de Cuidar da Sua Beleza!</p>
        </div>
        <div class="content">
            <h2>Olá, {ag.nome.split()[0]}!</h2>
            <p>Já se passaram {(date.today() - ag.data).days} dias desde seu último <strong>{ag.get_servico_display().lower()}</strong> conosco. Para manter seus cílios impecáveis e sua beleza em dia, recomendamos agendar uma manutenção!</p>
            
            <div class="highlight-box">
                <p style="font-size: 18px; font-weight: bold; color: #d63384;">Não deixe sua beleza para depois!</p>
                <p>Agende agora mesmo para garantir seu horário e continuar deslumbrante.</p>
            </div>
            
            <div class="button-container">
                <a href="https://LihStudio.com/agendar" class="button" target="_blank">📅 Agendar Minha Manutenção</a>
            </div>
            
            <p style="text-align: center; margin-top: 30px;">Estamos esperando você para renovar seu olhar! ✨</p>
        </div>
        
        <div class="footer">
            <p><strong>Lih Studio</strong> - Transformando sua beleza em arte</p>
            <p>✉️ contato@lihstudio.com | 📞 (83) 99999-9999</p>
            <div>
                <a href="https://www.instagram.com/lihstudio" target="_blank">Instagram</a> | 
                <a href="https://www.facebook.com/lihstudio" target="_blank">Facebook</a> | 
                <a href="https://www.lihstudio.com" target="_blank">Site Oficial</a>
            </div>
        </div>
    </div>
</body>
</html>
                """

                # Cria a mensagem com as duas versões
                msg = EmailMultiAlternatives(
                    subject=f"💖 Hora da Manutenção, {ag.nome.split()[0]}! - Lih Studio",
                    body=text_content,
                    from_email=None,
                    to=[ag.email]
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send(fail_silently=False)
                
                ag.manutencao_lembrada = True
                ag.save()
                self.stdout.write(f"✅ E-mail de manutenção enviado para {ag.email}")
                
            except Exception as e:
                self.stdout.write(f"❌ ERRO no envio para {ag.email}: {str(e)}")

        self.stdout.write(f"\n🎉 Concluído! Total de lembretes de manutenção enviados: {total}")