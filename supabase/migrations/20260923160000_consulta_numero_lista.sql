-- Last displayed ordering, isolated per sender. No anonymous/client access.
create table if not exists public.listas_exibidas_chat (
  telefone text primary key,
  itens jsonb not null check (jsonb_typeof(itens) = 'array'),
  atualizado_em timestamptz not null default now()
);
alter table public.listas_exibidas_chat enable row level security;
revoke all on public.listas_exibidas_chat from public, anon, authenticated;
grant select, insert, update, delete on public.listas_exibidas_chat to service_role;
