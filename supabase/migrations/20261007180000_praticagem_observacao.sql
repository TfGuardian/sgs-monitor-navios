-- Modo de observação da Praticagem. Não envia mensagens nem altera o monitor APS.
create table if not exists public.coletas_praticagem (
  id uuid primary key default gen_random_uuid(),
  iniciado_em timestamptz not null default now(),
  concluido_em timestamptz,
  resultado text not null default 'executando'
    check (resultado in ('executando', 'sucesso', 'falha')),
  quantidades jsonb not null default '{}'::jsonb,
  erro_codigo text,
  duracao_ms integer check (duracao_ms is null or duracao_ms >= 0)
);

create table if not exists public.estados_praticagem (
  imo text primary key,
  nome text not null,
  dados jsonb not null,
  coleta_id uuid not null references public.coletas_praticagem(id),
  atualizado_em timestamptz not null default now()
);

create table if not exists public.eventos_praticagem (
  id uuid primary key default gen_random_uuid(),
  coleta_id uuid not null references public.coletas_praticagem(id),
  imo text not null,
  nome text not null,
  chave_manobra text,
  mudancas jsonb not null,
  detectado_em timestamptz not null default now(),
  unique (coleta_id, imo, chave_manobra)
);

create table if not exists public.alertas_simulados_praticagem (
  evento_id uuid not null references public.eventos_praticagem(id),
  telefone text not null check (telefone ~ '^[0-9]{10,15}$'),
  texto text not null,
  estado text not null default 'nao_enviado'
    check (estado = 'nao_enviado'),
  criado_em timestamptz not null default now(),
  primary key (evento_id, telefone)
);

create table if not exists public.controle_praticagem (
  id boolean primary key default true check (id),
  reserva_token uuid,
  reserva_ate timestamptz
);
insert into public.controle_praticagem(id) values(true) on conflict do nothing;

create index if not exists coletas_praticagem_iniciado_idx
  on public.coletas_praticagem (iniciado_em desc);
create index if not exists eventos_praticagem_detectado_idx
  on public.eventos_praticagem (detectado_em desc);

alter table public.coletas_praticagem enable row level security;
alter table public.estados_praticagem enable row level security;
alter table public.eventos_praticagem enable row level security;
alter table public.alertas_simulados_praticagem enable row level security;
alter table public.controle_praticagem enable row level security;
revoke all on public.coletas_praticagem, public.estados_praticagem,
  public.eventos_praticagem, public.alertas_simulados_praticagem,
  public.controle_praticagem
  from public, anon, authenticated;
grant all on public.coletas_praticagem, public.estados_praticagem,
  public.eventos_praticagem, public.alertas_simulados_praticagem,
  public.controle_praticagem
  to service_role;

create or replace function public.reservar_coleta_praticagem()
returns uuid language plpgsql security definer set search_path=public as $$
declare token uuid;
begin
  update controle_praticagem
    set reserva_token=gen_random_uuid(), reserva_ate=now()+interval '3 minutes'
    where id and (reserva_ate is null or reserva_ate<now())
    returning reserva_token into token;
  return token;
end $$;

create or replace function public.concluir_observacao_praticagem(
  p_token uuid, p_estados jsonb, p_eventos jsonb,
  p_quantidades jsonb, p_duracao_ms integer)
returns uuid language plpgsql security definer set search_path=public as $$
declare
  v_coleta uuid;
  v_evento uuid;
  item jsonb;
  aviso jsonb;
begin
  perform 1 from controle_praticagem
    where id and reserva_token=p_token and reserva_ate>now() for update;
  if not found then raise exception 'Reserva de coleta inválida ou expirada'; end if;
  if jsonb_typeof(p_estados)<>'array' or jsonb_typeof(p_eventos)<>'array' then
    raise exception 'Estados e eventos devem ser arrays'; end if;
  insert into coletas_praticagem(iniciado_em,resultado,concluido_em,quantidades,duracao_ms)
    values(now()-p_duracao_ms*interval '1 millisecond',
           'sucesso',now(),coalesce(p_quantidades,'{}'::jsonb),p_duracao_ms)
    returning id into v_coleta;
  for item in select value from jsonb_array_elements(p_estados) loop
    if coalesce(item->>'imo','')='' then raise exception 'Estado sem IMO'; end if;
    insert into estados_praticagem(imo,nome,dados,coleta_id)
      values(item->>'imo',coalesce(item->>'nome',''),item,v_coleta)
      on conflict(imo) do update set nome=excluded.nome,dados=excluded.dados,
        coleta_id=excluded.coleta_id,atualizado_em=now();
  end loop;
  for item in select value from jsonb_array_elements(p_eventos) loop
    insert into eventos_praticagem(coleta_id,imo,nome,chave_manobra,mudancas)
      values(v_coleta,item->>'imo',coalesce(item->>'nome',''),
             item->>'manobra',item->'mudancas')
      returning id into v_evento;
    for aviso in select value from jsonb_array_elements(
      coalesce(item->'alertas','[]'::jsonb)) loop
      insert into alertas_simulados_praticagem(evento_id,telefone,texto)
        select v_evento,aviso->>'telefone',aviso->>'texto'
        where exists(select 1 from destinatarios_relatorio d
                     where d.telefone=aviso->>'telefone' and d.ativo);
    end loop;
  end loop;
  update controle_praticagem set reserva_token=null,reserva_ate=null where id;
  return v_coleta;
end $$;

create or replace function public.registrar_falha_praticagem(
  p_token uuid, p_erro_codigo text, p_duracao_ms integer)
returns uuid language plpgsql security definer set search_path=public as $$
declare v_coleta uuid;
begin
  perform 1 from controle_praticagem
    where id and reserva_token=p_token and reserva_ate>now() for update;
  if not found then raise exception 'Reserva de coleta inválida ou expirada'; end if;
  insert into coletas_praticagem(iniciado_em,resultado,concluido_em,erro_codigo,duracao_ms)
    values(now()-p_duracao_ms*interval '1 millisecond',
           'falha',now(),left(p_erro_codigo,100),p_duracao_ms)
    returning id into v_coleta;
  update controle_praticagem set reserva_token=null,reserva_ate=null where id;
  return v_coleta;
end $$;

revoke all on function public.reservar_coleta_praticagem(),
  public.concluir_observacao_praticagem(uuid,jsonb,jsonb,jsonb,integer),
  public.registrar_falha_praticagem(uuid,text,integer)
  from public,anon,authenticated;
grant execute on function public.reservar_coleta_praticagem(),
  public.concluir_observacao_praticagem(uuid,jsonb,jsonb,jsonb,integer),
  public.registrar_falha_praticagem(uuid,text,integer)
  to service_role;

comment on table public.alertas_simulados_praticagem is
  'Mensagens que seriam enviadas; esta tabela nunca aciona a API da Meta.';
