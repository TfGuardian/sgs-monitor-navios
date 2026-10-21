# Observador da Praticagem — ativação por etapas

## Estado em 08/10/2026

A migração `supabase/migrations/20261007180000_praticagem_observacao.sql` foi
aplicada no Supabase. O observador local registra coletas reais a cada minuto,
e as coletas consultadas até aqui terminaram com sucesso e sem transições dos
navios acompanhados. O fluxo de WhatsApp **permanece desligado**; os
eventuais textos ficam em `alertas_simulados_praticagem` com estado
`nao_enviado`.

Dos nove cadastros ativos, oito têm IMO e estado persistido. `ROSTRUM HEDONIST`
recebeu o IMO `9955894`, `AG VALOR` recebeu `9312327` e
`FIGALIA PRUDENCE` recebeu `9588316` após conferência. `BELUGA` ainda não tem
IMO seguro; será associado somente quando aparecer com nome exato e único na
coleta. Caso ambíguo interrompe a coleta, sem criar alerta duvidoso. Um estado
persistido pode estar vazio: ele serve de referência para detectar a próxima
aparição e não prova presença atual no portal.

## Arquivos

- `praticagem_portal.py`: lê as quatro tabelas visíveis, com fase da manobra
  indicada pela cor, e reutiliza a sessão autenticada.
- `praticagem_normalizador.py`, `praticagem_snapshot.py` e
  `praticagem_transicoes.py`: validam os dados, correlacionam ocorrências e
  geram mudanças. Linha sem IMO ou ocorrência ambígua não vira aviso.
- `praticagem_observador.py`: reserva uma coleta e grava resultados de modo
  atômico no Supabase. Nunca chama a Meta.
- `praticagem_worker.py`: inicia coletas com intervalo mínimo de 60 segundos,
  recria a sessão após erro e limita a espera planejada entre tentativas a dois
  minutos em falhas consecutivas. Se uma leitura demorar mais que o intervalo,
  a próxima só começa depois de terminar a anterior; não há coleta paralela.
  Só abre o navegador depois de reservar a coleta. O portal é considerado
  pronto quando as tabelas ficam visíveis; não depende do carregamento completo
  da página. A abertura do Edge tem prazo de 60 segundos para evitar longos
  bloqueios quando o computador sai da espera.
  O log registra o início de cada ciclo, o intervalo desde o ciclo anterior e
  a duração até concluir ou falhar. As quatro tabelas são lidas em uma só
  operação no navegador, reduzindo o tempo e evitando misturar leituras de
  momentos diferentes.
  Se um ciclo ficar preso por mais de 165 segundos, o processo se encerra para
  que o Agendador de Tarefas o reinicie. A tarefa local tenta reiniciar até 20
  vezes, com intervalo de um minuto. Isso limita uma trava do Edge, mas não
  cria dados quando o computador dorme ou o portal está indisponível.

## Teste local do processo contínuo

O `.env` local deve conter `SPPILOTS_USUARIO`, `SPPILOTS_SENHA`,
`SUPABASE_URL`, `SUPABASE_KEY` e `SUPABASE_SECRET_KEY`. Não imprima nem publique
essas credenciais. No Windows deste workspace, as dependências estão em
`tmp/praticagem-deps`; o leitor usa o Microsoft Edge instalado.

```powershell
$env:PYTHONPATH = (Resolve-Path -LiteralPath '.\tmp\praticagem-deps').Path
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\praticagem_worker.py
```

Use `Ctrl+C` para interromper. Um computador desligado ou a janela fechada
interrompe a observação. O teste local não equivale a operação 24 horas.

### Execução automática neste Windows

Cada evento novo registrado emite um miado no computador junto do aviso
no console, inclusive enquanto a entrega por WhatsApp está em modo simulado.
Coletas sem eventos não tocam. O arquivo tem pico normalizado em 97%, e o
volume final segue o dispositivo de áudio do Windows. Créditos em
`assets/sounds/CREDITOS.md`.
Para testar o som, execute `python alerta_sonoro.py`. Para desativá-lo, defina
`PRATICAGEM_SOM_ATIVO=false` no `.env` e reinicie o observador.

O iniciador mantém a coleta em um processo filho. Se a proteção contra
travamento encerrar esse processo (código 124), o iniciador registra a saída
e o recria após 15 segundos. Isso evita depender exclusivamente do reinício
do Agendador. Uma saída normal ou Ctrl+C encerra o supervisor. A retomada
da coleta ainda respeita a reserva temporária no Supabase.

Cada execução agora pertence a um Job Object privado do Windows. O processo
aguarda essa associação antes de abrir o navegador. Ao encerrar a execução
ou o supervisor, o Windows encerra também os auxiliares pertencentes ao grupo;
outros navegadores do usuário ficam fora dele. O log registra memória física
disponível a cada início. A leitura bloqueia imagens, fontes e mídia, mas mantém
HTML, CSS e scripts necessários às tabelas e às cores dos estados.
A tarefa do observador usa prioridade 4 (normal), em vez de 7 (reduzida),
para não herdar prioridade baixa de CPU, disco e memória sob carga.

Em 08/10/2026, a tarefa `SGS Praticagem Observador` foi registrada no
Agendador de Tarefas para iniciar ao entrar na conta do Windows. Ela chama
`executar_praticagem_windows.py`, que encontra as dependências em
`tmp/praticagem-deps`, lê o `.env` local e grava em
`tmp/praticagem-worker.log`. A tarefa foi iniciada e duas coletas sucessivas
terminaram com sucesso e zero eventos simulados.
O iniciador também espelha a saída no console da tarefa. Quando uma mudança
real for registrada, aparecerá um bloco `AVISO SIMULADO; NÃO ENVIADO` com o
texto do aviso. Sem mudança, aparecem apenas linhas com `eventos simulados=0`.

```powershell
Get-ScheduledTask -TaskName 'SGS Praticagem Observador'
Get-Content -LiteralPath '.\tmp\praticagem-worker.log' -Tail 20
Stop-ScheduledTask -TaskName 'SGS Praticagem Observador'
Start-ScheduledTask -TaskName 'SGS Praticagem Observador'
```

O computador foi configurado para não suspender enquanto estiver na tomada.
Na bateria, a suspensão continua após 15 minutos. Para restaurar os 15
minutos também na tomada, use `powercfg /change standby-timeout-ac 15`.
Depois de reiniciar, é preciso entrar na conta do Windows para a tarefa
iniciar; bloqueio de tela não a interrompe. Desligamento, suspensão ou perda
de internet suspendem a coleta. Evite executar outra cópia manual do worker
enquanto a tarefa estiver ativa.

Para ver exemplos imediatamente, sem acessar o portal nem gravar no banco:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\simular_praticagem.py
```

O comando usa um navio fictício e imprime previsão, confirmação, andamento,
mudança de horário/local e fundeio. Nada é persistido ou enviado.

Para pedir que **a tarefa já em execução** mostre os exemplos no console e no
log, acrescente `--observador` ao comando acima. O pedido é consumido uma vez
no início do próximo ciclo. O bloco recebe o título `TESTE LOCAL NO OBSERVADOR`
e continua sem gravar eventos falsos no Supabase ou enviar WhatsApp.

Para testar o **TOXOTIS com dados reais do próximo ciclo**, use:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\simular_praticagem.py --observador --toxotis
Get-Content -LiteralPath '.\tmp\praticagem-worker.log' -Tail 25
```

O observador reutiliza a captura autenticada desse ciclo, confirma a fase atual
do IMO 9563419 e imprime uma próxima fase hipotética identificada como teste.
O alerta não é gravado no Supabase nem enviado ao WhatsApp. Se o navio não
estiver visível, o pedido permanece para a próxima coleta, e o log mostra a
falha do teste sem afetar a observação real.

Em Linux, instale `requirements-praticagem.txt` e o navegador Chromium do
Playwright antes de executar `python praticagem_worker.py`; configure as mesmas
variáveis no ambiente do processo, sem copiar `.env` para o repositório.

## Conferência no Supabase SQL Editor

```sql
select iniciado_em, resultado, quantidades, erro_codigo, duracao_ms
from public.coletas_praticagem order by iniciado_em desc limit 20;

select imo, nome, atualizado_em
from public.estados_praticagem order by nome;

select detectado_em, imo, nome, chave_manobra, mudancas
from public.eventos_praticagem order by detectado_em desc limit 20;

select a.criado_em, e.nome, a.telefone, a.texto, a.estado
from public.alertas_simulados_praticagem a
join public.eventos_praticagem e on e.id = a.evento_id
order by a.criado_em desc limit 20;
```

Ausência de eventos quando as tabelas não mudam é normal. A última linha de
`coletas_praticagem` deve continuar recente enquanto o worker estiver ativo;
falhas aparecem com `resultado='falha'` e `erro_codigo`.

## Próxima etapa

Deixar o computador ligado e conectado à tomada por 24–72 horas. Conferir no
Supabase se `coletas_praticagem` continua recebendo linhas `sucesso` e revisar
qualquer linha `falha`, evento e alerta simulado. Somente depois de validar uma
transição real da fonte, considerar a entrega WhatsApp; não há código de envio
neste observador.

As simulações locais em `tests/test_praticagem_simulacao.py` cobrem previsão,
confirmação, andamento com mudança de horário e local, encerramento, fundeio,
releitura idêntica e desaparecimento de linha. Elas não inserem dados falsos
no Supabase e não substituem a observação de uma mudança real no portal.

O coletor legado foi removido. A captura autenticada é feita por
`praticagem_portal.py`, com análise de fases e comparação pelo observador.
