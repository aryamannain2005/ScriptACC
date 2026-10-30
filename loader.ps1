# ==============================================================================
# ScriptACC – Bulletproof One-Click Web Loader (Windows)
# Usage:
#   Direct in PowerShell : powershell -ExecutionPolicy Bypass -File .\loader.ps1
#   Web one-liner        : irm https://raw.githubusercontent.com/aryamannain2005/ScriptACC/main/loader.ps1 | iex
# ==============================================================================

# 1. Force Modern TLS 1.2 / 1.3
try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13
    [System.Net.ServicePointManager]::DefaultConnectionLimit = 100
} catch { }

# Try setting ExecutionPolicy for this session
try {
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue
} catch { }

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "         ScriptACC AI Assistant Loader            " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan

$timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# 2. Determine Safe Workspace
# If run locally inside a cloned repository, use current folder; else use %LOCALAPPDATA%\ScriptACC
$isLocal = $false
if ($PSScriptRoot -and (Test-Path "$PSScriptRoot\server.py") -and (Test-Path "$PSScriptRoot\capture_ocr.py")) {
    $workspace = $PSScriptRoot
    $isLocal = $true
} elseif ((Test-Path "$PWD\server.py") -and (Test-Path "$PWD\capture_ocr.py")) {
    $workspace = $PWD.Path
    $isLocal = $true
} else {
    $workspace = "$env:LOCALAPPDATA\ScriptACC"
    if (-not (Test-Path $workspace)) {
        New-Item -ItemType Directory -Path $workspace -Force | Out-Null
    }
}
Set-Location $workspace
Write-Host "[*] Workspace directory: $workspace" -ForegroundColor DarkGray

# 3. Clean older running ScriptACC instances
try {
    # Free port 8000 cleanly
    if (Get-Command "Get-NetTCPConnection" -ErrorAction SilentlyContinue) {
        $portProcs = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $portProcs) {
            if ($p -and [int]$p -gt 4) { Stop-Process -Id [int]$p -Force -ErrorAction SilentlyContinue }
        }
    }

    # Clean previous PID files
    if (Test-Path "$workspace\client.pid") {
        $op = Get-Content "$workspace\client.pid" -ErrorAction SilentlyContinue
        if ($op -and [int]$op -gt 4) { Stop-Process -Id [int]$op -Force -ErrorAction SilentlyContinue }
        Remove-Item "$workspace\client.pid" -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path "$workspace\server.pid") {
        $op = Get-Content "$workspace\server.pid" -ErrorAction SilentlyContinue
        if ($op -and [int]$op -gt 4) { Stop-Process -Id [int]$op -Force -ErrorAction SilentlyContinue }
        Remove-Item "$workspace\server.pid" -Force -ErrorAction SilentlyContinue
    }

    # Clean lingering python processes running ScriptACC
    Get-Process -Name "python*", "pythonw*" -ErrorAction SilentlyContinue | Where-Object {
        $_.Id -ne $PID
    } | ForEach-Object {
        try {
            $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            if ($cmd -match "capture_ocr|uvicorn|server:app") {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
        } catch { }
    }
} catch { }

# 4. Bulletproof Python Detection on Windows
function Find-PythonExecutable {
    $testPy = {
        param($exe)
        if (-not $exe -or -not (Test-Path $exe)) { return $null }
        try {
            $out = & $exe -c "import sys; print(sys.executable)" 2>$null
            if ($out -and (Test-Path $out.Trim())) { return $out.Trim() }
        } catch { }
        return $null
    }

    # A. Check py launcher (py.exe -3)
    try {
        $pyLauncher = (Get-Command "py.exe" -ErrorAction SilentlyContinue).Source
        if ($pyLauncher) {
            $out = & $pyLauncher -3 -c "import sys; print(sys.executable)" 2>$null
            if ($out -and (Test-Path $out.Trim())) { return $out.Trim() }
        }
    } catch { }

    # B. Check python.exe in PATH (skip dummy Microsoft Store 0-byte stub if it fails)
    try {
        $inPath = (Get-Command "python.exe" -ErrorAction SilentlyContinue).Source
        if ($inPath) {
            $verified = & $testPy $inPath
            if ($verified) { return $verified }
        }
    } catch { }

    # C. Search common Windows installation directories (Python 3.10 to 3.14)
    $candidates = @()
    if ($env:LOCALAPPDATA) {
        $candidates += Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python" -Filter "python.exe" -Recurse -Depth 2 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
    }
    $candidates += Get-ChildItem -Path "C:\Program Files\Python*" -Filter "python.exe" -Depth 1 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
    $candidates += Get-ChildItem -Path "C:\Python*" -Filter "python.exe" -Depth 1 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName

    foreach ($cand in $candidates) {
        $verified = & $testPy $cand
        if ($verified) { return $verified }
    }

    return $null
}

$pythonExe = Find-PythonExecutable

if (-not $pythonExe) {
    Write-Host "[*] Python not detected. Attempting install via winget..." -ForegroundColor Yellow
    try {
        winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements | Out-Null
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        $pythonExe = Find-PythonExecutable
    } catch { }
}

if (-not $pythonExe) {
    Write-Host "[-] Python 3.10+ is required but was not found." -ForegroundColor Red
    Write-Host "    Please download and install Python from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "    IMPORTANT: Check 'Add python.exe to PATH' during installation!" -ForegroundColor Yellow
    Write-Host "`nPress Enter to exit..."
    try { [Console]::ReadLine() } catch { }
    return
}
Write-Host "[+] Python verified: $pythonExe" -ForegroundColor Green

# 5. Fetch Latest Project Files (Only needed if NOT running in local cloned repo)
if (-not $isLocal) {
    $REPO_ZIP_URL = "https://github.com/aryamannain2005/ScriptACC/archive/refs/heads/main.zip"
    Write-Host "[*] Syncing ScriptACC project files from GitHub..." -ForegroundColor Cyan
    $zipFile = "$workspace\update_$timestamp.zip"
    $downloadSuccess = $false

    try {
        Invoke-WebRequest -Uri $REPO_ZIP_URL -OutFile $zipFile -UserAgent $userAgent -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop
        if ((Test-Path $zipFile) -and ((Get-Item $zipFile).Length -gt 2000)) {
            $downloadSuccess = $true
        }
    } catch {
        if (Get-Command "curl.exe" -ErrorAction SilentlyContinue) {
            & curl.exe -sSL -A $userAgent "$REPO_ZIP_URL" -o "$zipFile"
            if ((Test-Path $zipFile) -and ((Get-Item $zipFile).Length -gt 2000)) {
                $downloadSuccess = $true
            }
        }
    }

    if ($downloadSuccess) {
        try {
            $tempExtract = "$workspace\ext_$timestamp"
            Expand-Archive -Path $zipFile -DestinationPath $tempExtract -Force
            Remove-Item -Path $zipFile -Force -ErrorAction SilentlyContinue

            $extractedFolder = Get-ChildItem -Path $tempExtract -Directory -Filter "ScriptACC-*" | Select-Object -First 1
            if ($extractedFolder) {
                Get-ChildItem -Path $extractedFolder.FullName | ForEach-Object {
                    Move-Item -Path $_.FullName -Destination $workspace -Force
                }
            }
            Remove-Item -Path $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Host "[!] Note: Using existing local files." -ForegroundColor DarkGray
        }
    }
}

# 6. Virtual Environment & Dependencies
$venvDir = "$workspace\.venv"
$venvPython = "$venvDir\Scripts\python.exe"

# Create .venv if not already present (prevents permission denied and path pollution)
if (-not (Test-Path $venvPython)) {
    Write-Host "[*] Setting up isolated Python virtual environment (.venv)..." -ForegroundColor Cyan
    & $pythonExe -m venv $venvDir 2>$null
}

$runPython = $pythonExe
if (Test-Path $venvPython) {
    $runPython = $venvPython
}

Write-Host "[*] Checking Python dependencies..." -ForegroundColor Cyan
$depsOk = $false
try {
    $check = & $runPython -c "import fastapi, uvicorn, pynput, PySide6, pyautogui, yaml, httpx; print('OK')" 2>$null
    if ($check -match "OK") { $depsOk = $true }
} catch { }

if (-not $depsOk) {
    Write-Host "[*] Installing dependencies (first run may take a couple minutes for PySide6)..." -ForegroundColor Yellow
    if (Test-Path "$workspace\requirements.txt") {
        & $runPython -m pip install -r "$workspace\requirements.txt" --disable-pip-version-check
    } else {
        & $runPython -m pip install httpx pytesseract pyautogui pynput PySide6 fastapi "uvicorn[standard]" pyyaml winocr --disable-pip-version-check
    }
} else {
    Write-Host "[+] Dependencies ready!" -ForegroundColor Green
}

# 7. Check OCR Engines (Tesseract Fallback)
$tessPaths = @(
    "C:\Program Files\Tesseract-OCR",
    "C:\Program Files (x86)\Tesseract-OCR",
    "$env:LOCALAPPDATA\Programs\Tesseract-OCR"
)
foreach ($tp in $tessPaths) {
    if (Test-Path "$tp\tesseract.exe") {
        $env:Path += ";$tp"
        break
    }
}

# 8. Auto-configure Groq Cloud Engine in config.yaml
$cfgPath = "$workspace\config.yaml"
if (-not (Test-Path $cfgPath)) {
    $defaultCfg = @"
token: YOUR_REGISTRATION_TOKEN
llm_provider: groq
groq_api_key: ""
groq_model: "openai/gpt-oss-120b"
ollama_endpoint: http://127.0.0.1:11434/api/generate
ollama_model: llama3.2:3b
ocr_language: eng
server_url: http://127.0.0.1:8000/process
"@
    [System.IO.File]::WriteAllText($cfgPath, $defaultCfg)
} else {
    try {
        $cfgText = Get-Content $cfgPath -Raw
        $cfgText = $cfgText -replace 'groq_model:.*', 'groq_model: "openai/gpt-oss-120b"'
        $cfgText = $cfgText -replace 'llm_provider:.*', 'llm_provider: groq'
        [System.IO.File]::WriteAllText($cfgPath, $cfgText)
    } catch { }
}

# 9. Start FastAPI C2 Server (Hidden background process with health check)
Write-Host "[*] Launching C2 Server gateway..." -ForegroundColor Cyan
$serverLog = "$workspace\server.log"
$serverErr = "$workspace\server_err.log"
Remove-Item -Path $serverLog, $serverErr -Force -ErrorAction SilentlyContinue

Start-Process -FilePath $runPython -ArgumentList "-m uvicorn server:app --host 127.0.0.1 --port 8000" -WorkingDirectory $workspace -WindowStyle Hidden -RedirectStandardOutput $serverLog -RedirectStandardError $serverErr

# Verify Server is responding (wait up to 15 seconds)
$serverReady = $false
Write-Host -NoNewline "[*] Waiting for server gateway"
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    Write-Host -NoNewline "."
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($h.status -eq "ok") {
            $serverReady = $true
            break
        }
    } catch { }
}
Write-Host ""

if (-not $serverReady) {
    Write-Host "[-] Server failed to start! Details from server_err.log:" -ForegroundColor Red
    if (Test-Path $serverErr) { Get-Content $serverErr -Tail 20 }
    Write-Host "`nPress Enter to exit..." -ForegroundColor Yellow
    try { [Console]::ReadLine() } catch { }
    return
}
Write-Host "[+] C2 Server is active and verified!" -ForegroundColor Green

# 10. Launch ScriptACC Client
Write-Host "[*] Launching HostLab client..." -ForegroundColor Cyan
$clientLog = "$workspace\client.log"
$clientErr = "$workspace\client_err.log"
Remove-Item -Path $clientLog, $clientErr -Force -ErrorAction SilentlyContinue

Start-Process -FilePath $runPython -ArgumentList "capture_ocr.py" -WorkingDirectory $workspace -WindowStyle Hidden -RedirectStandardOutput $clientLog -RedirectStandardError $clientErr
Start-Sleep -Milliseconds 2000

# Verify client didn't crash on launch
if (Test-Path $clientErr) {
    $errTxt = Get-Content $clientErr -Raw -ErrorAction SilentlyContinue
    if ($errTxt -and ($errTxt -match "Traceback \(most recent call last\):|ModuleNotFoundError|ImportError")) {
        Write-Host "[-] Client startup error detected:" -ForegroundColor Red
        Write-Host $errTxt
        Write-Host "`nPress Enter to exit..." -ForegroundColor Yellow
        try { [Console]::ReadLine() } catch { }
        return
    }
}
Write-Host "[+] HostLab Client is active and listening for hotkeys!" -ForegroundColor Green

# 11. Success Banner
Write-Host "`n==================================================" -ForegroundColor Green
Write-Host " [SUCCESS] HostLab / ScriptACC is ACTIVE!         " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host " Hotkeys Active in Background:" -ForegroundColor White
Write-Host "   - Alt + M         : Multi-MCQ Solver" -ForegroundColor Yellow
Write-Host "   - Alt + 8         : Coding Solver (DSA)" -ForegroundColor Yellow
Write-Host "   - Alt + 9         : FullStack / SQL / Debug" -ForegroundColor Yellow
Write-Host "   - Alt + 0         : Game & Puzzle Solver" -ForegroundColor Yellow
Write-Host "   - Alt + B         : Add SS to Buffer" -ForegroundColor Yellow
Write-Host "   - Alt + F         : Auto-Type Solution" -ForegroundColor Yellow
Write-Host "   - Alt + G         : Ghost-Type (Stealth)" -ForegroundColor Yellow
Write-Host "   - Alt + R         : Pause / Resume Typing" -ForegroundColor Yellow
Write-Host "   - Alt + E         : Stop Typing" -ForegroundColor Yellow
Write-Host "   - Alt + D         : Show / Hide Overlay" -ForegroundColor Yellow
Write-Host "   - Alt + N         : Dim 9% (Stealth)" -ForegroundColor Yellow
Write-Host "   - Alt + I         : Show Hotkey Guide" -ForegroundColor Yellow
Write-Host "   - Alt + Shift + X : Emergency Exit" -ForegroundColor Red
Write-Host "==================================================" -ForegroundColor Green
Write-Host "`n[*] Running in background." -ForegroundColor DarkGray

if (-not $isLocal) {
    Write-Host "[*] Window closing in 3 seconds...`n" -ForegroundColor DarkGray
    Start-Sleep -Seconds 3
    exit 0
}
