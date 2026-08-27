alter table public.navios_monitorados
add column if not exists etb text;

comment on column public.navios_monitorados.etb is
'Estimated Time of Berthing (data e hora prevista/real de atracacao)';
