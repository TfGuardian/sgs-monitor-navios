# Estrutura técnica

A pasta do pacote é `src/vessel_monitor/`. Os contextos Python, Supabase,
Windows e GitHub permanecem no mesmo repositório.

## Fluxos

1. WhatsApp chega à função TypeScript no Supabase, que atende comandos e registra pedidos.
2. GitHub Actions processa a sincronização do porto e os pedidos de atualização.
3. O observador local lê a Praticagem, seleciona nomes monitorados, compara estados e grava eventos.
4. O worker mostra os alertas, toca o áudio e processa a entrega ao VOS.

Os alertas da Praticagem para WhatsApp continuam em modo de observação. As
respostas aos comandos do chat usam o fluxo real existente.

## Execução

`application/praticagem_observador.py` executa uma coleta.
`runtime/worker.py` controla repetição, recuperação e intervalo entre coletas.
Essa divisão permite preparar futuramente outro executor sem duplicar regras.
Esta reorganização não criou um endpoint nem um serviço HTTP.

## Dados e recursos

`paths.py` encontra a raiz pelo conjunto de pastas do projeto; pode ser
configurada explicitamente com `VESSEL_MONITOR_ROOT`. Isso permite ler o
`.env`, certificados e áudio mesmo quando o comando começa em outra pasta.
A instalação recomendada é editável, mantendo os recursos junto ao checkout.
Uma distribuição independente em wheel precisa apontar para a pasta de recursos
com `VESSEL_MONITOR_ROOT`.

Logs: `var/logs/`. Pedidos de simulação: `var/state/`.
O ambiente legado em `tmp/praticagem-deps/` permanece como compatibilidade.
Dependências novas ficam no ambiente virtual e são declaradas em `pyproject.toml`.

## Preservação da operação

Os nomes das tarefas Windows, dos workflows, das variáveis e das migrações
foram mantidos. As entradas antigas ainda usadas por supervisores instalados
permanecem na raiz como pequenos iniciadores. Nenhuma tabela foi renomeada.
O destino VOS vem da configuração; sua validação aceita uma função HTTPS
com nome técnico, sem fixar um nome de personagem.

## Publicação

Reinicie observador e controlador depois da atualização. Não execute um segundo
worker em paralelo para validar o caminho novo. Nenhum instalador ou reinício é
executado automaticamente pela reorganização dos arquivos.

## Validação da reorganização em 21/10/2026

Passaram 162 testes Python e os cinco arquivos de testes do webhook/SQL com
PGlite local. A sintaxe Python também foi verificada. Os testes não executaram
coleta real nem enviaram mensagens. As tarefas Windows não foram reinstaladas
ou reiniciadas por esta alteração.

O script SQL avulso antigo ficou em
`supabase/maintenance/migration_etb_legacy.sql`; seu conteúdo operacional foi
preservado, sem incluí-lo como nova migração automática.

## Mapa dos módulos anteriores

- `config.py` → `src/vessel_monitor/config.py`.
- `main.py` → `src/vessel_monitor/cli.py`.
- `consulta_navio.py` → `src/vessel_monitor/presentation/consulta_navio.py`.
- `console.py` → `src/vessel_monitor/presentation/console.py`.
- `relatorio.py` → `src/vessel_monitor/presentation/relatorio.py`.
- `chat.py` → `src/vessel_monitor/application/chat.py`.
- `lista_monitoramento.py` → `src/vessel_monitor/application/lista_monitoramento.py`.
- `limpeza.py` → `src/vessel_monitor/application/limpeza.py`.
- `sincronizador.py` → `src/vessel_monitor/application/sincronizador.py`.
- `atualizacao_chat.py` → `src/vessel_monitor/application/atualizacao_chat.py`.
- `relatorio_horario.py` → `src/vessel_monitor/application/relatorio_horario.py`.
- `monitor_aps.py` → `src/vessel_monitor/sources/porto_santos/monitor_aps.py`.
- `monitor_atracacoes.py` → `src/vessel_monitor/sources/porto_santos/monitor_atracacoes.py`.
- `monitor_atracados.py` → `src/vessel_monitor/sources/porto_santos/monitor_atracados.py`.
- `monitor_fundeados.py` → `src/vessel_monitor/sources/porto_santos/monitor_fundeados.py`.
- `praticagem_portal.py` → `src/vessel_monitor/sources/praticagem/praticagem_portal.py`.
- `praticagem_normalizador.py` → `src/vessel_monitor/sources/praticagem/praticagem_normalizador.py`.
- `praticagem_por_nome.py` → `src/vessel_monitor/domain/praticagem_por_nome.py`.
- `praticagem_snapshot.py` → `src/vessel_monitor/domain/praticagem_snapshot.py`.
- `praticagem_transicoes.py` → `src/vessel_monitor/domain/praticagem_transicoes.py`.
- `praticagem_observador.py` → `src/vessel_monitor/application/praticagem_observador.py`.
- `praticagem_worker.py` → `src/vessel_monitor/runtime/worker.py`.
- `whatsapp.py` → `src/vessel_monitor/integrations/whatsapp.py`.
- `vos_integration.py` → `src/vessel_monitor/integrations/vos.py`.
- `alerta_sonoro.py` → `src/vessel_monitor/presentation/alerta_sonoro.py`.
- `controle_observador.py` → `src/vessel_monitor/runtime/windows/controle_observador.py`.
- `executar_praticagem_windows.py` → `src/vessel_monitor/runtime/windows/executar_praticagem_windows.py`.
- `executar_controle_observador_windows.py` → `src/vessel_monitor/runtime/windows/executar_controle_observador_windows.py`.
- `processos_observador.py` → `src/vessel_monitor/runtime/windows/processos_observador.py`.
- `iniciar_filho_observador.py` → `src/vessel_monitor/runtime/windows/iniciar_filho_observador.py`.
- `simulador_chat.py` → `src/vessel_monitor/simulation/simulador_chat.py`.
- `simular_praticagem.py` → `src/vessel_monitor/simulation/simular_praticagem.py`.
- `comparar_capturas_praticagem.py` → `src/vessel_monitor/simulation/comparar_capturas_praticagem.py`.
