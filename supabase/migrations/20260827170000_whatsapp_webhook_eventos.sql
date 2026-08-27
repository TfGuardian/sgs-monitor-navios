create table if not exists public.whatsapp_webhook_eventos (
  message_id text primary key,
  remetente text not null,
  mensagem text,
  processado_em timestamptz not null default now()
);

alter table public.whatsapp_webhook_eventos enable row level security;

comment on table public.whatsapp_webhook_eventos is
'Controle interno para impedir respostas duplicadas a webhooks da Meta.';

