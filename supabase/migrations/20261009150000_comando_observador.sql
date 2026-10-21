-- Pedidos do WhatsApp para iniciar/reiniciar a tarefa local do observador.
-- Apenas a chave administrativa acessa a fila; o computador a consulta.
create table if not exists public.pedidos_observador (
  id uuid primary key default gen_random_uuid(),
  telefone text not null check (telefone ~ '^[0-9]{10,15}$'),
  estado text not null default 'pendente'
    check (estado in ('pendente', 'executando', 'concluido', 'falha')),
  solicitado_em timestamptz not null default now(),
  reserva_token uuid,
  reserva_ate timestamptz,
  concluido_em timestamptz,
  resultado text
);
create index if not exists pedidos_observador_pendentes_idx
  on public.pedidos_observador (solicitado_em)
  where estado in ('pendente', 'executando');

alter table public.pedidos_observador enable row level security;
revoke all on public.pedidos_observador from public, anon, authenticated;
grant all on public.pedidos_observador to service_role;

create or replace function public.solicitar_observador(numero text)
returns uuid language plpgsql security definer set search_path = public as $$
declare pedido uuid;
begin
  if not exists (select 1 from administradores_chat
                 where telefone = numero and ativo) then
    raise exception 'Numero sem permissao administrativa';
  end if;
  perform pg_advisory_xact_lock(9102026);
  select id into pedido from pedidos_observador
    where estado = 'pendente' order by solicitado_em limit 1;
  if pedido is null then
    insert into pedidos_observador(telefone) values (numero)
      returning id into pedido;
  end if;
  return pedido;
end $$;

create or replace function public.reservar_pedido_observador()
returns table(pedido_id uuid, token uuid)
language plpgsql security definer set search_path = public as $$
begin
  return query
    update pedidos_observador p
       set estado = 'executando', reserva_token = gen_random_uuid(),
           reserva_ate = now() + interval '2 minutes'
     where p.id = (
       select q.id from pedidos_observador q
        where q.estado = 'pendente'
           or (q.estado = 'executando' and q.reserva_ate < now())
        order by q.solicitado_em
        for update skip locked limit 1
     )
     returning p.id, p.reserva_token;
end $$;

create or replace function public.concluir_pedido_observador(
  pedido uuid, token uuid, sucesso boolean, detalhe text)
returns boolean language plpgsql security definer set search_path = public as $$
declare atualizado uuid;
begin
  update pedidos_observador
     set estado = case when sucesso then 'concluido' else 'falha' end,
         resultado = left(coalesce(detalhe, ''), 500),
         concluido_em = now(), reserva_ate = null, reserva_token = null
   where id = pedido and reserva_token = token and estado = 'executando'
   returning id into atualizado;
  return atualizado is not null;
end $$;

revoke all on function public.solicitar_observador(text),
  public.reservar_pedido_observador(),
  public.concluir_pedido_observador(uuid,uuid,boolean,text)
  from public, anon, authenticated;
grant execute on function public.solicitar_observador(text),
  public.reservar_pedido_observador(),
  public.concluir_pedido_observador(uuid,uuid,boolean,text)
  to service_role;
