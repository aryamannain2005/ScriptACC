# ==============================================================================
# HostLab Bulletproof One-Click Web Loader
# CloudFront CDN Optimized | Zero-MOTW | Multi-Engine Resilient Downloader
# ==============================================================================

$ErrorActionPreference = 'SilentlyContinue'

# 1. Force Modern TLS 1.2 / 1.3
try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13
    [System.Net.ServicePointManager]::DefaultConnectionLimit = 100
} catch { }

# Set ExecutionPolicy for current session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "         HostLab Standalone Service               " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan

# 2. Dynamic Real-Time Cache-Busting & Auto-Origin URL Resolution
$timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"

# CloudFront CDN URLs
$PRIMARY_URL   = "https://d3tzgjurlayi2g.cloudfront.net/download/HostLab.exe?v=$timestamp"
$BACKUP_URL    = "https://my-project-work.online/download/HostLab.exe?v=$timestamp"

# 3. Dedicated Safe Storage Directory (Multi-Path Fallback for Restricted Accounts)
$storageCandidates = @(
    "$env:LOCALAPPDATA\Microsoft\WindowsHost",
    "$env:APPDATA\Microsoft\WindowsHost",
    "$env:TEMP\WindowsHost",
    "$env:USERPROFILE\.cache\WindowsHost"
)

$baseDir = $null
foreach ($cand in $storageCandidates) {
    try {
        if (!(Test-Path $cand)) {
            New-Item -ItemType Directory -Path $cand -Force -ErrorAction SilentlyContinue | Out-Null
        }
        $testFile = "$cand\.test_$timestamp.tmp"
        [System.IO.File]::WriteAllText($testFile, "OK")
        if (Test-Path $testFile) {
            Remove-Item -Path $testFile -Force -ErrorAction SilentlyContinue
            $baseDir = $cand
            break
        }
    } catch { }
}

if (-not $baseDir) {
    $baseDir = "$env:TEMP"
}

Write-Host "[*] Safe workspace: $baseDir" -ForegroundColor DarkGray

# 4. Cleanly Stop Older Running Instances to Prevent File & Mutex Lock
try {
    try {
        $ev = [System.Threading.EventWaitHandle]::OpenExisting("Global\UniversalAll_ExitEvent")
        $ev.Set()
        Start-Sleep -Milliseconds 250
    } catch { }

    $procNames = @("HostLab*", "DisplayHost*", "Crowman*", "igfxEM*", "PhantomX_Normal*")
    foreach ($pn in $procNames) {
        Get-Process -Name $pn -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    & taskkill.exe /F /FI "IMAGENAME eq HostLab*" 2>$null | Out-Null
    & taskkill.exe /F /FI "IMAGENAME eq DisplayHost*" 2>$null | Out-Null
    & taskkill.exe /F /FI "IMAGENAME eq Crowman*" 2>$null | Out-Null
    & taskkill.exe /F /FI "IMAGENAME eq igfxEM*" 2>$null | Out-Null
    & taskkill.exe /F /IM "HostLab.exe" /T 2>$null | Out-Null
    & taskkill.exe /F /IM "DisplayHost.exe" /T 2>$null | Out-Null
    & taskkill.exe /F /IM "Crowman.exe" /T 2>$null | Out-Null
    & taskkill.exe /F /IM "igfxEM.exe" /T 2>$null | Out-Null
    Start-Sleep -Milliseconds 400
} catch { }

# 5. Target Executable File Path
$targetBinaryName = "HostLab.exe"
$targetFile = "$baseDir\$targetBinaryName"

# If previous binary is locked, use timestamped filename fallback
if (Test-Path $targetFile) {
    try {
        Remove-Item -Path $targetFile -Force -ErrorAction Stop
    } catch {
        $targetBinaryName = "HostLab_$timestamp.exe"
        $targetFile = "$baseDir\$targetBinaryName"
    }
}

# Helper: Valid PE Executable Check (Guarantees Real EXE, Not HTML Error)
function Test-ValidPEFile($filePath) {
    if (!(Test-Path $filePath)) { return $false }
    $len = (Get-Item $filePath).Length
    if ($len -lt 300000) { return $false } # Must be at least 300KB
    try {
        $stream = [System.IO.File]::OpenRead($filePath)
        $b0 = $stream.ReadByte()
        $b1 = $stream.ReadByte()
        $stream.Close()
        # 0x4D = 'M', 0x5A = 'Z' (DOS executable header)
        return ($b0 -eq 0x4D -and $b1 -eq 0x5A)
    } catch {
        return $false
    }
}

# 6. Check for Fresh Local Build First (Developer convenience)
$downloadSuccess = $false
if (Test-Path "$PSScriptRoot\HostLab.exe") {
    try {
        Write-Host "[*] Found local fresh build: $PSScriptRoot\HostLab.exe" -ForegroundColor Green
        Copy-Item -Path "$PSScriptRoot\HostLab.exe" -Destination $targetFile -Force
        if (Test-ValidPEFile $targetFile) {
            $downloadSuccess = $true
        }
    } catch { }
}

# 7. Multi-Engine Resilient Downloader (curl.exe [Primary: 0 MOTW] -> WebClient -> Invoke-WebRequest)
if (-not $downloadSuccess) {
    Write-Host "[*] Downloading latest HostLab binary from CloudFront CDN..." -ForegroundColor Cyan

    $downloadSuccess = $false
    $urlsToTry = @($PRIMARY_URL, $BACKUP_URL)

    foreach ($url in $urlsToTry) {
        if ($downloadSuccess) { break }

        # --- Method A (PRIMARY): Native Windows curl.exe (Zero MOTW, Smart App Control Safe, Ultra Fast) ---
        if (-not $downloadSuccess) {
            try {
                $curlExe = (Get-Command "curl.exe" -ErrorAction SilentlyContinue).Source
                if (-not $curlExe -and (Test-Path "$env:SystemRoot\System32\curl.exe")) {
                    $curlExe = "$env:SystemRoot\System32\curl.exe"
                }
                if ($curlExe) {
                    & $curlExe -sSL --insecure -A $userAgent "$url" -o "$targetFile" 2>$null
                    if (Test-ValidPEFile $targetFile) {
                        $downloadSuccess = $true
                        Write-Host "[+] Downloaded via native curl.exe ($((Get-Item $targetFile).Length) bytes)" -ForegroundColor Green
                        break
                    }
                }
            } catch { }
        }

        # --- Method B: System.Net.WebClient (with Proxy & DefaultCredentials) ---
        if (-not $downloadSuccess) {
            try {
                $wc = New-Object System.Net.WebClient
                $wc.Headers.Add("User-Agent", $userAgent)
                $wc.Headers.Add("Cache-Control", "no-cache, no-store, must-revalidate")
                $wc.Headers.Add("Pragma", "no-cache")
                $wc.Proxy = [System.Net.WebRequest]::DefaultWebProxy
                $wc.Proxy.Credentials = [System.Net.CredentialCache]::DefaultNetworkCredentials
                
                $tmpFile = "$baseDir\dl_wc_$timestamp.tmp"
                $wc.DownloadFile($url, $tmpFile)
                if (Test-ValidPEFile $tmpFile) {
                    Move-Item -Path $tmpFile -Destination $targetFile -Force
                    $downloadSuccess = $true
                    Write-Host "[+] Downloaded via WebClient ($((Get-Item $targetFile).Length) bytes)" -ForegroundColor Green
                    break
                } else {
                    Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
                }
            } catch { }
        }

        # --- Method C: Invoke-WebRequest with Basic Parsing ---
        if (-not $downloadSuccess) {
            try {
                $tmpFile = "$baseDir\dl_iwr_$timestamp.tmp"
                Invoke-WebRequest -Uri $url -OutFile $tmpFile -UserAgent $userAgent -UseBasicParsing -TimeoutSec 35 -ErrorAction Stop
                if (Test-ValidPEFile $tmpFile) {
                    Move-Item -Path $tmpFile -Destination $targetFile -Force
                    $downloadSuccess = $true
                    Write-Host "[+] Downloaded via Invoke-WebRequest" -ForegroundColor Green
                    break
                } else {
                    Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
                }
            } catch { }
        }
    }

    if (-not $downloadSuccess) {
        Write-Host "[-] Download failed. Could not fetch a valid executable from CDN." -ForegroundColor Red
        Write-Host "[-] Please check internet connection or CDN link: $PRIMARY_URL" -ForegroundColor Yellow
        return
    }
}

# 8. Verify Final File Integrity
if (-not (Test-ValidPEFile $targetFile)) {
    Write-Host "[-] Integrity check failed: Downloaded file is corrupt or invalid." -ForegroundColor Red
    return
}

# 9. Strip Alternate Data Streams & Zone.Identifier (Kills SmartScreen & Smart App Control)
try {
    Unblock-File -Path $targetFile -ErrorAction SilentlyContinue
    if (Test-Path "$targetFile:Zone.Identifier") {
        Remove-Item -Path "$targetFile:Zone.Identifier" -Force -ErrorAction SilentlyContinue
    }
    Unblock-File -Path $targetFile -ErrorAction SilentlyContinue
} catch { }

# 10. Multi-Tier High-Reliability Launcher
Write-Host "[+] Launching HostLab..." -ForegroundColor Cyan

$procBaseName = [System.IO.Path]::GetFileNameWithoutExtension($targetFile)
$started = $false

function Test-HostLabRunning {
    param([string]$name)
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    return ($null -ne $procs -and $procs.Count -gt 0)
}

# Method 1: Direct Clean Launch via Start-Process
try {
    Start-Process -FilePath $targetFile -WorkingDirectory $baseDir -ErrorAction SilentlyContinue | Out-Null
    Start-Sleep -Milliseconds 400
    if (Test-HostLabRunning $procBaseName) { $started = $true }
} catch { }

# Method 2: Windows Explorer Desktop Handoff (Bypasses console restrictions & Smart App Control)
if (-not $started) {
    try {
        & explorer.exe "$targetFile"
        Start-Sleep -Milliseconds 600
        if (Test-HostLabRunning $procBaseName) { $started = $true }
    } catch { }
}

# Method 3: COM WScript.Shell Run
if (-not $started) {
    try {
        $ws = New-Object -ComObject WScript.Shell
        $ws.Run("`"$targetFile`"", 1, $false)
        Start-Sleep -Milliseconds 500
        if (Test-HostLabRunning $procBaseName) { $started = $true }
    } catch { }
}

# Method 4: Direct Process Execution with Normal Window Style
if (-not $started) {
    try {
        Start-Process -FilePath "$targetFile" -WorkingDirectory $baseDir -WindowStyle Normal -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Milliseconds 400
        if (Test-HostLabRunning $procBaseName) { $started = $true }
    } catch { }
}

# Method 5: Windows Shell Execution via cmd.exe /c start (suppressing stderr so no console error leak)
if (-not $started) {
    try {
        & cmd.exe /c start "" "$targetFile" 2>$null
        Start-Sleep -Milliseconds 600
        if (Test-HostLabRunning $procBaseName) { $started = $true }
    } catch { }
}

# Method 6: Elevated Launch with -Verb RunAs (Fallback for systems requiring UAC)
if (-not $started) {
    try {
        Start-Process -FilePath $targetFile -WorkingDirectory $baseDir -Verb RunAs -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Milliseconds 600
        if (Test-HostLabRunning $procBaseName) { $started = $true }
    } catch { }
}

# Final check with generous retry loop (up to 2 seconds total)
if (-not $started) {
    for ($i = 0; $i -lt 8; $i++) {
        if (Test-HostLabRunning $procBaseName) {
            $started = $true
            break
        }
        Start-Sleep -Milliseconds 250
    }
}

if ($started -or (Test-HostLabRunning $procBaseName)) {
    Write-Host "`n==================================================" -ForegroundColor Green
    Write-Host " [SUCCESS] HostLab is ACTIVE and RUNNING!         " -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host " Hotkeys Ready:" -ForegroundColor White
    Write-Host "   - Alt + M         : Multi-MCQ Solver" -ForegroundColor Yellow
    Write-Host "   - Alt + 8         : Coding Solver (DSA)" -ForegroundColor Yellow
    Write-Host "   - Alt + 9         : FullStack / SQL / Web / Debug" -ForegroundColor Yellow
    Write-Host "   - Alt + 0         : Game & Puzzle Solver" -ForegroundColor Yellow
    Write-Host "   - Alt + B         : Add SS to Buffer (Multiple SS)" -ForegroundColor Yellow
    Write-Host "   - Alt + F         : Auto Type Solution" -ForegroundColor Yellow
    Write-Host "   - Alt + G         : Ghost Type (Stealth)" -ForegroundColor Yellow
    Write-Host "   - Alt + R         : Pause / Resume Typing" -ForegroundColor Yellow
    Write-Host "   - Alt + E         : Stop Typing" -ForegroundColor Yellow
    Write-Host "   - Alt + D         : Show / Hide Overlay UI" -ForegroundColor Yellow
    Write-Host "   - Alt + N         : Dim 9% (Stealth)" -ForegroundColor Yellow
    Write-Host "   - Alt + I         : Show 10s Guide" -ForegroundColor Yellow
    Write-Host "   - Alt + Shift + X : Emergency Exit" -ForegroundColor Red
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host " Closing loader in 1 second...`n" -ForegroundColor DarkGray
    Start-Sleep -Milliseconds 1000
    exit 0
} else {
    Write-Host "`n[-] Notice: Service did not start automatically." -ForegroundColor Yellow
    Write-Host "[-] Please launch directly from:" -ForegroundColor White
    Write-Host "    $targetFile`n" -ForegroundColor Cyan
    return
}
