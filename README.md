# Monitoramento de navios

Sistema de coleta do Porto de Santos, observação da Praticagem e atendimento
pelo WhatsApp. O pacote Python usa o nome técnico `vessel_monitor`.

## Organização

- `src/vessel_monitor/domain/`: identificação, estados e comparação de movimentos.
- `src/vessel_monitor/application/`: sincronização, lista, filas e uma coleta completa.
- `src/vessel_monitor/sources/`: leitores do Porto de Santos e da Praticagem.
- `src/vessel_monitor/integrations/`: comunicação com WhatsApp e VOS.
- `src/vessel_monitor/config.py`: configuração e cliente compartilhado do Supabase.
- `src/vessel_monitor/runtime/`: ciclo contínuo e supervisão Windows.
- `src/vessel_monitor/presentation/`: consultas, relatórios, console e som.
- `src/vessel_monitor/simulation/`: cenários e comparação de capturas.
- `supabase/functions/`: atendimento real do WhatsApp em TypeScript.
- `supabase/migrations/`: histórico SQL; ordem e nomes preservados.
- `scripts/windows/`: instalação e iniciadores das tarefas locais.
- `tests/unit/`, `tests/integration/`, `tests/webhook/`: validações automatizadas.
- `docs/`: manuais, briefing e mapa dos arquivos reorganizados.
- `deploy/`: modelo de serviço Linux.
- `assets/`, `certs/`, `templates/`: áudio, certificado auxiliar e modelos de mensagem.
- `var/logs/`, `var/state/`: registros e pedidos locais de simulação, fora do Git.
- `tools/`: orientações para usar os diagnósticos e simuladores.

## Instalação nova

Use Python 3.11 ou superior, na raiz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-praticagem.txt
```

Copie `.env.example` para `.env` e configure os valores privados nesse arquivo.
No Windows, o leitor usa o Edge instalado. Para Chromium em outro ambiente,
instale o navegador com `python -m playwright install chromium` no mesmo Python.
Os nomes e valores das variáveis existentes foram preservados.

## Entradas principais

Com o pacote instalado no Python usado pelos comandos:

```powershell
python -m vessel_monitor --help
python -m vessel_monitor --sincronizar --dry-run
python -m vessel_monitor.application.praticagem_observador --help
python -m vessel_monitor.runtime.worker --help
python -m vessel_monitor.simulation.simular_praticagem
python -m unittest discover -s tests -v
```

O modo normal de sincronização pode alterar o banco. Use `--dry-run` para
simular o planejamento. Comandos reais de coleta exigem credenciais e rede.
A coleta da Praticagem continua repetida pelo worker; endpoint e agendamento
externo a cada minuto ainda são uma etapa futura.

## Windows já instalado

Os arquivos `main.py`, `executar_praticagem_windows.py`,
`executar_controle_observador_windows.py`, `praticagem_worker.py` e
`iniciar_filho_observador.py` na raiz são somente entradas de compatibilidade.
Mantêm os caminhos usados pelas tarefas existentes e carregam o novo pacote.
A implementação fica em `src/`.

Para instalações novas, veja [o manual do comando Observador](docs/ATIVAR_COMANDO_OBSERVADOR.md).
Os iniciadores ainda aceitam as dependências locais existentes em
`tmp/praticagem-deps/`; não apague essa pasta antes de preparar outro ambiente.
Não é necessário reinstalar tarefas para os caminhos antigos continuarem válidos.

Após atualizar os arquivos, reinicie o observador e o controlador para carregar
os módulos novos. Processos já abertos continuam usando código carregado antes.
Os logs novos ficam em `var/logs/`; logs antigos em `tmp/` são preservados.

## Documentação e publicação

- [Arquitetura e mapa da reorganização](docs/ESTRUTURA.md).
- [Operação da Praticagem](docs/ATIVAR_PRATICAGEM.md).
- [Atualização pelo WhatsApp](docs/ATIVAR_ATUALIZACAO.md).
- [Cadastro de reserva](docs/ATIVAR_RESERVA_PRATICAGEM.md).
- [Relatório horário, reservado para retomada](docs/RELATORIO_HORARIO.md).
- [Testes](tests/README.md).

Publicar no GitHub atualiza os executores que baixam o código; a função
TypeScript e as migrações têm publicação própria no Supabase. A reorganização
Python não exige uma nova migração nem altera os horários dos workflows.
