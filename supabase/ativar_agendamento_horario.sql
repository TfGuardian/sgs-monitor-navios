-- EXECUTAR SOMENTE depois da migracao, deploy do webhook, modelo aprovado
-- e teste manual do worker. Configurar no Vault (Dashboard > Integrations):
-- sgs_github_actions_token: token fine-grained restrito a este repositorio,
-- com Actions: Read and write. Nao colocar o valor no codigo ou no chat.
create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;
create table if not exists public.disparos_relatorio_horario (
  id bigint generated always as identity primary key,
  criado_em timestamptz not null default now(),
  request_id bigint not null
);
alter table public.disparos_relatorio_horario enable row level security;
revoke all on public.disparos_relatorio_horario from anon,authenticated;
grant select on public.disparos_relatorio_horario to service_role;

create or replace function public.disparar_relatorio_horario()
returns void language plpgsql security definer set search_path=public as $$
declare segredo text; pedido bigint;
begin
  perform pg_advisory_xact_lock(25092027);
  if exists(select 1 from relatorios_horarios where
    reserva_ate>now() or (hora=date_trunc('hour',now()) and concluido_em is not null)) then return; end if;
  if exists(select 1 from disparos_relatorio_horario where criado_em>now()-interval '10 minutes') then return; end if;
  select decrypted_secret into segredo from vault.decrypted_secrets where name='sgs_github_actions_token';
  if segredo is null then raise exception 'Token do agendamento ausente no Vault'; end if;
  select net.http_post(
    url:='https://api.github.com/repos/TfGuardian/sgs-monitor-navios/actions/workflows/monitor.yml/dispatches',
    headers:=jsonb_build_object('Authorization','Bearer '||segredo,
      'Accept','application/vnd.github+json','Content-Type','application/json','User-Agent','sgs-monitor-navios'),
    body:='{"ref":"main"}'::jsonb, timeout_milliseconds:=10000) into pedido;
  insert into disparos_relatorio_horario(request_id) values(pedido);
end $$;
revoke all on function public.disparar_relatorio_horario() from public,anon,authenticated;

do $$ begin
  if not exists(select 1 from vault.decrypted_secrets where name='sgs_github_actions_token') then
    raise exception 'Cadastre sgs_github_actions_token no Vault antes de ativar'; end if;
end $$;
-- Verifica a cada cinco minutos; o banco limita a um relatorio por hora UTC.
select cron.schedule('sgs-relatorio-horario', '*/5 * * * *',
  'select public.disparar_relatorio_horario();');

-- Para pausar: select cron.unschedule('sgs-relatorio-horario');
-- Diagnostico do acionamento (HTTP 204 = GitHub aceitou o pedido):
-- select d.criado_em,r.status_code,r.timed_out
-- from public.disparos_relatorio_horario d left join net._http_response r on r.id=d.request_id
-- order by d.criado_em desc limit 12;
