-- Aplicar depois da migracao da fila de atualizacoes.
alter table public.atualizacoes_chat add column if not exists indisponiveis jsonb not null default '[]';
alter table public.atualizacoes_chat_destinatarios
  add column if not exists remocao_tratada boolean not null default false,
  add column if not exists proxima_pergunta integer not null default 0;

create or replace function public.oferecer_remocao_indisponiveis(lote uuid, numero text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare destinatario atualizacoes_chat_destinatarios%rowtype;
        pendente confirmacoes_chat%rowtype; candidatos jsonb; proposta jsonb;
begin
  perform pg_advisory_xact_lock(hashtextextended(numero, 0));
  select * into destinatario from atualizacoes_chat_destinatarios
    where atualizacao_id=lote and telefone=numero for update;
  if not found then return null; end if;
  if not exists(select 1 from administradores_chat where telefone=numero and ativo) then return null; end if;
  select * into pendente from confirmacoes_chat where telefone=numero for update;
  if destinatario.remocao_tratada then
    if pendente.payload->>'lote'=lote::text and pendente.expira_em>now() then
      return pendente.payload;
    end if;
    return null; -- Nunca recriar uma confirmacao ja respondida, cancelada ou expirada.
  end if;
  update atualizacoes_chat_destinatarios set remocao_tratada=true where atualizacao_id=lote and telefone=numero;
  if pendente.expira_em>now() then return null; end if; -- Preserva outra operacao pendente.
  select indisponiveis into candidatos from atualizacoes_chat
    where id=lote and resultado='sucesso' and estado='pronto';
  select jsonb_build_object('ids',jsonb_agg(l.id order by l.id),
    'nomes',jsonb_agg(l.nome_confirmado order by l.id), 'origem','indisponiveis','lote',lote::text)
    into proposta from lista_monitoramento l
    where l.ativo and l.id in (select (x->>'id')::bigint from jsonb_array_elements(coalesce(candidatos,'[]')) x)
    and not exists(select 1 from navios_monitorados n where n.lista_monitoramento_id=l.id and n.situacao<>'indisponivel');
  if proposta->'ids' is null or proposta->'ids'='null'::jsonb then return null; end if;
  insert into confirmacoes_chat(telefone,acao,payload,criado_em,expira_em)
    values(numero,'remover_navios',proposta,now(),now()+interval '10 minutes')
    on conflict(telefone) do update set acao=excluded.acao,payload=excluded.payload,
      criado_em=excluded.criado_em,expira_em=excluded.expira_em;
  return proposta;
end $$;

-- Consumir confirmacao e excluir na mesma transacao, com revalidacao.
create or replace function public.confirmar_remocao_chat(numero text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare pendente confirmacoes_chat%rowtype; removidos jsonb;
begin
  perform pg_advisory_xact_lock(hashtextextended(numero, 0));
  if not exists(select 1 from administradores_chat where telefone=numero and ativo) then
    raise exception 'Sem permissao administrativa';
  end if;
  select * into pendente from confirmacoes_chat where telefone=numero for update;
  if not found then return '[]'::jsonb; end if;
  if pendente.expira_em<=now() then
    delete from confirmacoes_chat where telefone=numero;
    return '[]'::jsonb;
  end if;
  -- Bloqueia os dados existentes contra uma atualizacao concorrente durante a exclusao.
  perform 1 from lista_monitoramento l where l.id in
    (select value::bigint from jsonb_array_elements_text(pendente.payload->'ids')) for update;
  perform 1 from navios_monitorados n where n.lista_monitoramento_id in
    (select value::bigint from jsonb_array_elements_text(pendente.payload->'ids')) for update;
  with apagados as (
    delete from lista_monitoramento l where l.id in
      (select value::bigint from jsonb_array_elements_text(pendente.payload->'ids'))
      and (coalesce(pendente.payload->>'origem','manual')<>'indisponiveis' or
        not exists(select 1 from navios_monitorados n where n.lista_monitoramento_id=l.id and n.situacao<>'indisponivel'))
      returning l.nome_confirmado
  ) select coalesce(jsonb_agg(nome_confirmado),'[]'::jsonb) into removidos from apagados;
  delete from confirmacoes_chat where telefone=numero;
  return removidos;
end $$;
revoke all on function public.oferecer_remocao_indisponiveis(uuid,text),public.confirmar_remocao_chat(text) from public,anon,authenticated;
grant execute on function public.oferecer_remocao_indisponiveis(uuid,text),public.confirmar_remocao_chat(text) to service_role;
