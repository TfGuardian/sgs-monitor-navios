# Ativar o relatório automático por WhatsApp

## O que foi preparado

- Um relatório completo por hora, mesmo sem mudanças, para todos os inscritos ativos.
- Coleta nova nas quatro fontes antes de montar o relatório. Uma falha não apresenta dados antigos como atualizados.
- Dois navios por mensagem, com emojis e separadores; inclui indisponíveis. Uma lista de 10 navios gera 5 mensagens por destinatário.
- Snapshot e progresso persistidos. Novas tentativas reutilizam os mesmos dados e não reenviam partes aceitas.
- Assinatura cancelada por `Parar` é verificada antes de cada envio.
- Aceite da API e entrega no telefone são estados diferentes. O webhook registra `sent`, `delivered`, `read` e `failed`.

**Ainda exige ativação:** migração no Supabase, atualização do webhook, modelo aprovado pela Meta, variáveis no GitHub e agendamento.

## 1. Preparar o banco e o webhook

No SQL Editor do Supabase, executar **uma vez**:
`supabase/migrations/20260925160000_relatorios_horarios.sql`.

Depois atualizar a função `whatsapp-webhook` usando o conteúdo completo de
`supabase/functions/whatsapp-webhook/index.ts` e clicar em Deploy updates.
Manter a configuração de assinatura Meta existente.

## 2. Aprovar o modelo na Meta

No Gerenciador do WhatsApp, abrir Modelos de mensagem e criar:

- Nome: `relatorio_horario_navios_v2`
- Idioma: Português (BR), código `pt_BR`
- Categoria proposta: Utilidade (a Meta decide a aprovação e a classificação)
- Apenas corpo, com parâmetros numéricos de `{{1}}` a `{{12}}`.
- Sem cabeçalho, rodapé ou botões adicionais.

Copiar o corpo integral de `templates/relatorio_horario_navios_v2.txt`.
O arquivo JSON no mesmo diretório contém os exemplos de cada variável e a estrutura para cadastro pela API. Os exemplos são fictícios.
Não reutilizar o modelo antigo de uma variável.

As quebras de linha pertencem ao texto fixo. Os valores das variáveis são linhas simples.
O sistema recusa conteúdo acima do limite em vez de cortar dados.
Para uma lista ímpar, a última posição informa `Fim da lista`; lista vazia também recebe aviso.

## 3. Configurar o GitHub depois da aprovação

Settings → Secrets and variables → Actions → Variables:

| Nome | Valor |
|---|---|
| META_REPORT_TEMPLATE_NAME | relatorio_horario_navios_v2 |
| META_REPORT_TEMPLATE_LANGUAGE | pt_BR |
| RELATORIO_WHATSAPP_ATIVO | true |

Os secrets `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `SUPABASE_URL` e a chave administrativa do Supabase continuam necessários. Não trocar chaves que já funcionam sem necessidade.

Executar manualmente **Executar Monitor APS**. Isso envia aos inscritos ativos.
Conferir todos os navios e as partes no WhatsApp. Uma segunda execução na mesma hora não cria outro relatório.
Se o teste falhar, inspecionar as entregas antes de repetir ou modificar os registros.

## 4. Ativar o agendamento no Supabase

Criar um token GitHub fine-grained limitado ao repositório `TfGuardian/sgs-monitor-navios`, com permissão **Actions: Read and write**.
No Vault do Supabase, cadastrar esse token com o nome `sgs_github_actions_token`.
Não enviar o token em conversas ou salvá-lo em arquivos do repositório.

Executar `supabase/ativar_agendamento_horario.sql` no SQL Editor após o teste manual bem-sucedido.
O Cron verifica a cada 5 minutos e aciona o GitHub se a hora atual ainda não foi processada. Uma reserva impede execuções concorrentes do relatório. Novo disparo ocorre no máximo a cada 10 minutos enquanto há pendências. O agendamento GitHub existente permanece como alternativa; a fila evita dois relatórios na mesma hora.

**Precisão:** a coleta começa após o acionamento e depende da fila do GitHub e da disponibilidade das fontes. Isso melhora a regularidade, mas não garante chegada em minuto exato. Para uma exigência rígida de prazo, o worker Python precisa de um executor dedicado, independente do GitHub Actions.

## 5. Validar a operação

Validar três horas consecutivas sem intervenção: uma nova coleta por hora, todos os navios presentes, todos os destinatários com as partes entregues. Validar também fora da janela de 24 horas de conversa.

No SQL Editor:

```sql
select r.hora, r.criado_em, r.concluido_em,
       e.estado, count(*) as partes
from public.relatorios_horarios r
left join public.entregas_horarias e on e.relatorio_id=r.id
where r.hora >= now()-interval '24 hours'
group by r.hora,r.criado_em,r.concluido_em,e.estado
order by r.hora desc,e.estado;
```

`concluido_em` indica submissão concluída, **não entrega confirmada**.
`delivered` ou `read` confirma entrega. `aceito`/`sent` ainda não comprova que o telefone recebeu.
As horas são armazenadas em UTC; o WhatsApp exibe Brasília.

Rejeições HTTP 4xx têm até três tentativas na mesma hora, com intervalo mínimo de 5 minutos. `failed` (falha posterior informada pela Meta), `incerto` e `enviando` sem retorno exigem diagnóstico; não repetir cegamente. Timeout ou erro 5xx podem acontecer depois do aceite: não existe garantia de envio exatamente uma vez entre a API externa e o banco. A correlação do webhook permite reconciliar retornos tardios.

Não há recuperação automática de todas as horas perdidas: o próximo ciclo gera um relatório novo, evitando uma sequência de relatórios antigos. Não há alerta externo de ausência total de execução nesta versão; consultar o histórico e habilitar notificações de falha do GitHub.

## Pausar

Definir `RELATORIO_WHATSAPP_ATIVO=false` no GitHub **e** executar:

```sql
select cron.unschedule('sgs-relatorio-horario');
```

O comando `Atualizar` continua independente do relatório horário.

Referência do agendador: https://supabase.com/docs/guides/cron
