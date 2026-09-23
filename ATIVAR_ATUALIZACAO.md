# Ativar Atualizar no WhatsApp

## O que faz

Administradores pedem `Atualizar`. O webhook grava a solicitacao no Supabase e responde imediatamente.
O GitHub consulta a fila a cada cinco minutos (sujeito a atrasos do agendador), coleta uma vez
para os solicitantes do lote e envia o resumo individualmente. A coleta horaria continua existindo.
Os dois workflows compartilham o grupo de concorrencia para evitar sobreposicao no GitHub.
Nao executar coletas manuais no computador ao mesmo tempo que o executor hospedado.

## Ordem de implantacao

1. No SQL Editor do Supabase, executar `supabase/migrations/20260921190000_atualizacao_sob_demanda.sql` uma unica vez.
2. Enviar para a branch principal do GitHub os arquivos Python atualizados e ambos os workflows em `.github/workflows`.
3. Em GitHub Settings > Secrets and variables > Actions, conferir os secrets:
   `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SECRET_KEY`, `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`.
   Os secrets do Supabase nao sao copiados automaticamente para o GitHub.
   O token e o ID devem ser os mesmos validos para o numero corporativo que ja responde no bot.
4. Criar a variavel de Actions `ATUALIZACAO_CHAT_ATIVA=true`.
5. Executar manualmente `Processar Atualizacoes do Chat` e confirmar sucesso (fila vazia e normal).
6. Publicar o novo `supabase/functions/whatsapp-webhook/index.ts` no editor de Edge Functions.
7. Somente apos validar o executor, cadastrar o secret `ATUALIZACAO_CHAT_ATIVA=true` no Supabase.
8. Enviar `Ajuda`, depois `Atualizar` no WhatsApp de um administrador.
   Deve chegar a confirmacao, seguida do resumo com horario ou aviso de falha.
9. Pedir simultaneamente de dois administradores: ambos devem receber o resultado do mesmo lote.

## Diagnostico e recuperacao

- Tabelas `atualizacoes_chat` e `atualizacoes_chat_destinatarios` sao privadas, com RLS e acesso apenas service_role.
- Sem pedido, o executor termina sem coletar.
- Execucao interrompida: reserva vence em 40 minutos; proxima execucao recupera o lote.
- Coleta falhou: mensagem clara de falha; use Resumo para consultar dados antigos.
- Falha de entrega: paginas aceitas sao registradas; proxima execucao retoma a pagina pendente sem nova coleta.
- Aceite da API nao confirma entrega no celular. Consulte tambem os eventos de status do webhook.
- Queda entre aceite da Meta e registro no banco pode repetir uma pagina. Nao ha garantia de entrega exatamente uma vez.
- Pedidos com 23 horas expiram sem envio de texto livre, para evitar ultrapassar a janela de atendimento.
  Ficam marcados como expirados no banco; e necessario um novo pedido. O GitHub registra esse fato.
- Para ocultar e desativar novos pedidos, mudar o secret do Supabase para false.
- Para pausar o executor, mudar a variavel do GitHub para false. Pedidos existentes ficam aguardando.

## Limites

Nao e tempo real e nao ha prazo garantido do GitHub. Falhas em fontes obrigatorias invalidam a coleta;
nao afirmar atualizacao completa quando uma fonte obrigatoria falha. Fontes sem integracao autorizada,
como praticagem, nao sao adicionadas por esta mudanca. Os horarios apresentados sao das fontes existentes.
Rotina horaria e coleta sob demanda usam a mesma lista compartilhada. Pedidos durante a coleta horaria
podem causar uma coleta adicional ao terminar; pedidos simultaneos via chat compartilham o lote sob demanda.

## Disparo direto do GitHub (sem esperar o agendamento)

1. Criar um fine-grained personal access token com acesso somente a
   `TfGuardian/sgs-monitor-navios`, permissao de repositorio Actions: Read and write.
   Metadata: Read e automatica. Nao conceder Contents: Write nem acesso a todos os repositorios.
   O token precisa pertencer a uma conta com acesso adequado ao repositorio e atender
   eventuais aprovacoes da organizacao. Se o repositorio nao aparecer, pedir ao proprietario
   para configurar a credencial restrita; nao ampliar permissoes para contornar a ausencia.
2. Salvar o token apenas nos Secrets das Edge Functions do Supabase como `GH_ACTIONS_TOKEN`.
   Nao confundir com o token da Meta. Registrar a data de expiracao para renovacao.
3. Publicar a versao atual de `supabase/functions/whatsapp-webhook/index.ts`.
4. Enviar `Atualizar`: deve confirmar que o acionamento foi aceito; conferir nova execucao
   do workflow e entrega do resumo. Isso nao garante inicio instantaneo: ainda existe fila do GitHub.
5. Logs `disparo_github` mostram apenas resultado e status HTTP. Em caso de falha, o pedido
   permanece salvo e a resposta avisa que o acionamento nao foi confirmado.

Nao e necessaria nova migracao SQL nem mudar o workflow. A reserva e a concorrencia existentes
continuam evitando coleta simultanea por estes workflows. Cada comando pode gerar uma execucao;
execucoes extras sem pedidos terminam sem coletar. O agendamento permanece como recuperacao.
Para o simulador local, `GH_ACTIONS_TOKEN` e opcional no ambiente; sem ele, o pedido fica na fila.
Nao e necessario cadastrar esse token nos secrets do GitHub para o executor processar a fila.
Se o token expirar ou for revogado, o disparo direto falha com o pedido preservado.

## Confirmacao de remocao apos Atualizar

1. Aplicar `supabase/migrations/20260923120000_confirmar_indisponiveis.sql` no SQL Editor.
2. Publicar o `index.ts` atualizado na Edge Function.
3. Atualizar `atualizacao_chat.py`, `lista_monitoramento.py` e `chat.py` na raiz do GitHub.
4. Enviar Atualizar com administrador. Depois do resumo, havendo indisponiveis, o bot pergunta
   se deve remove-los. Confirmar/SIM remove somente a selecao; Cancelar/NAO mantem a lista.

A selecao e salva a partir do mesmo conjunto de dados que produziu o resumo e revalidada no envio
 e na confirmacao. A confirmacao expira em dez minutos. Uma operacao pendente valida e preservada,
por isso nao e substituida pela pergunta automatica. Uma coleta com falha nao gera sugestao.
Apos duas ausencias o sincronizador ja remove dados operacionais; agora e possivel confirmar tambem
 a retirada da lista compartilhada. Apenas desatualizacao por horario nao e motivo para oferecer remocao.
Nao envia essa pergunta a usuarios sem permissao administrativa. A pergunta e enviada depois que
 todas as partes do resumo forem aceitas pela API; aceite nao e comprovacao de entrega/leitura.
Lotes anteriores sem snapshot de indisponiveis nao geram perguntas; solicite nova Atualizar.
Esta etapa abrange Atualizar; Resumo e o relatorio horario nao abrem confirmacoes automaticamente.
As migracoes foram testadas em PostgreSQL em memoria com PGlite, alem dos testes Python.


## Cruzamento de fundeados

Publicar juntos `monitor_fundeados.py`, `monitor_atracados.py`, `config.py`,
`sincronizador.py` e `consulta_navio.py` no executor Python. Publicar também
`supabase/functions/whatsapp-webhook/index.ts` para a inclusão e consulta pelo WhatsApp.
Não requer nova migração para os status: utiliza os campos evento e fonte existentes.
FUNDEADOS_URL é opcional; o padrão é a página oficial da APS de navios fundeados.

A relação de fundeados é obrigatória em cada coleta: erro HTTP ou formato desconhecido
aborta o catálogo antes de sincronizar ou propor remoções. Uma tabela reconhecida vazia
é diferente de uma página de erro. Terminal dos fundeados é exibido como terminal previsto.
Chegada/Arrival não é convertida em ETA, data de fundeio ou atualização da fonte.

O cruzamento usa IMO quando disponível (ignorando zeros iniciais), nome normalizado,
viagem e DUV. Divergências de escala, homônimos com IMO distintos, duplicatas ambíguas
ou presença simultânea em fundeados e atracados resultam em Situação em verificação.
Não há desempate por ordem de download ou por ETB. Ainda não há data efetiva de
atualização comum às fontes que permita resolver esses casos automaticamente.

A programação fornece ETA/ETB; não comprova manobra em andamento. Para atracados,
o ETB é omitido: não deve ser rotulado como data efetiva de atracação. Uma fonte
explícita de data efetiva será necessária para exibir Atracado em com segurança.

Validação: 75 testes Python; cenários TypeScript de cruzamento e apresentação;
coleta real das quatro páginas somente de leitura, sem banco nem WhatsApp.
