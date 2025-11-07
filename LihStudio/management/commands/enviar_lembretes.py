from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives # Importar EmailMultiAlternatives
from LihStudio.models import Agendamento

class Command(BaseCommand):
    help = "Envia lembretes por e-mail para agendamentos de amanhã."

    def handle(self, *args, **options):
        amanha = date.today() + timedelta(days=1)

        agendamentos = (
            Agendamento.objects
            .filter(hora__data=amanha, confirmado=True)
            .select_related("hora")
        )

        if not agendamentos:
            self.stdout.write("Nenhum lembrete para enviar hoje.")
            return

        for ag in agendamentos:
            # Versão texto simples do lembrete
            text_content = f"""
Olá, {ag.nome}!

Este é um lembrete amigável do seu agendamento no Lih Studio para amanhã!

📅 Detalhes do seu agendamento:
Data: {ag.hora.data.strftime('%d/%m/%Y')}
Horário: {ag.hora.hora.strftime('%H:%M')}
Serviço: {ag.get_servico_display()}

Estamos ansiosos para te receber e proporcionar um momento de beleza e bem-estar!

Qualquer dúvida ou necessidade de alteração, entre em contato conosco.

Até breve! 💖
Equipe Lih Studio
✉️ contato@lihstudio.com
📞 (83) 99999-9999
            """

            # Versão HTML do lembrete (mesmo HTML que padronizamos antes)
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
            <h1>Lih Studio</h1>
            <p>Lembrete de Agendamento</p>
        </div>
        <div class="content">
            <h2>Olá, {ag.nome}!</h2>
            <p>Este é um lembrete amigável do seu agendamento no Lih Studio para amanhã!</p>
            
            <div class="details">
                <h3 style="margin-top: 0; color: #d63384;">📅 Detalhes do Seu Agendamento</h3>
                <p><strong>📅 Data:</strong> {ag.hora.data.strftime('%d/%m/%Y')}</p>
                <p><strong>⏰ Horário:</strong> {ag.hora.hora.strftime('%H:%M')}</p>
                <p><strong>💅 Serviço:</strong> {ag.get_servico_display()}</p>
            </div>
            
            <p style="text-align: center;">Estamos ansiosos para te receber e proporcionar um momento de beleza e bem-estar!</p>
            
            <div class="button-container">
                <a href="https://wa.me/5583999999999" class="button" target="_blank">💬 Falar no WhatsApp</a>
            </div>
            
            <p style="font-size: 0.9em; text-align: center;">Qualquer dúvida ou necessidade de alteração, entre em contato conosco.</p>
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
                subject=f"🔔 Lembrete: Seu Agendamento Amanhã no Lih Studio!",
                body=text_content,
                from_email=None,  # usa DEFAULT_FROM_EMAIL
                to=[ag.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
            self.stdout.write(f"Lembrete enviado para {ag.email}")