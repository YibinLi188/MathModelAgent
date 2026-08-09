<#
.SYNOPSIS
    One-command Windows launcher for MathModelAgent.
#>
[CmdletBinding()]
param(
    [ValidateSet("docker", "local")]
    [string]$Mode = "docker",
    [string]$ApiType = "openai-responses",
    [string]$Model = "gpt-5.5",
    [string]$BaseUrl = "https://api.openai-next.com/v1",
    [string]$ApiKey,
    [switch]$SeparateKeys,
    [switch]$NoFrontend,
    [switch]$Force,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $repoRoot "backend"
$envFile = Join-Path $backendDir ".env.dev"

function Read-Secret([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

function Require-Command([string]$Name, [string]$InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing command '$Name'. $InstallHint"
    }
}

function Write-EnvFile {
    if ((Test-Path -LiteralPath $envFile) -and -not $Force) {
        $answer = Read-Host "$envFile already exists. Overwrite it? [y/N]"
        if ($answer -notmatch "^(y|yes)$") { throw "Canceled; use -Force to overwrite." }
    }

    $keyMap = @{}
    if ($SeparateKeys) {
        foreach ($role in @("COORDINATOR", "MODELER", "CODER", "WRITER")) {
            $keyMap[$role] = Read-Secret "$role API key"
        }
    }
    else {
        if (-not $ApiKey) { $ApiKey = Read-Secret "One API key for all four agents" }
        if (-not $ApiKey) { throw "API key cannot be empty." }
        foreach ($role in @("COORDINATOR", "MODELER", "CODER", "WRITER")) {
            $keyMap[$role] = $ApiKey
        }
    }

    $redisUrl = if ($Mode -eq "docker") { "redis://redis:6379/0" } else { "redis://localhost:6379/0" }
    $lines = @(
        "ENV=dev",
        "COORDINATOR_API_TYPE=$ApiType", "COORDINATOR_API_KEY=$($keyMap['COORDINATOR'])", "COORDINATOR_MODEL=$Model", "COORDINATOR_BASE_URL=$BaseUrl",
        "MODELER_API_TYPE=$ApiType", "MODELER_API_KEY=$($keyMap['MODELER'])", "MODELER_MODEL=$Model", "MODELER_BASE_URL=$BaseUrl",
        "CODER_API_TYPE=$ApiType", "CODER_API_KEY=$($keyMap['CODER'])", "CODER_MODEL=$Model", "CODER_BASE_URL=$BaseUrl",
        "WRITER_API_TYPE=$ApiType", "WRITER_API_KEY=$($keyMap['WRITER'])", "WRITER_MODEL=$Model", "WRITER_BASE_URL=$BaseUrl",
        "E2B_API_KEY=", "OPENALEX_EMAIL=", "OPENALEX_API_KEY=", "TAVILY_API_KEY=", "SEARCH_ENABLED=false", "RAG_ENABLED=false",
        "HIL_ENABLED=false", "DEBUG=true", "MAX_RETRIES=3", "MAX_CHAT_TURNS=20", "REDIS_URL=$redisUrl",
        "CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173", "SERVER_HOST=http://localhost:8000"
    )
    # `utf8` works in both Windows PowerShell 5.1 and PowerShell 7.
    Set-Content -LiteralPath $envFile -Value $lines -Encoding utf8
    Write-Host "Wrote backend/.env.dev. The key value was not printed." -ForegroundColor Green
}

Set-Location $repoRoot
Write-Host "MathModelAgent launcher" -ForegroundColor Cyan
Write-Host "Provider: $ApiType | Model: $Model | Mode: $Mode"

# Check prerequisites before requesting or writing any API key.
if ($Mode -eq "docker") {
    Require-Command "docker" "Install Docker Desktop and enable Linux containers."
}
else {
    Require-Command "python" "Install Python 3.12 or newer."
    Require-Command "redis-server" "Install Redis for Windows or use -Mode docker."
    if (-not $NoFrontend) {
        Require-Command "pnpm" "Run 'npm install -g pnpm' or use -NoFrontend."
    }
}
Write-EnvFile

if ($Mode -eq "docker") {
    docker compose config | Out-Null
    Write-Host "Starting services. Open http://localhost:5173" -ForegroundColor Green
    if ($NoFrontend) { docker compose up --build redis backend }
    else { docker compose up --build }
    exit $LASTEXITCODE
}

if (-not $SkipInstall) {
    Push-Location $backendDir
    try {
        if (Get-Command uv -ErrorAction SilentlyContinue) { uv sync }
        else { python -m pip install -e . }
    }
    finally { Pop-Location }
}
Start-Process redis-server -WindowStyle Hidden
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", "Set-Location '$backendDir'; `$env:ENV='dev'; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 60 --ws-ping-timeout 120"
if (-not $NoFrontend) {
    $frontendDir = Join-Path $repoRoot "frontend"
    Push-Location $frontendDir
    try {
        if (-not $SkipInstall) { pnpm install }
        Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendDir'; pnpm run dev"
    }
    finally { Pop-Location }
}
Write-Host "Services started. Backend: http://localhost:8000 | Frontend: http://localhost:5173" -ForegroundColor Green
