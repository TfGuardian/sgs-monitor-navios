param(
  [string]$Python = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) {
  throw "Python não encontrado: $Python"
}
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$usuario = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$configuracao = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
  -RestartCount 20 -RestartInterval (New-TimeSpan -Minutes 1) `
  -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Priority 4

function Garantir-Tarefa([string]$nome, [string]$arquivo) {
  $acao = New-ScheduledTaskAction -Execute $Python `
    -Argument ('"' + (Join-Path $raiz $arquivo) + '"') -WorkingDirectory $raiz
  $existente = Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue
  if ($existente) {
    $ajustes = $existente.Settings
    $ajustes.Priority = 4
    Set-ScheduledTask -TaskName $nome -Action $acao -Settings $ajustes | Out-Null
    Write-Output "Tarefa existente: $nome"
    return
  }
  Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho `
    -Principal $principal -Settings $configuracao | Out-Null
  Write-Output "Tarefa criada: $nome"
}

Garantir-Tarefa 'SGS Praticagem Observador' 'scripts\windows\observar.py'
Garantir-Tarefa 'SGS Praticagem Controle' 'scripts\windows\controlar.py'

$controle = Get-ScheduledTask -TaskName 'SGS Praticagem Controle'
if ($controle.State -ne 'Running') {
  Start-ScheduledTask -TaskName 'SGS Praticagem Controle'
  Write-Output 'Controlador iniciado.'
}
Write-Output 'O observador será iniciado/reiniciado quando chegar o comando pelo WhatsApp.'
