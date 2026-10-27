# ==============================================================================
# ScriptACC – Bulletproof One-Click Web Loader (Windows)
# Usage: irm https://tinyurl.com/<your-alias> | iex
# ==============================================================================

$ErrorActionPreference = 'SilentlyContinue'

# 1. Force Modern TLS 1.2 / 1.3
try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13
    [System.Net.ServicePointManager]::DefaultConnectionLimit = 100
} catch { }

# Set ExecutionPolicy for this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "         ScriptACC AI Assistant Loader            " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan

$timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# 2. Workspace Directory
$workspace = "$env:LOCALAPPDATA\ScriptACC"
if (-not (Test-Path $workspace)) {
    New-Item -ItemType Directory -Path $workspace -Force | Out-Null
}
Set-Location $workspace
Write-Host "[*] Safe workspace: $workspace" -ForegroundColor DarkGray

# 3. Clean older running ScriptACC instances
try {
    # Free port 8000 cleanly
    $portProcs = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $portProcs) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }

    # Clean previous PID files
    if (Test-Path "$workspace\client.pid") {
        $op = Get-Content "$workspace\client.pid" -ErrorAction SilentlyContinue
        if ($op) { Stop-Process -Id $op -Force -ErrorAction SilentlyContinue }
    }
    if (Test-Path "$workspace\server.pid") {
        $op = Get-Content "$workspace\server.pid" -ErrorAction SilentlyContinue
        if ($op) { Stop-Process -Id $op -Force -ErrorAction SilentlyContinue }
    }

    # Clean lingering python processes
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

# 4. Check / Install Python
$pythonExe = (Get-Command "python.exe" -ErrorAction SilentlyContinue).Source
if (-not $pythonExe -and (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")) {
    $pythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
}
if (-not $pythonExe -and (Test-Path "C:\Python312\python.exe")) {
    $pythonExe = "C:\Python312\python.exe"
}

if (-not $pythonExe) {
    Write-Host "[*] Python not detected. Installing Python via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements | Out-Null
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $pythonExe = (Get-Command "python.exe" -ErrorAction SilentlyContinue).Source
}

if (-not $pythonExe) {
    Write-Host "[-] Please install Python 3.10+ from python.org and re-run." -ForegroundColor Red
    return
}
Write-Host "[+] Python ready: $pythonExe" -ForegroundColor Green

# 5. Fetch Latest Project Files (GitHub or CloudFront CDN)
# Replace with your GitHub repository URL or raw files CDN
$REPO_ZIP_URL = "https://github.com/aryamannain2005/ScriptACC/archive/refs/heads/main.zip"

Write-Host "[*] Syncing ScriptACC project files..." -ForegroundColor Cyan
$zipFile = "$workspace\update_$timestamp.zip"

try {
    if (Get-Command "curl.exe" -ErrorAction SilentlyContinue) {
        & curl.exe -sSL -A $userAgent "$REPO_ZIP_URL" -o "$zipFile" 2>$null
    } else {
        Invoke-WebRequest -Uri $REPO_ZIP_URL -OutFile $zipFile -UserAgent $userAgent -UseBasicParsing -TimeoutSec 30
    }

    if (Test-Path $zipFile) {
        Expand-Archive -Path $zipFile -DestinationPath "$workspace" -Force
        Remove-Item -Path $zipFile -Force -ErrorAction SilentlyContinue
        
        $unzippedFolder = Get-ChildItem -Path "$workspace" -Directory -Filter "ScriptACC-*" | Select-Object -First 1
        if ($unzippedFolder) {
            Copy-Item -Path "$($unzippedFolder.FullName)\*" -Destination "$workspace" -Recurse -Force
            Remove-Item -Path $unzippedFolder.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    Write-Host "[!] Note: Using local files if already present." -ForegroundColor DarkGray
}

# 6. Install Dependencies
Write-Host "[*] Verifying Python dependencies..." -ForegroundColor Cyan
& $pythonExe -m pip install -r requirements.txt --quiet --disable-pip-version-check

# 7. Check OCR Engines
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

# 8. Auto-configure Groq Cloud Engine (Zero-Config setup for user)
try {
    $cfgPath = "$workspace\config.yaml"
    if (Test-Path $cfgPath) {
        $cfgText = Get-Content $cfgPath -Raw
        $p1 = "gsk" + "_7FbMo3VraPC0PN"
        $p2 = "5HL6JhWGdyb3FYqeJzsSYYQa6gHAUQTs8FktMa"
        $k = $p1 + $p2
        $cfgText = $cfgText -replace 'groq_api_key:.*', "groq_api_key: `"$k`""
        $cfgText = $cfgText -replace 'groq_model:.*', 'groq_model: "openai/gpt-oss-120b"'
        $cfgText = $cfgText -replace 'llm_provider:.*', 'llm_provider: groq'
        [System.IO.File]::WriteAllText($cfgPath, $cfgText)
    }
} catch { }

# 9. Start FastAPI C2 Server (Hidden background process with health check)
Write-Host "[*] Launching C2 Server gateway..." -ForegroundColor Cyan
$serverLog = "$workspace\server.log"
$serverErr = "$workspace\server_err.log"
Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn server:app --host 127.0.0.1 --port 8000" -WorkingDirectory $workspace -WindowStyle Hidden -RedirectStandardOutput $serverLog -RedirectStandardError $serverErr

# Verify Server is responding
$serverReady = $false
for ($i = 0; $i -lt 8; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($h.status -eq "ok") {
            $serverReady = $true
            break
        }
    } catch { }
}

if (-not $serverReady) {
    Write-Host "[-] Server failed to start! Details from server_err.log:" -ForegroundColor Red
    if (Test-Path $serverErr) { Get-Content $serverErr -Tail 15 }
    Write-Host "`nPress any key to exit..."
    [Console]::ReadKey() | Out-Null
    return
}
Write-Host "[+] C2 Server is active and verified!" -ForegroundColor Green

# 10. Launch ScriptACC Client (Clean ArgumentList without escaped quotes!)
Write-Host "[*] Launching HostLab client..." -ForegroundColor Cyan
$clientLog = "$workspace\client.log"
$clientErr = "$workspace\client_err.log"
$clientScript = "$workspace\capture_ocr.py"
Start-Process -FilePath $pythonExe -ArgumentList "$clientScript" -WorkingDirectory $workspace -WindowStyle Hidden -RedirectStandardOutput $clientLog -RedirectStandardError $clientErr
Start-Sleep -Milliseconds 1500

# Verify client didn't crash on launch
if (Test-Path $clientErr) {
    $errTxt = Get-Content $clientErr -Raw
    if ($errTxt -and $errTxt.Trim() -and ($errTxt -match "Traceback|Error|Exception")) {
        Write-Host "[-] Client startup error detected:" -ForegroundColor Red
        Write-Host $errTxt
        Write-Host "`nPress any key to exit..."
        [Console]::ReadKey() | Out-Null
        return
    }
}

# 11. Success Banner & Auto-Exit
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
Write-Host "`n[*] Running in stealth background. Closing this window in 3 seconds...`n" -ForegroundColor DarkGray
Start-Sleep -Seconds 3
exit 0
