-- Catálogo completo da última coleta real, separado dos estados históricos de alertas.
create table public.catalogo_praticagem (
  id boolean primary key default true check (id),
  navios jsonb not null check (jsonb_typeof(navios) = 'array'),
  atualizado_em timestamptz not null default now()
);
alter table public.catalogo_praticagem enable row level security;
revoke all on public.catalogo_praticagem from anon, authenticated;
grant select on public.catalogo_praticagem to service_role;

create function public.concluir_coleta_catalogo_praticagem(
  p_token uuid, p_estados jsonb, p_eventos jsonb,
  p_quantidades jsonb, p_duracao_ms integer, p_catalogo jsonb)
returns uuid language plpgsql security definer set search_path=public as $$
declare v_coleta uuid;
begin
  if p_catalogo is null or jsonb_typeof(p_catalogo) <> 'array'
     or jsonb_array_length(p_catalogo) = 0 then
    raise exception 'Catálogo vazio ou inválido';
  end if;
  if exists(select 1 from jsonb_array_elements(p_catalogo) n
    where coalesce(n->>'imo','') !~ '^[0-9]{7}$'
       or btrim(coalesce(n->>'nome','')) = '') then
    raise exception 'Identificação inválida no catálogo';
  end if;
  v_coleta := concluir_observacao_praticagem(
    p_token,p_estados,p_eventos,p_quantidades,p_duracao_ms);
  insert into catalogo_praticagem(id,navios,atualizado_em)
    values(true,p_catalogo,now()) on conflict(id) do update
    set navios=excluded.navios, atualizado_em=excluded.atualizado_em;
  return v_coleta;
end $$;
revoke all on function public.concluir_coleta_catalogo_praticagem(uuid,jsonb,jsonb,jsonb,integer,jsonb)
  from public,anon,authenticated;
grant execute on function public.concluir_coleta_catalogo_praticagem(uuid,jsonb,jsonb,jsonb,integer,jsonb)
  to service_role;
