# Validação

Na raiz, com o pacote e as dependências instalados:

```powershell
python -m unittest discover -s tests -v
$testes = @(Get-ChildItem tests/webhook -Filter '*.mjs' | ForEach-Object { $_.FullName })
node --test --test-concurrency=1 $testes
```

- `unit/`: regras, formatação, filas e falhas com serviços simulados.
- `integration/`: controle da árvore de processos, entradas e localização dos recursos.
- `webhook/`: regras TypeScript e migrações SQL em banco local PGlite.

Os testes JavaScript usam PGlite instalado em `tmp/webhook-validation/`.
Com Node/npm disponíveis, prepare-o com
`npm install --prefix tmp/webhook-validation @electric-sql/pglite`.
Não usam o banco de produção nem enviam mensagens reais.
