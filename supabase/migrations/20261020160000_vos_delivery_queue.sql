begin;

create table public.vos_delivery_queue (
  id uuid primary key default gen_random_uuid(),
  sequence_id bigint generated always as identity unique,
  payload jsonb not null,
  attempts integer not null default 0,
  available_at timestamptz not null default now(),
  lease_token uuid,
  lease_until timestamptz,
  delivered_at timestamptz,
  last_error text,
  created_at timestamptz not null default now()
);
create index vos_delivery_pending_idx on public.vos_delivery_queue(sequence_id)
  where delivered_at is null;
alter table public.vos_delivery_queue enable row level security;
revoke all on public.vos_delivery_queue from public, anon, authenticated;
grant select, update, insert on public.vos_delivery_queue to service_role;
grant usage, select on sequence public.vos_delivery_queue_sequence_id_seq to service_role;

create function public.enqueue_vos_watch() returns trigger
language plpgsql security definer set search_path = public as $$
declare delivery uuid := gen_random_uuid();
begin
  insert into vos_delivery_queue(id, payload) values(delivery, jsonb_build_object(
    'deliveryId', delivery::text, 'kind', 'monitoring.updated',
    'watchId', new.id::text, 'vesselName', new.nome_confirmado,
    'occurredAt', coalesce(new.atualizado_em, now()),
    'active', new.ativo));
  return new;
end $$;
create trigger vos_watch_delivery after insert or update of ativo, nome_confirmado
  on public.lista_monitoramento for each row execute function public.enqueue_vos_watch();

create function public.enqueue_vos_movement() returns trigger
language plpgsql security definer set search_path = public as $$
declare watch public.lista_monitoramento%rowtype;
  delivery uuid := gen_random_uuid();
  body text;
  title text := 'Vessel movement updated';
begin
  -- Exact normalized name; never equate the legacy internal name key with an IMO.
  select * into watch from lista_monitoramento
    where ativo and upper(regexp_replace(btrim(nome_confirmado), '\s+', ' ', 'g'))
      = upper(regexp_replace(btrim(new.nome), '\s+', ' ', 'g'))
    order by id limit 1;
  if not found then return new; end if;
  select case value->>'depois'
    when 'previsao' then 'Maneuver scheduled'
    when 'confirmada' then 'Maneuver confirmed'
    when 'andamento' then 'Maneuver in progress'
    when 'encerrada' then 'Maneuver completed'
    else 'Vessel movement updated' end into title
    from jsonb_array_elements(new.mudancas) where value->>'campo'='fase' limit 1;
  title := coalesce(title, 'Vessel movement updated');
  select string_agg(
    format('%s: %s → %s',
      case value->>'campo' when 'fase' then 'Phase' when 'mv' then 'Maneuver code'
        when 'pob' then 'POB' when 'passag' then 'Passage'
        when 'local1' then 'Location 1' when 'local2' then 'Location 2'
        when 'fundeado' then 'Anchored' when 'atracado' then 'Berthed'
        else value->>'campo' end,
      coalesce(value->>'antes', 'N/A'), coalesce(value->>'depois', 'N/A')),
    E'\n' order by ordinality)
  into body from jsonb_array_elements(new.mudancas) with ordinality;
  insert into vos_delivery_queue(id, payload) values(delivery, jsonb_build_object(
    'deliveryId', delivery::text, 'kind', 'movement.detected',
    'watchId', watch.id::text, 'vesselName', new.nome,
    'occurredAt', new.detectado_em, 'eventId', new.id::text,
    'movement', jsonb_build_object(
      'title', title,
      'message', new.nome || E'\n' || coalesce(body, 'Movement detected'),
      'sourceTime', null,
      'changes', jsonb_build_object('maneuver', new.chave_manobra, 'items', new.mudancas))));
  return new;
end $$;
create trigger vos_movement_delivery after insert on public.eventos_praticagem
  for each row execute function public.enqueue_vos_movement();

-- One lease at a time and strict queue order, including retries.
create function public.claim_vos_delivery() returns jsonb
language plpgsql security definer set search_path = public as $$
declare queued vos_delivery_queue%rowtype; token uuid := gen_random_uuid();
begin
  if not pg_try_advisory_xact_lock(20261020, 1) then return null; end if;
  select * into queued from vos_delivery_queue where delivered_at is null
    order by sequence_id limit 1 for update;
  if not found or queued.available_at > now()
    or queued.lease_until > now() then return null; end if;
  update vos_delivery_queue set lease_token=token,
    lease_until=now()+interval '2 minutes', attempts=attempts+1
    where id=queued.id;
  return jsonb_build_object('id',queued.id,'leaseToken',token,'payload',queued.payload);
end $$;

create function public.finish_vos_delivery(p_id uuid, p_token uuid,
  p_success boolean, p_error text default null) returns boolean
language plpgsql security definer set search_path = public as $$
begin
  update vos_delivery_queue set
    delivered_at=case when p_success then now() else null end,
    available_at=case when p_success then available_at
      else now()+make_interval(secs => least(900, 15 * power(2, least(attempts,6)))::integer) end,
    last_error=case when p_success then null else left(p_error,100) end,
    lease_token=null, lease_until=null
  where id=p_id and lease_token=p_token and delivered_at is null;
  return found;
end $$;

revoke all on function public.enqueue_vos_watch(), public.enqueue_vos_movement(),
  public.claim_vos_delivery(), public.finish_vos_delivery(uuid,uuid,boolean,text)
  from public,anon,authenticated;
grant execute on function public.claim_vos_delivery(),
  public.finish_vos_delivery(uuid,uuid,boolean,text) to service_role;

-- Bootstrap only currently monitored vessels; do not replay historical alerts.
insert into public.vos_delivery_queue(id,payload)
select delivery, jsonb_build_object('deliveryId',delivery::text,
  'kind','monitoring.updated','watchId',id::text,'vesselName',nome_confirmado,
  'occurredAt',coalesce(atualizado_em,now()),'active',true)
from (select l.*,gen_random_uuid() delivery from public.lista_monitoramento l
  where ativo order by id) existing;

commit;
