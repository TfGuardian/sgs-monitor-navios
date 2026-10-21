# Comando `Observador` pelo WhatsApp

**Estado em 09/10/2026:** migração executada, função `whatsapp-webhook`
publicada e tarefas do Windows registradas. Um pedido administrativo feito
diretamente na fila terminou como `concluido` e reiniciou o observador.
Ainda é útil enviar **Observador** pelo próprio WhatsApp para validar a
entrada e a resposta na conversa.

O administrador envia **Observador**. O webhook registra um pedido no Supabase e
confirma o recebimento. Uma tarefa leve no computador consulta a fila a cada
15 segundos e inicia ou reinicia a tarefa **SGS Praticagem Observador**.

O pedido fica registrado caso o computador esteja desligado, sem internet ou
em suspensão. Ele será processado depois que o usuário entrar no Windows e a
conexão voltar. A resposta imediata no WhatsApp confirma o pedido, não o
resultado da execução no computador.

## Publicar no Supabase

1. No **SQL Editor** do projeto, execute o conteúdo de
   [`supabase/migrations/20261009150000_comando_observador.sql`](../supabase/migrations/20261009150000_comando_observador.sql).
2. Publique a versão atualizada de
   [`supabase/functions/whatsapp-webhook/index.ts`](../supabase/functions/whatsapp-webhook/index.ts)
   na função `whatsapp-webhook`.
3. No SQL Editor, confira:

   ```sql
   select proname from pg_proc
   where pronamespace = 'public'::regnamespace
     and proname in ('solicitar_observador',
       'reservar_pedido_observador', 'concluir_pedido_observador');
   ```

## Instalar neste computador

Instale primeiro `requirements-praticagem.txt` no Python escolhido. O instalador
aceita `-Python CAMINHO` para usar esse interpretador. Tarefas antigas continuam
válidas pelas entradas de compatibilidade da raiz.

As tarefas foram instaladas neste Windows. Caso precise instalá-las novamente:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\instalar_observador.ps1
```

O script cria a tarefa do observador se ela ainda não existir e cria/inicia a
tarefa independente **SGS Praticagem Controle**. Esta última deve permanecer
ativa para receber os pedidos enquanto o observador estiver parado.

## Conferir

```powershell
Get-ScheduledTask -TaskName 'SGS Praticagem Observador','SGS Praticagem Controle' |
  Select-Object TaskName,State
Get-Content -LiteralPath .\var\logs\controle-observador.log -Tail 15
Get-Content -LiteralPath .\var\logs\praticagem-worker.log -Tail 15
```

Após enviar **Observador** no WhatsApp, o log de controle deve mostrar
`pedido ... concluido`, e a tarefa do observador deve ficar `Running`.
No Supabase:

```sql
select solicitado_em, estado, concluido_em, resultado
from public.pedidos_observador
order by solicitado_em desc limit 5;
```

O comando é aceito apenas de números ativos em `administradores_chat`.
Nenhum texto recebido pelo WhatsApp é executado como comando no Windows.
