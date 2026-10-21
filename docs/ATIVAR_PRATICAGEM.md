# Operação do observador da Praticagem

O worker faz coletas reais das quatro tabelas do portal e acompanha apenas os
nomes da lista ativa. IMO é auxiliar; ausência de IMO não impede acompanhar um
nome único. Casos ambíguos são isolados para evitar avisos de outro navio.

O primeiro estado serve de referência. Mudanças posteriores de fase, horário
ou local podem gerar eventos. Falha na fonte não significa manobra encerrada.
Os alertas WhatsApp da Praticagem permanecem simulados; os eventos podem ser
encaminhados pela integração VOS configurada.

## Preparar o ambiente

Na raiz, instale `requirements-praticagem.txt` com o Python que executará o
observador. Configure no `.env` as variáveis `SPPILOTS_USUARIO`,
`SPPILOTS_SENHA`, `SUPABASE_URL`, `SUPABASE_KEY` e
`SUPABASE_SECRET_KEY`. Nunca publique valores reais.

No Windows, o portal usa Edge. Em Linux, instale o Chromium pelo Playwright.

## Executar

Com o pacote instalado:

```powershell
python -m vessel_monitor.runtime.worker
```

No computador já preparado, também é possível usar o iniciador da raiz:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\executar_praticagem_windows.py
```

Use uma única execução. O worker tenta iniciar ciclos a cada 60 segundos,
reaproveitando a sessão. Falhas podem aumentar a espera até 120 segundos.
Um ciclo preso por mais de 165 segundos encerra o processo; o supervisor
Windows reinicia após 15 segundos. Reserva no banco impede sobreposição.

Os logs novos ficam em `var/logs/praticagem-worker.log`. Logs anteriores
em `tmp/` continuam disponíveis. Fechar o processo, desligar ou suspender o
computador interrompe o monitoramento local.

## Testes de avisos

```powershell
python -m vessel_monitor.simulation.simular_praticagem
python -m vessel_monitor.simulation.simular_praticagem --observador
python -m vessel_monitor.simulation.simular_praticagem --observador --toxotis
python -m vessel_monitor.presentation.alerta_sonoro
```

Os exemplos não gravam movimentações falsas nem enviam mensagens. O teste
TOXOTIS usa a captura real do próximo ciclo e simula a etapa seguinte em memória.
Após uma atualização da estrutura, reinicie o worker antes de pedir testes:
processos antigos ainda usam as pastas de pedidos anteriores.

Cada evento novo pode tocar `assets/sounds/miado.wav`. O volume final depende
do Windows; `PRATICAGEM_SOM_ATIVO=false` desativa o som após reinício.
Créditos em [CREDITOS.md](../assets/sounds/CREDITOS.md).

## Conferir no banco

```sql
select iniciado_em, resultado, quantidades, erro_codigo, duracao_ms
from public.coletas_praticagem order by iniciado_em desc limit 20;

select detectado_em, nome, chave_manobra, mudancas
from public.eventos_praticagem order by detectado_em desc limit 20;
```

Uma coleta recente com sucesso e zero eventos é normal quando não houve
mudanças. O histórico de coletas permite distinguir silêncio normal de falha.

Para instalar tarefas e controlar pelo WhatsApp, consulte
[ATIVAR_COMANDO_OBSERVADOR.md](ATIVAR_COMANDO_OBSERVADOR.md).
