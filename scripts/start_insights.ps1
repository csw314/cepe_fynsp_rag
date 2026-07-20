<#
.SYNOPSIS
Starts every CEPE dashboard and the same-origin AskSage Get Insights service.

.DESCRIPTION
Loads only approved AskSage and certificate settings from a local .env file without evaluating
its contents as PowerShell. The script enables approved PNG interpretation for this server run,
prints boolean readiness information only, and starts the loopback-bound insights server.

.PARAMETER ProjectRoot
Repository root. Defaults to the parent of this script's directory.

.PARAMETER EnvFile
Absolute path or project-root-relative path to the environment file. Defaults to .env.

.PARAMETER Port
Loopback port for the combined static dashboard and insights API server.

.PARAMETER ValidateOnly
Validates startup readiness without starting the server.
#>

[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$ProjectRoot = (Join-Path $PSScriptRoot '..'),

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$EnvFile = '.env',

    [Parameter()]
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,

    [Parameter()]
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ApprovedEnvironmentNames = @(
    'ASKSAGE_INSTANCE',
    'ASKSAGE_APPROVED_HOSTS',
    'ASKSAGE_EMAIL',
    'ASKSAGE_API_KEY',
    'ASKSAGE_ACCESS_TOKEN',
    'ASKSAGE_MODEL',
    'ASKSAGE_CONNECT_TIMEOUT_SECONDS',
    'ASKSAGE_READ_TIMEOUT_SECONDS',
    'ASKSAGE_MAX_RETRIES',
    'ASKSAGE_BACKOFF_FACTOR',
    'ASKSAGE_DATASET_GUIDANCE_ID',
    'ASKSAGE_DATASET_DASHBOARD_PAYLOAD_ID',
    'ASKSAGE_DATASET_ONTOLOGY_ID',
    'ASKSAGE_IMAGE_INPUT_SUPPORTED',
    'REQUESTS_CA_BUNDLE'
)

function Test-ProcessEnvironmentValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    return -not [string]::IsNullOrWhiteSpace($value)
}

function Import-ApprovedDotEnv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string[]]$AllowedNames
    )

    $allowed = @{}
    foreach ($allowedName in $AllowedNames) {
        $allowed[$allowedName] = $true
    }

    $lineNumber = 0
    foreach ($rawLine in [IO.File]::ReadAllLines($Path)) {
        $lineNumber += 1
        $line = $rawLine.Trim().TrimStart([char]0xFEFF)
        if (-not $line -or $line.StartsWith('#')) {
            continue
        }

        if ($line.StartsWith('export ', [StringComparison]::OrdinalIgnoreCase)) {
            $line = $line.Substring(7).TrimStart()
        }

        $separator = $line.IndexOf('=')
        if ($separator -lt 1) {
            throw "Invalid .env assignment at line $lineNumber."
        }

        $name = $line.Substring(0, $separator).Trim()
        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            throw "Invalid .env variable name at line $lineNumber."
        }
        if (-not $allowed.ContainsKey($name)) {
            continue
        }

        $value = $line.Substring($separator + 1).Trim()
        if ($value.Length -gt 0) {
            $firstCharacter = [int][char]$value[0]
            if ($firstCharacter -eq 34 -or $firstCharacter -eq 39) {
                if ($value.Length -lt 2 -or [int][char]$value[$value.Length - 1] -ne $firstCharacter) {
                    throw "Unterminated quoted .env value for '$name' at line $lineNumber."
                }
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        $processValue = if ([string]::IsNullOrWhiteSpace($value)) { $null } else { $value }
        [Environment]::SetEnvironmentVariable($name, $processValue, 'Process')
    }
}

function Assert-StartupArtifacts {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$PythonPath,

        [Parameter(Mandatory = $true)]
        [string]$ServerPath
    )

    $requiredFiles = @(
        $PythonPath,
        $ServerPath,
        (Join-Path $Root 'web\index.html')
    )
    foreach ($requiredFile in $requiredFiles) {
        if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
            throw "Required startup file is unavailable: $requiredFile"
        }
    }

    $dashboardArtifacts = @(
        @{ Payload = 'dashboard_01_pit_production'; Page = '01_overview' },
        @{ Payload = 'dashboard_02_acquisition_schedule'; Page = '02_acquisition' },
        @{ Payload = 'dashboard_03_site_capacity'; Page = '03_site_capacity' },
        @{ Payload = 'dashboard_04_priority_challenge'; Page = '04_priority_challenge' },
        @{ Payload = 'dashboard_05_findings_report_generator'; Page = '05_findings_report_generator' }
    )
    foreach ($dashboard in $dashboardArtifacts) {
        $payloadPath = Join-Path $Root ("data\curated\dashboard_payloads\{0}" -f $dashboard.Payload)
        $pagePath = Join-Path $Root ("web\dashboards\{0}\index.html" -f $dashboard.Page)
        if (-not (Test-Path -LiteralPath $payloadPath -PathType Container)) {
            throw "Generated dashboard payloads are unavailable. Run scripts/run_etl.py first."
        }
        if (-not (Test-Path -LiteralPath $pagePath -PathType Leaf)) {
            throw "Required dashboard page is unavailable: $pagePath"
        }
    }
}

$resolvedProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$resolvedEnvFile = if ([IO.Path]::IsPathRooted($EnvFile)) {
    $EnvFile
} else {
    Join-Path $resolvedProjectRoot $EnvFile
}
if (-not (Test-Path -LiteralPath $resolvedEnvFile -PathType Leaf)) {
    throw "Environment file was not found. Create .env from .env.example before starting insights."
}
$resolvedEnvFile = (Resolve-Path -LiteralPath $resolvedEnvFile).Path

$pythonPath = Join-Path $resolvedProjectRoot '.venv\Scripts\python.exe'
$serverPath = Join-Path $resolvedProjectRoot 'scripts\run_insights_server.py'
Assert-StartupArtifacts -Root $resolvedProjectRoot -PythonPath $pythonPath -ServerPath $serverPath

$originalEnvironment = @{}
foreach ($environmentName in $ApprovedEnvironmentNames) {
    $originalEnvironment[$environmentName] = [Environment]::GetEnvironmentVariable(
        $environmentName,
        'Process'
    )
}

$locationChanged = $false
try {
    Import-ApprovedDotEnv -Path $resolvedEnvFile -AllowedNames $ApprovedEnvironmentNames

    # This explicit operator assertion is scoped to the server process launched below.
    [Environment]::SetEnvironmentVariable(
        'ASKSAGE_IMAGE_INPUT_SUPPORTED',
        'true',
        'Process'
    )

    if (
        -not (Test-ProcessEnvironmentValue -Name 'REQUESTS_CA_BUNDLE') -and
        (Test-ProcessEnvironmentValue -Name 'SSL_CERT_FILE')
    ) {
        $sslCertificateFile = [Environment]::GetEnvironmentVariable('SSL_CERT_FILE', 'Process')
        [Environment]::SetEnvironmentVariable(
            'REQUESTS_CA_BUNDLE',
            $sslCertificateFile,
            'Process'
        )
    }

    if (Test-ProcessEnvironmentValue -Name 'REQUESTS_CA_BUNDLE') {
        $certificateBundle = [Environment]::GetEnvironmentVariable(
            'REQUESTS_CA_BUNDLE',
            'Process'
        )
        if (-not [IO.Path]::IsPathRooted($certificateBundle)) {
            $certificateBundle = Join-Path $resolvedProjectRoot $certificateBundle
            [Environment]::SetEnvironmentVariable(
                'REQUESTS_CA_BUNDLE',
                $certificateBundle,
                'Process'
            )
        }
        if (-not (Test-Path -LiteralPath $certificateBundle -PathType Leaf)) {
            throw 'REQUESTS_CA_BUNDLE is configured, but its certificate bundle is unavailable.'
        }
    }

    $hasAccessToken = Test-ProcessEnvironmentValue -Name 'ASKSAGE_ACCESS_TOKEN'
    $hasEmailAndApiKey = (
        (Test-ProcessEnvironmentValue -Name 'ASKSAGE_EMAIL') -and
        (Test-ProcessEnvironmentValue -Name 'ASKSAGE_API_KEY')
    )
    $authenticationConfigured = $hasAccessToken -or $hasEmailAndApiKey

    $ontologyAvailable = @(
        Get-ChildItem -LiteralPath (Join-Path $resolvedProjectRoot 'data\ontology') `
            -Filter '*_graph.json' -File -ErrorAction SilentlyContinue
    ).Count -gt 0
    $documentContextAvailable = Test-Path -LiteralPath (
        Join-Path $resolvedProjectRoot 'data\curated\guidance_chunks\index.jsonl'
    ) -PathType Leaf

    Write-Output 'Insights startup readiness:'
    Write-Output '  Environment file loaded=True'
    Write-Output ("  AskSage instance configured={0}" -f (
        Test-ProcessEnvironmentValue -Name 'ASKSAGE_INSTANCE'
    ))
    Write-Output ("  AskSage authentication configured={0}" -f $authenticationConfigured)
    Write-Output ("  AskSage model configured={0}" -f (
        Test-ProcessEnvironmentValue -Name 'ASKSAGE_MODEL'
    ))
    Write-Output '  Image input enabled=True'
    Write-Output ("  Certificate bundle override configured={0}" -f (
        Test-ProcessEnvironmentValue -Name 'REQUESTS_CA_BUNDLE'
    ))
    Write-Output '  Dashboard suite available=True'
    Write-Output ("  Ontology context available={0}" -f $ontologyAvailable)
    Write-Output ("  Document context available={0}" -f $documentContextAvailable)

    if (-not $authenticationConfigured) {
        throw (
            'AskSage authentication is not configured. Set ASKSAGE_ACCESS_TOKEN or both ' +
            'ASKSAGE_EMAIL and ASKSAGE_API_KEY in .env.'
        )
    }

    if ($ValidateOnly) {
        Write-Output 'Startup validation completed; the server was not started.'
        return
    }

    Write-Output ("Starting the dashboard and Get Insights server on loopback port {0}." -f $Port)
    Write-Output 'Press Ctrl+C to stop the server.'
    Push-Location -LiteralPath $resolvedProjectRoot
    $locationChanged = $true
    & $pythonPath $serverPath --project-root $resolvedProjectRoot --host '127.0.0.1' --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "The insights server exited with code $LASTEXITCODE."
    }
} finally {
    if ($locationChanged) {
        Pop-Location
    }
    foreach ($environmentName in $ApprovedEnvironmentNames) {
        [Environment]::SetEnvironmentVariable(
            $environmentName,
            $originalEnvironment[$environmentName],
            'Process'
        )
    }
}
