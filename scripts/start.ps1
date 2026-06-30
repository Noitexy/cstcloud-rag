[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot 'backend'
$FrontendDir = Join-Path $ProjectRoot 'frontend'
$BackendPython = Join-Path $BackendDir '.venv\Scripts\python.exe'
$EnvFile = Join-Path $BackendDir '.env'
$EnvExample = Join-Path $BackendDir '.env.example'

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[提示] $Message" -ForegroundColor Yellow
}

function Test-Url([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Wait-Url([string]$Url, [int]$Seconds = 40) {
    for ($index = 0; $index -lt ($Seconds * 2); $index++) {
        if (Test-Url $Url) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Get-PythonLauncher {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    $candidates = @()
    if ($py) {
        $candidates += @{ File = $py.Source; Args = @('-3.12'); Label = 'Python 3.12' }
        $candidates += @{ File = $py.Source; Args = @('-3.11'); Label = 'Python 3.11' }
    }
    $codexPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $codexPython) {
        $candidates += @{ File = $codexPython; Args = @(); Label = 'Codex Python runtime' }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { $candidates += @{ File = $python.Source; Args = @(); Label = 'PATH Python' } }
    foreach ($candidate in $candidates) {
        $arguments = @($candidate.Args) + @('-c', 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)')
        $previousPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $candidate.File $arguments 2>$null
            $candidateExitCode = $LASTEXITCODE
        } catch {
            $candidateExitCode = 1
        } finally {
            $ErrorActionPreference = $previousPreference
        }
        if ($candidateExitCode -eq 0) {
            Write-Ok "使用 $($candidate.Label) 创建后端环境"
            return $candidate
        }
    }
    throw '未找到兼容的 Python。请安装 Python 3.11 或 3.12；当前项目暂不使用 Python 3.14。'
}

function Test-BackendEnvironment {
    if (-not (Test-Path -LiteralPath $BackendPython)) { return $false }
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $BackendPython -c 'import sys; assert (3, 10) <= sys.version_info[:2] < (3, 14); import fastapi, pydantic_core, chromadb; assert int(chromadb.__version__.split(''.'', 1)[0]) < 1' 2>$null
        $environmentExitCode = $LASTEXITCODE
    } catch {
        $environmentExitCode = 1
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    return $environmentExitCode -eq 0
}

Write-Host 'CSTCloud-RAG 一键启动器' -ForegroundColor White
Write-Host "项目目录：$ProjectRoot" -ForegroundColor DarkGray

if ($CheckOnly) {
    Write-Step '检查当前环境'
    if (Test-BackendEnvironment) { Write-Ok '后端 Python 虚拟环境健康且版本兼容' } else { Write-Warn '后端虚拟环境缺失或已损坏，启动时会自动使用 Python 3.11/3.12 重建' }
    if (Test-Path -LiteralPath (Join-Path $FrontendDir 'node_modules')) { Write-Ok '前端依赖已安装' } else { Write-Warn '前端依赖不存在，首次启动时会自动 npm install' }
    if (Get-Command npm.cmd -ErrorAction SilentlyContinue) { Write-Ok 'Node.js / npm 可用' } else { Write-Warn '未找到 npm，请安装 Node.js 20' }
    if (Test-Path -LiteralPath $EnvFile) { Write-Ok 'backend/.env 已存在' } else { Write-Warn 'backend/.env 不存在，首次启动时会自动创建' }
    if (Test-Url 'http://127.0.0.1:8000/api/health') { Write-Ok '后端当前正在运行' } else { Write-Warn '后端当前未运行' }
    if (Test-Url 'http://127.0.0.1:5173') { Write-Ok '前端当前正在运行' } else { Write-Warn '前端当前未运行' }
    exit 0
}

Write-Step '检查后端环境'
if (-not (Test-BackendEnvironment)) {
    $venvDir = Join-Path $BackendDir '.venv'
    if (Test-Path -LiteralPath $venvDir) {
        Write-Warn '检测到损坏或不兼容的虚拟环境，正在安全重建。'
        $backendFull = [System.IO.Path]::GetFullPath($BackendDir)
        $venvFull = [System.IO.Path]::GetFullPath($venvDir)
        if (-not $venvFull.StartsWith($backendFull, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw '虚拟环境路径不在 backend 目录内，已停止自动清理。'
        }
        Remove-Item -LiteralPath $venvFull -Recurse -Force
    } else {
        Write-Warn '首次运行：正在创建 Python 虚拟环境并安装依赖，可能需要几分钟。'
    }
    $launcher = Get-PythonLauncher
    $venvArguments = @($launcher.Args) + @('-m', 'venv', $venvDir)
    & $launcher.File $venvArguments
    if ($LASTEXITCODE -ne 0) { throw 'Python 虚拟环境创建失败。建议安装 Python 3.11 后重试。' }
    & $BackendPython -m pip install --upgrade 'pip>=26.1.2'
    if ($LASTEXITCODE -ne 0) { throw 'pip 安全升级失败，请检查网络后重试。' }
    & $BackendPython -m pip install -r (Join-Path $BackendDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw '后端依赖安装失败，请检查网络后重试。' }
}
Write-Ok '后端环境就绪'

Write-Step '检查科技云配置'
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
    Write-Warn '已创建 backend/.env。记事本即将打开，请在 CSTCLOUD_API_KEY= 后填写你新生成的科技云 Token。'
    Write-Warn '填写后保存并关闭记事本，启动器会继续执行。没有 Token 也能打开界面，但不能建立向量索引或调用模型。'
    Start-Process -FilePath 'notepad.exe' -ArgumentList @($EnvFile) -Wait
}
$envContent = Get-Content -LiteralPath $EnvFile -Raw -ErrorAction SilentlyContinue
if ($envContent -match '(?m)^\s*CSTCLOUD_API_KEY\s*=\s*(.+?)\s*$' -and $Matches[1].Trim()) {
    Write-Ok '检测到 CSTCLOUD_API_KEY（不会显示具体内容）'
} else {
    Write-Warn '未填写 CSTCLOUD_API_KEY：界面可以打开，但聊天、Embedding 和 Rerank 会提示配置 Token。'
}

Write-Step '检查前端环境'
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) { throw '未找到 npm。请安装 Node.js 20 LTS 后重新双击启动。' }
if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir 'node_modules'))) {
    Write-Warn '首次运行：正在安装前端依赖，可能需要几分钟。'
    Push-Location $FrontendDir
    try {
        & $npm.Source install
        if ($LASTEXITCODE -ne 0) { throw '前端依赖安装失败，请检查网络后重试。' }
    } finally {
        Pop-Location
    }
}
Write-Ok '前端环境就绪'

Write-Step '启动后端与前端'
if (-not (Test-Url 'http://127.0.0.1:8000/api/health')) {
    $backendCommand = "`$Host.UI.RawUI.WindowTitle='CSTCloud-RAG 后端（关闭此窗口即停止）'; Set-Location -LiteralPath '$($BackendDir.Replace("'", "''"))'; & '$($BackendPython.Replace("'", "''"))' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
    Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $backendCommand) -WorkingDirectory $BackendDir | Out-Null
} else {
    Write-Ok '后端已经在运行，不重复启动'
}

if (-not (Test-Url 'http://127.0.0.1:5173')) {
    $frontendCommand = "`$Host.UI.RawUI.WindowTitle='CSTCloud-RAG 前端（关闭此窗口即停止）'; Set-Location -LiteralPath '$($FrontendDir.Replace("'", "''"))'; & '$($npm.Source.Replace("'", "''"))' run dev -- --host 127.0.0.1 --port 5173 --strictPort"
    Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $frontendCommand) -WorkingDirectory $FrontendDir | Out-Null
} else {
    Write-Ok '前端已经在运行，不重复启动'
}

$backendReady = Wait-Url 'http://127.0.0.1:8000/api/health' 40
$frontendReady = Wait-Url 'http://127.0.0.1:5173' 40

if ($backendReady) { Write-Ok '后端：http://127.0.0.1:8000' } else { Write-Warn '后端没有按时就绪，请查看“CSTCloud-RAG 后端”窗口中的错误。' }
if ($frontendReady) { Write-Ok '前端：http://127.0.0.1:5173' } else { Write-Warn '前端没有按时就绪，请查看“CSTCloud-RAG 前端”窗口中的错误。' }

if ($frontendReady -and -not $NoBrowser) {
    Start-Process 'http://127.0.0.1:5173'
}

Write-Host "`n启动完成。以后打开项目只需双击“启动项目.bat”。" -ForegroundColor Green
Write-Host '停止项目：在“后端”和“前端”两个窗口中按 Ctrl+C，或直接关闭这两个窗口。' -ForegroundColor Yellow
