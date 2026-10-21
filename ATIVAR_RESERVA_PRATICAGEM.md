# Cadastro de reserva pela Praticagem

Quando a consulta ao Porto de Santos falhar, `Adicionar: NOME` (ou IMO)
usa o catálogo completo da última coleta real da Praticagem, com até 5 minutos.
O computador e o observador precisam estar ligados e coletando com sucesso.
Não há nova consulta ao portal por mensagem: todas as quatro tabelas já são lidas
pelo observador, inclusive navios ainda não monitorados.

O cadastro salva nome e IMO na mesma lista usada pelo WhatsApp e pelo observador.
Não inventa terminal, ETB ou situação operacional. Esses dados continuam sendo
responsabilidade das fontes do porto. O próximo ciclo passa a acompanhar o IMO.

`Remover: NOME` e `Confirmar` continuam usando a lista salva e independem de ambos
os sites. A remoção passa a valer para os próximos ciclos do observador.

## Ativação (nesta ordem)

1. Executar `supabase/migrations/20261013120000_catalogo_praticagem.sql` no SQL Editor.
2. Publicar `supabase/functions/whatsapp-webhook/index.ts` na função `whatsapp-webhook`.
3. Reiniciar o observador com os arquivos locais atualizados (comando `Observador`).
4. Após uma coleta bem-sucedida, verificar a linha de `catalogo_praticagem` e seu horário.
5. Durante a indisponibilidade do porto, testar `Adicionar: NOME` com um navio
   presente na Praticagem; conferir `Lista`. Para desfazer, usar `Remover: NOME`
   e `Confirmar`.

Snapshots de simulação não atualizam o catálogo de cadastro. Se a coleta falhar,
o catálogo anterior só pode ser usado enquanto estiver dentro dos 5 minutos.

## Monitoramento pelo nome (15/10/2026)

O observador filtra as linhas pelos nomes ativos antes de interpretar manobras.
Ignora diferenças de caixa, acentos e espaços. Nome semelhante não é associado
automaticamente. IMO vazio ou zero não impede acompanhar um nome único.

Os estados existentes mantêm suas chaves para preservar histórico. Novos estados
usam uma chave interna derivada do nome (prefixo `nome:`), armazenada na coluna
legada `imo`; essa chave não é um número IMO e não entra no catálogo público.
A primeira leitura de um novo estado estabelece a base, sem anunciar fatos antigos.
O catálogo de cadastro continua abrangendo nomes fora da lista, com IMO opcional.
A migração `20261015170000_catalogo_por_nome.sql` deve preceder o reinício do worker.
