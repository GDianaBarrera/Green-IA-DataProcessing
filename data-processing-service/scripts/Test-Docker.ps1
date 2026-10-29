[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$fixturePath = Join-Path (Split-Path -Parent $projectRoot) 'datasets/raw/synthetic_greenai/BD_GreenAi.xlsx'
$runId = [Guid]::NewGuid().ToString('N').Substring(0, 12)
$imageName = "green-ai-data-processing:verify-$runId"
$networkName = "greenai-test-$runId"
$monitoringName = "greenai-monitoring-test-$runId"
$processingName = "greenai-processing-test-$runId"
$networkCreated = $false
$monitoringCreated = $false
$processingCreated = $false

function Invoke-Docker {
    param([string[]]$DockerArguments)
    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker fallo (exit $LASTEXITCODE): $($DockerArguments[0])"
    }
}

Push-Location $projectRoot
try {
    Invoke-Docker -DockerArguments @('info', '--format', '{{.ServerVersion}}')
    if (-not (Test-Path -LiteralPath $fixturePath -PathType Leaf)) {
        throw "Falta el fixture Excel sintetico para la suite completa: $fixturePath"
    }
    Invoke-Docker -DockerArguments @('compose', '-f', 'compose.yaml', 'config', '--quiet')
    Invoke-Docker -DockerArguments @('compose', '-f', 'compose.local.yaml', 'config', '--quiet')
    Invoke-Docker -DockerArguments @('build', '--tag', $imageName, '.')
    Invoke-Docker -DockerArguments @('run', '--rm', '--mount',
        "type=bind,source=$fixturePath,target=/datasets/raw/synthetic_greenai/BD_GreenAi.xlsx,readonly",
        $imageName, 'python', '-m', 'pytest', '-q', '-p', 'no:cacheprovider')
    Invoke-Docker -DockerArguments @('network', 'create', $networkName)
    $networkCreated = $true
    Invoke-Docker -DockerArguments @('create', '--name', $monitoringName, '--network', $networkName,
        '--network-alias', 'monitoring', '--no-healthcheck', $imageName,
        'python', 'tests/docker_monitoring_fixture.py')
    $monitoringCreated = $true
    Invoke-Docker -DockerArguments @('start', $monitoringName)
    Invoke-Docker -DockerArguments @('create', '--name', $processingName, '--network', $networkName,
        '--network-alias', 'data-processing', '-e', 'MONITORING_BASE_URL=http://monitoring:8080',
        '-e', 'SUPABASE_ENABLED=false', $imageName)
    $processingCreated = $true
    Invoke-Docker -DockerArguments @('start', $processingName)
    Invoke-Docker -DockerArguments @('run', '--rm', '--network', $networkName, $imageName,
        'python', 'scripts/docker_smoke.py', 'http://data-processing:8000')
    Write-Host "OK: imagen construida, suite y HTTP entre contenedores verificados. Imagen: $imageName"
} finally {
    # Only resources created by this run; existing services/networks are untouched.
    if ($processingCreated) { & docker rm --force $processingName | Out-Null }
    if ($monitoringCreated) { & docker rm --force $monitoringName | Out-Null }
    if ($networkCreated) { & docker network rm $networkName | Out-Null }
    Pop-Location
}
