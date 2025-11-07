from django.core.management.base import BaseCommand
from LihStudio.models import Servico
from decimal import Decimal

class Command(BaseCommand):
    help = 'Cria os serviços iniciais no banco de dados'

    def handle(self, *args, **kwargs):
        servicos_iniciais = [
            {
                'nome': 'Cílios Fio a Fio',
                'preco': Decimal('120.00'),
                'descricao': 'Extensão de cílios técnica fio a fio',
                'ordem': 1
            },
            {
                'nome': 'Volume Russo',
                'preco': Decimal('150.00'),
                'descricao': 'Extensão de cílios técnica volume russo',
                'ordem': 2
            },
            {
                'nome': 'Cílios Híbrido',
                'preco': Decimal('130.00'),
                'descricao': 'Extensão de cílios técnica híbrida',
                'ordem': 3
            },
            {
                'nome': 'Design de Sobrancelhas',
                'preco': Decimal('50.00'),
                'descricao': 'Design e modelagem de sobrancelhas',
                'ordem': 4
            },
            {
                'nome': 'Curso - Extensão de Cílios',
                'preco': Decimal('500.00'),
                'descricao': 'Curso completo de extensão de cílios',
                'ordem': 5
            },
            {
                'nome': 'Curso - Design de Sobrancelhas',
                'preco': Decimal('300.00'),
                'descricao': 'Curso completo de design de sobrancelhas',
                'ordem': 6
            },
        ]

        for servico_data in servicos_iniciais:
            servico, created = Servico.objects.get_or_create(
                nome=servico_data['nome'],
                defaults={
                    'preco': servico_data['preco'],
                    'descricao': servico_data['descricao'],
                    'ordem': servico_data['ordem'],
                    'ativo': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Serviço criado: {servico.nome} - R$ {servico.preco}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'→ Serviço já existe: {servico.nome}')
                )

        self.stdout.write(
            self.style.SUCCESS('\n✅ Migração de serviços concluída!')
        )