-- Fila administrativa: somente o backend pode acessar.
create table public.atualizacoes_chat (
  id uuid primary key default gen_random_uuid(),
  estado text not null default 'pendente' check (estado in ('pendente','executando','pronto','concluido')),
  criado_em timestamptz not null default now(),
  reserva_ate timestamptz,
  ultima_tentativa timestamptz,
  paginas jsonb,
  resultado text,
  concluido_em timestamptz
);
create unique index atualizacoes_chat_ativa on public.atualizacoes_chat ((true))
  where estado in ('pendente','executando');
create table public.atualizacoes_chat_destinatarios (
  atualizacao_id uuid references public.atualizacoes_chat(id) on delete cascade,
  telefone text not null check (telefone ~ '^[0-9]{10,15}$'),
  solicitado_em timestamptz not null default now(),
  proxima_pagina integer not null default 0,
  enviado boolean not null default false,
  expirado boolean not null default false,
  primary key (atualizacao_id, telefone)
);
alter table public.atualizacoes_chat enable row level security;
alter table public.atualizacoes_chat_destinatarios enable row level security;
revoke all on public.atualizacoes_chat, public.atualizacoes_chat_destinatarios from anon, authenticated;
grant all on public.atualizacoes_chat, public.atualizacoes_chat_destinatarios to service_role;

create or replace function public.solicitar_atualizacao_chat(numero text)
returns uuid language plpgsql security definer set search_path = public as $$
declare lote uuid;
begin
  if not exists (select 1 from administradores_chat where telefone=numero and ativo) then
    raise exception 'Numero sem permissao administrativa';
  end if;
  perform pg_advisory_xact_lock(21092026);
  select id into lote from atualizacoes_chat where estado in ('pendente','executando') limit 1;
  if lote is null then
    insert into atualizacoes_chat default values returning id into lote;
  end if;
  insert into atualizacoes_chat_destinatarios(atualizacao_id,telefone) values (lote,numero)
    on conflict (atualizacao_id,telefone) do nothing;
  return lote;
end $$;

create or replace function public.reservar_atualizacao_chat()
returns setof public.atualizacoes_chat language plpgsql security definer set search_path = public as $$
declare lote uuid;
begin
  perform pg_advisory_xact_lock(21092026);
  if exists (select 1 from atualizacoes_chat where reserva_ate > now() and estado <> 'concluido') then
    return;
  end if;
  select id into lote from atualizacoes_chat
    where estado <> 'concluido'
    order by coalesce(ultima_tentativa, criado_em), criado_em limit 1 for update;
  if lote is null then return; end if;
  return query update atualizacoes_chat set
    estado=case when estado='pronto' then 'pronto' else 'executando' end,
    reserva_ate=now()+interval '40 minutes', ultima_tentativa=now()
    where id=lote returning *;
end $$;

-- Fecha a lista de solicitantes de forma atomica antes de iniciar as entregas.
create or replace function public.finalizar_coleta_chat(lote uuid, conteudo jsonb, resultado_coleta text)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform pg_advisory_xact_lock(21092026);
  update atualizacoes_chat set estado='pronto',paginas=conteudo,resultado=resultado_coleta
    where id=lote and estado='executando';
end $$;
revoke all on function public.solicitar_atualizacao_chat(text), public.reservar_atualizacao_chat(),
 public.finalizar_coleta_chat(uuid,jsonb,text) from public, anon, authenticated;
grant execute on function public.solicitar_atualizacao_chat(text), public.reservar_atualizacao_chat(),
 public.finalizar_coleta_chat(uuid,jsonb,text) to service_role;
