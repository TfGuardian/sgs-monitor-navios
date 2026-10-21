# Compatibilidade com instruções anteriores; implementação em scripts/windows/.
param([string]$Python)
$parametros = @{}
if ($Python) { $parametros.Python = $Python }
& (Join-Path $PSScriptRoot 'scripts/windows/instalar_observador.ps1') @parametros
