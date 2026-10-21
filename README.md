# Alfredo — monitoramento de navios

## Estrutura e pontos de entrada

- `main.py`: consultas, administração e sincronização do Porto de Santos.
- `sincronizador.py` e `monitor_*.py`: coleta e consolidação das fontes do porto.
- `praticagem_portal.py`: captura autenticada das tabelas da Praticagem.
- `praticagem_por_nome.py`, `praticagem_normalizador.py`, `praticagem_snapshot.py`
  e `praticagem_transicoes.py`: seleção pelo nome, interpretação e comparação.
- `praticagem_observador.py`: execução de uma coleta e persistência.
- `praticagem_worker.py`: agendamento contínuo local atualmente em uso.
- `executar_praticagem_windows.py`, `iniciar_filho_observador.py` e
  `processos_observador.py`: supervisão e controle dos processos no Windows.
- `controle_observador.py` e `executar_controle_observador_windows.py`:
  atendimento dos pedidos de início/reinício.
- `vos_integration.py`: entrega de eventos ao VOS; integração ativa.
- `supabase/functions/`: atendimento do WhatsApp.
- `supabase/migrations/`: histórico de alterações do banco; manter as migrações.
- `tests/`: testes automatizados. Simuladores na raiz também são ferramentas de validação.
- `assets/` e `certs/`: som, créditos e certificado utilizados pelo sistema.
- `templates/`: modelos de mensagens; envio horário está reservado para retomada.
- `deploy/` e `.github/workflows/`: configurações de execução e publicação.

## Ambiente local

`tmp/` contém dependências do observador, dependências dos testes JavaScript e
logs. Não apagar essa pasta indiscriminadamente: os executores locais a utilizam.
`.venv/` é o ambiente configurado no editor. Ambos ficam fora do Git.
`output/` contém documentos gerados e também fica fora do Git.

Prints de conversas, anexos e arquivos de revisão não pertencem ao código e foram
removidos. `.gitignore` impede sua inclusão acidental; exclusões no VS Code
mantêm a visualização focada no código. Caches Python podem reaparecer normalmente.

## Documentação operacional

Consultar `ATIVAR_PRATICAGEM.md`, `ATIVAR_COMANDO_OBSERVADOR.md`,
`ATIVAR_RESERVA_PRATICAGEM.md` e `ATIVAR_ATUALIZACAO.md`.
A migração para agendamento externo por endpoint ainda não está implementada.

## Limpeza realizada em 21/10/2026

Removidos anexos de conversas, prints de publicação, imagens de revisão,
temporários de documentos e a cópia antiga de publicação em tmp.
Removido o coletor legado sem referências `monitor_praticagem.py` e sua
configuração `PRATICAGEM_URL`. Preservados o observador atual, VOS, ferramentas
administrativas, simuladores, testes, modelos de mensagens e histórico SQL.
Validação: 159 testes Python passaram após a remoção do módulo legado.
