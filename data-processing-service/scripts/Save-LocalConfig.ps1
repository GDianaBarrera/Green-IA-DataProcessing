[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path -Parent $PSScriptRoot
$targetPath = Join-Path $serviceRoot '.env'
if (Test-Path -LiteralPath $targetPath) {
    throw 'Ya existe .env. No se sobrescribio; revisalo localmente.'
}
$names = @('SUPABASE_URL', 'SUPABASE_API_KEY', 'SUPABASE_READ_TOKEN')
foreach ($name in $names) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ([string]::IsNullOrWhiteSpace($value) -or $value -match '[\s<>]' -or
        $value -match '^(TU_ACCESS_TOKEN|YOUR_ACCESS_TOKEN|CHANGEME)$') {
        throw "Falta un valor real para $name en ESTA sesion de PowerShell. No se guardaron credenciales."
    }
}
if ($env:SUPABASE_READ_TOKEN -match '^sb_(publishable|secret)_') {
    throw 'SUPABASE_READ_TOKEN debe ser un JWT de lectura, no una API key.'
}
$uri = $null
if (-not [Uri]::TryCreate($env:SUPABASE_URL, [UriKind]::Absolute, [ref]$uri) -or
    $uri.Scheme -ne 'https' -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
    throw 'SUPABASE_URL debe ser una URL HTTPS sin credenciales ni query.'
}
$pageSize = 500
if ($env:HISTORICAL_MAX_PAGE_SIZE) {
    if (-not [int]::TryParse($env:HISTORICAL_MAX_PAGE_SIZE, [ref]$pageSize) -or $pageSize -lt 1 -or $pageSize -gt 500) {
        throw 'HISTORICAL_MAX_PAGE_SIZE debe estar entre 1 y 500.'
    }
}
function Quote-Env([string]$value) {
    # Compose single-quoted values prevent interpolation of dollar signs.
    if ($value.Contains("'") -or $value.Contains("`r") -or $value.Contains("`n")) {
        throw 'Un valor contiene caracteres no admitidos; no se creo .env.'
    }
    return "'" + $value + "'"
}
$lines = @('# Solo local. No subir este archivo a Git.', 'SUPABASE_ENABLED=true')
foreach ($name in $names) {
    $lines += $name + '=' + (Quote-Env ([Environment]::GetEnvironmentVariable($name, 'Process')))
}
$lines += "HISTORICAL_MAX_PAGE_SIZE=$pageSize"
# CreateNew prevents an existing file from being overwritten, even in a race.
$stream = [IO.File]::Open($targetPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
try {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($lines -join "`n") + "`n")
    $stream.Write($bytes, 0, $bytes.Length)
} finally {
    $stream.Dispose()
}
Write-Host 'Configuracion guardada en .env local. No se mostraron claves ni se validaron permisos de la identidad.'
