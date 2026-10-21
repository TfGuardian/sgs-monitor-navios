-- Aplicar antes de publicar o worker e o webhook. Nenhum envio e ativado aqui.
create table public.relatorios_horarios (
  id uuid primary key default gen_random_uuid(),
  hora timestamptz not null unique,
  paginas jsonb,
  reserva_token uuid,
  reserva_ate timestamptz,
  criado_em timestamptz not null default now(),
  concluido_em timestamptz
);
create table public.entregas_horarias (
  id uuid primary key default gen_random_uuid(),
  relatorio_id uuid not null references public.relatorios_horarios(id),
  telefone text not null,
  pagina integer not null,
  parametros jsonb not null,
  estado text not null default 'pendente' check (estado in
    ('pendente','enviando','aceito','sent','delivered','read','failed','falha','incerto','cancelado')),
  tentativas integer not null default 0,
  message_id text,
  codigo_erro integer,
  atualizado_em timestamptz not null default now(),
  unique(relatorio_id,telefone,pagina)
);
alter table public.relatorios_horarios enable row level security;
alter table public.entregas_horarias enable row level security;
revoke all on public.relatorios_horarios, public.entregas_horarias from anon, authenticated;
grant all on public.relatorios_horarios, public.entregas_horarias to service_role;

create function public.reservar_relatorio_horario()
returns setof public.relatorios_horarios language plpgsql security definer set search_path=public as $$
declare escolhido uuid; hora_atual timestamptz := date_trunc('hour',now());
begin
  perform pg_advisory_xact_lock(25092026);
  if exists(select 1 from relatorios_horarios where reserva_ate > now()) then return; end if;
  -- Nao enviar uma fila de relatorios antigos depois de uma indisponibilidade.
  insert into relatorios_horarios(hora) values(hora_atual) on conflict(hora) do nothing;
  select id into escolhido from relatorios_horarios where hora=hora_atual and concluido_em is null;
  if escolhido is null then return; end if;
  return query update relatorios_horarios set reserva_token=gen_random_uuid(),
    reserva_ate=now()+interval '35 minutes' where id=escolhido returning *;
end $$;

create function public.validar_reserva_horaria(lote uuid, token uuid)
returns void language plpgsql security definer set search_path=public as $$
begin
  perform 1 from relatorios_horarios where id=lote and reserva_token=token and reserva_ate>now() for update;
  if not found then raise exception 'Reserva horaria invalida ou expirada'; end if;
end $$;

create function public.preparar_relatorio_horario(lote uuid, token uuid, conteudo jsonb)
returns void language plpgsql security definer set search_path=public as $$
begin
  perform validar_reserva_horaria(lote,token);
  if jsonb_typeof(conteudo)<>'array' or jsonb_array_length(conteudo)=0 then
    raise exception 'Relatorio vazio'; end if;
  if (select paginas is not null from relatorios_horarios where id=lote) then return; end if;
  update relatorios_horarios set paginas=conteudo where id=lote;
  insert into entregas_horarias(relatorio_id,telefone,pagina,parametros)
    select lote,d.telefone,p.n::integer,p.valor from destinatarios_relatorio d
    cross join jsonb_array_elements(conteudo) with ordinality p(valor,n) where d.ativo;
end $$;

create function public.listar_entregas_horarias(lote uuid, token uuid)
returns setof public.entregas_horarias language plpgsql security definer set search_path=public as $$
begin
  perform validar_reserva_horaria(lote,token);
  return query select * from entregas_horarias where relatorio_id=lote
    and (estado='pendente' or (estado='falha' and tentativas<3
      and atualizado_em < now()-interval '5 minutes')) order by telefone,pagina;
end $$;

create function public.iniciar_entrega_horaria(lote uuid, token uuid, entrega uuid)
returns boolean language plpgsql security definer set search_path=public as $$
begin
  perform validar_reserva_horaria(lote,token);
  update entregas_horarias e set estado='cancelado',atualizado_em=now()
    where e.id=entrega and e.relatorio_id=lote and not exists
      (select 1 from destinatarios_relatorio d where d.telefone=e.telefone and d.ativo);
  update entregas_horarias set estado='enviando',tentativas=tentativas+1,atualizado_em=now()
    where id=entrega and relatorio_id=lote and estado in ('pendente','falha') and tentativas<3;
  return found;
end $$;

create function public.finalizar_entrega_horaria(lote uuid, token uuid, entrega uuid, resultado text, mensagem text)
returns void language plpgsql security definer set search_path=public as $$
begin
  perform validar_reserva_horaria(lote,token);
  if resultado not in ('aceito','falha','incerto') then raise exception 'Resultado invalido'; end if;
  -- O webhook pode chegar antes da resposta HTTP: nao regredir um status.
  update entregas_horarias set estado=resultado,message_id=coalesce(mensagem,message_id),atualizado_em=now()
    where id=entrega and relatorio_id=lote and estado='enviando';
end $$;

create function public.registrar_status_horario(entrega uuid, mensagem text, situacao text, codigo integer default null)
returns void language plpgsql security definer set search_path=public as $$
begin
  if situacao not in ('sent','delivered','read','failed') then return; end if;
  update entregas_horarias set estado=situacao,message_id=mensagem,codigo_erro=codigo,atualizado_em=now()
    where id=entrega and estado not in ('cancelado','read')
      and (message_id is null or message_id=mensagem)
      and not (estado='delivered' and situacao in ('sent','failed'))
      and not (estado='failed' and situacao='sent');
end $$;

create function public.concluir_relatorio_horario(lote uuid, token uuid)
returns integer language plpgsql security definer set search_path=public as $$
declare pendentes integer;
begin
  perform validar_reserva_horaria(lote,token);
  select count(*) into pendentes from entregas_horarias where relatorio_id=lote
    and estado not in ('aceito','sent','delivered','read','cancelado');
  if pendentes=0 then update relatorios_horarios set concluido_em=now() where id=lote; end if;
  return pendentes;
end $$;

create function public.liberar_relatorio_horario(lote uuid, token uuid)
returns void language sql security definer set search_path=public as $$
  update relatorios_horarios set reserva_ate=null where id=lote and reserva_token=token;
$$;

revoke all on function public.reservar_relatorio_horario(),public.validar_reserva_horaria(uuid,uuid),
 public.preparar_relatorio_horario(uuid,uuid,jsonb),public.listar_entregas_horarias(uuid,uuid),
 public.iniciar_entrega_horaria(uuid,uuid,uuid),public.finalizar_entrega_horaria(uuid,uuid,uuid,text,text),
 public.registrar_status_horario(uuid,text,text,integer),public.concluir_relatorio_horario(uuid,uuid),
 public.liberar_relatorio_horario(uuid,uuid) from public,anon,authenticated;
grant execute on function public.reservar_relatorio_horario(),public.validar_reserva_horaria(uuid,uuid),
 public.preparar_relatorio_horario(uuid,uuid,jsonb),public.listar_entregas_horarias(uuid,uuid),
 public.iniciar_entrega_horaria(uuid,uuid,uuid),public.finalizar_entrega_horaria(uuid,uuid,uuid,text,text),
 public.registrar_status_horario(uuid,text,text,integer),public.concluir_relatorio_horario(uuid,uuid),
 public.liberar_relatorio_horario(uuid,uuid) to service_role;
