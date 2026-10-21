# Alertas de manobras da Praticagem — briefing

## Objetivo

Avisar no WhatsApp cada inscrito quando uma manobra de um navio da lista de
monitoramento mudar de fase no portal da SP Pilots. Este fluxo é independente
do relatório automático de hora em hora, que permanece desativado.

## Evidência observada em 02/10/2026

Área autenticada: https://login.sppilots.com.br/servicos (Santos).

- `Movimentos de Navios`: IMO, navio, MV, locais 1/2, POB, PASSAG, calado,
  agente, bordo e TUG. A cor da linha distingue manobra em previsão,
  confirmada pela Praticagem, em andamento e encerrada.
- `Manobras Previstas`: IMO, navio, MV, locais 1/2, agente, bordo e TUG.
- `Navios Atracados`: IMO, navio e local.
- `Navios Fundeados`: IMO, navio e horário de fundeio.
- As tabelas se sobrepõem. No mesmo acesso, TORINO (IMO 9398321) aparecia com
  movimento `E` encerrado e manobra `S` prevista. Logo, estado por navio não
  equivale a estado por manobra.

O acesso à interface foi confirmado. A nova fonte será coletada como as
tabelas do Porto de Santos: obter a página autenticada, ler suas tabelas,
normalizar as linhas e comparar cada coleta com o estado anterior. O mecanismo
interno pelo qual o site atualiza a própria página **não foi confirmado** e
não é requisito para essa abordagem.

## Coleta proposta

1. Abrir sessão autenticada no portal com credenciais guardadas apenas no
   ambiente do coletor; nunca colocar senha no código, no banco ou nos logs.
2. Ler as quatro tabelas completas e preservar, em cada registro, tabela de
   origem, IMO, MV, locais, horários disponíveis e fase indicada pela cor da
   linha. A cor é um dado operacional: um parser que extraia apenas texto não
   basta para `Movimentos de Navios`.
3. Validar a coleta antes de comparar: sessão expirada, página de login,
   tabela vazia inesperada e estrutura alterada são falhas da fonte, não
   movimentos dos navios.
4. Cruzar somente os registros dos navios da lista ativa e salvar um snapshot
   com horário da consulta. Comparar com o snapshot anterior e enfileirar
   alertas para cada mudança confirmada.
5. Executar o coletor continuamente em ciclos curtos, com **1 minuto como
   intervalo inicial proposto**. Enviar o aviso logo após detectar a mudança.
   O coletor atual da APS roda de hora em hora no GitHub Actions; para um
   ciclo de 1 minuto será necessário um executor próprio e confiável.

## Modelo de dados e regras

1. Cruzar o IMO da fonte com a lista ativa. Usar nome normalizado apenas como
   apoio quando o IMO estiver ausente; ambiguidades não geram alerta.
2. Manter dois conjuntos de estado independentes por IMO:
   - situação do navio: previsto, fundeado, atracado etc.;
   - manobras: cada ocorrência de `MV`, origem/destino, data e fase.
3. Não usar somente `IMO + MV` como chave: o mesmo navio pode ter várias
   entradas ou saídas. Também não tratar POB como identificador imutável,
   pois uma previsão pode mudar. Avaliar a existência de ID próprio da fonte;
   caso não haja, correlacionar ocorrências por direção, locais e janela
   temporal, com registro dos casos ambíguos.
4. Fases da manobra: `previsão -> confirmada -> em andamento -> encerrada`.
   Uma nova ocorrência pode começar em qualquer fase, conforme a fonte.
   Alterações de previsão são eventos distintos de avanço de fase.
5. A entrada em `Manobras Previstas` ou uma linha branca em `Movimentos` indica
   previsão. A fase de uma linha de `Movimentos` prevalece para a **mesma
   manobra**. Uma manobra antiga encerrada não prevalece sobre outra futura.
6. Presença em `Navios Atracados` ou `Navios Fundeados` descreve a situação
   física do navio, sem encerrar automaticamente sua manobra atual.
7. Desaparecimento de linha, erro de acesso ou resposta incompleta não prova
   cancelamento, conclusão nem saída. Nesses casos, conservar o último estado
   confirmado e registrar a saúde da fonte.
8. Fazer uma leitura inicial sem disparar avisos retroativos. Depois, gerar
   uma notificação por transição confirmada, com chave idempotente e fila de
   entrega para evitar duplicações após reinício ou falha da Meta.

## Eventos contemplados

- Primeira aparição de uma manobra em previsão e cada mudança de fase para
  confirmada, em andamento ou encerrada.
- Primeira aparição confirmada em `Navios Fundeados` ou `Navios Atracados`
  depois da leitura inicial. A ausência posterior, sozinha, não comprova
  desatracação, saída ou cancelamento.
- Quando fase de manobra e situação física mudarem na mesma coleta, compor um
  único evento claro para o navio, sem enviar duas mensagens redundantes.
- Mudanças de horário ou local da mesma manobra também geram aviso, mesmo sem
  mudança de fase. Comparar valores normalizados para ignorar diferenças
  apenas de formatação. Se vários campos mudarem na mesma coleta, compor um
  único aviso mostrando os valores anteriores e novos disponíveis.

## Mensagem proposta

```text
🚢 *BELUGA*
⚪ *Manobra em previsão*
📍 Local: 39
🕒 Atualizado pela Praticagem: ...
```

Depois, quando a **mesma manobra** avançar:

```text
🚢 *BELUGA*
🔵 *Manobra em andamento*
📍 Local: 39
🕒 Atualizado pela Praticagem: ...
```

Se apenas o horário ou local mudar:

```text
🚢 *BELUGA*
📝 *Manobra atualizada*
🕒 Horário: 14:00 → 15:30
📍 Local: 39 → 40
```

O texto final deve indicar entrada/saída/mudança somente após validar a
semântica da coluna `MV` com a fonte. Horários ausentes devem aparecer como
`N/A`, sem inventar um horário de evento a partir da hora de coleta.

## Requisito de latência

Com coleta de tabelas, o aviso sai imediatamente **após a detecção**, mas a
mudança só pode ser detectada na próxima consulta. Com intervalo de 1 minuto,
o atraso esperado pode chegar a aproximadamente 1 minuto mais o tempo de
publicação no site, processamento e entrega no WhatsApp. Isso é monitoramento
quase em tempo real, não recepção instantânea de eventos. Não prometer atraso
zero nem informar ao usuário que a manobra ocorreu na hora da coleta.

## Validação 24 horas sem WhatsApp (modo de observação)

- Manter `envio_whatsapp=false` por padrão. A coleta da Praticagem usa
  função, agendamento e tabelas próprios; não altera o monitor APS nem
  `navios_monitorados` durante a validação.
- Começar com uma prova de coleta autenticada: confirmar que o processo
  obtém as quatro tabelas e a fase indicada pela cor, inclusive após a
  renovação da sessão. Só então ativar o agendamento de 1 minuto.
- Usar Supabase Cron para invocar uma Edge Function a cada minuto se a
  autenticação e a leitura HTML couberem nos limites da função. Caso o site
  exija navegador completo ou processo persistente, usar um pequeno worker
  sempre ativo em vez de forçar o fluxo numa Edge Function.
- Gravar `coletas_praticagem` com instante, duração, sucesso/erro, quantidades
  por tabela e identificador do snapshot. Gravar `estados_praticagem` apenas
  para navios monitorados e `eventos_praticagem` quando ocorrer transição.
  Cada evento contém estado anterior, novo estado, manobra correlacionada,
  horário da detecção e evidência mínima da linha de origem.
- Produzir `alertas_simulados` com o texto que seria enviado, destinatários
  previstos e status `nao_enviado`. Os destinatários previstos são os números
  ativos em `destinatarios_relatorio`. Nenhum caminho do observador chama a
  API da Meta neste estágio.
- Disponibilizar consultas/visão no Supabase para últimos ciclos, falhas,
  eventos detectados e mensagens simuladas. Verificar automaticamente se
  faltar mais de um ciclo; o silêncio por ausência de manobras não deve ser
  confundido com observador parado.
- Testar a lógica sem esperar o porto mudar: reproduzir em ambiente de teste
  snapshots `previsão -> confirmada -> andamento -> encerrada`, sobreposição
  de entrada/saída, remoção temporária de linha e sessão expirada. Esses
  testes provam a comparação e o disparo simulado; somente uma mudança real
  da página comprova a captura fim a fim da fonte.
- Após 24–72 horas, revisar a estabilidade técnica e o volume de dados. Como
  transições dos navios escolhidos podem ser raras, manter o observador 24/7
  por semanas ou até capturar mudanças reais suficientes para validar a fonte.
  Reter histórico de eventos e resumos de ciclos; evitar armazenar HTML
  completo de cada minuto.

## Dependências antes da implementação

- Validar tecnicamente uma coleta autenticada repetível, inclusive captura da
  cor das linhas e renovação da sessão, e confirmar as condições de uso.
- Verificar a carga que um ciclo de 1 minuto impõe ao site e ajustar o
  intervalo se houver limites publicados ou respostas de contenção.
- Criar e aprovar o modelo de WhatsApp para alertas iniciados pelo sistema.
  A elegibilidade de pagamento da conta Meta também precisa estar regular.
- Reutilizar a inscrição existente: todos os números ativos em
  `destinatarios_relatorio` recebem os futuros alertas; novos usuários podem
  ativar com `Assinar` e qualquer usuário pode suspender com `Parar`.
  Atualizar os textos desses comandos para indicar que a inscrição também
  abrange alertas de manobra. No modo de observação, essas escolhas afetam
  apenas os destinatários previstos nas mensagens simuladas.

## Riscos do ciclo de 1 minuto e respostas previstas

- **Carga e restrições da fonte:** 1.440 consultas de página por dia (43.200
  em 30 dias) por coletor, além de recursos carregados pela página. Verificar
  limites e termos; usar uma única coleta compartilhada por todos os usuários,
  timeout, recuo progressivo e pausa diante de bloqueio ou HTTP 429.
- **Sessão e estrutura:** expiração de login, alteração do HTML ou das classes
  de cor pode produzir dados vazios ou errados. Validar autenticação, presença
  das quatro tabelas, cabeçalhos e legenda em cada coleta; alertar operação
  quando a fonte falhar, sem avisar usuários de falsa movimentação.
- **Fases rápidas entre consultas:** previsão e andamento podem ocorrer entre
  duas leituras. Informar a fase efetivamente observada, sem inventar fases
  intermediárias nem prometer histórico completo.
- **Sobreposição e identidade:** o mesmo IMO pode estar em tabelas diferentes
  ou ter manobras distintas simultâneas. Manter chave por ocorrência e
  direção; em caso ambíguo, registrar para revisão em vez de misturar fases.
- **Concorrência e duplicação:** duas execuções ou uma retomada após falha não
  devem disparar o mesmo aviso duas vezes. Persistir snapshot, transições e
  estado de entrega em banco, com reserva atômica e chave idempotente.
- **Entrega WhatsApp:** o alerta depende de modelo aprovado, conta habilitada
  para cobrança e confirmação de entrega pela Meta. Não confundir aceitação
  da API com recebimento no telefone; monitorar falhas e retentar com limite.
- **Executor:** o agendamento `schedule` do GitHub Actions aceita no mínimo
  5 minutos e pode atrasar. Para 1 minuto, escolher executor próprio e
  monitorar atrasos, falhas e consumo de recursos.

## Critérios de aceite

- TORINO com entrada encerrada e saída prevista gera aviso da **saída** sem
  regressão indevida do estado da entrada.
- Releitura de página idêntica não gera nova mensagem.
- Previsão -> andamento gera exatamente um novo aviso por destinatário.
- Alteração apenas do horário ou do local gera um aviso com antes/depois;
  mudança de ambos na mesma coleta gera um único aviso.
- Primeira entrada em fundeados/atracados após a leitura inicial gera aviso;
  mudança simultânea de fase e situação não duplica a comunicação.
- `Assinar` inclui novos destinatários e `Parar` exclui destinatários de
  novos alertas; números já ativos continuam elegíveis.
- Navio desaparecido ou fonte indisponível não gera aviso de encerramento.
- Um navio fora da lista não gera aviso.
- A latência declarada corresponde ao mecanismo de atualização efetivamente
  confirmado na origem.
