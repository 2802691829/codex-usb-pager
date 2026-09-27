param(
    [string]$StageRoot = "C:\Temp\codex-pager-rp2040-build",
    [string]$ToolchainRoot = "C:\ST\STM32CubeIDE_2.2.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.14.3.rel1.win32_1.0.100.202602081740\tools",
    [int]$ConfigureTimeoutSeconds = 120,
    [int]$BuildTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $projectRoot
$sdkSource = Join-Path $workspaceRoot "third_party\pico-sdk"
$picotoolSource = Join-Path $workspaceRoot "third_party\picotool-cache"
$sourceStage = Join-Path $StageRoot "src"
$sdkStage = Join-Path $StageRoot "pico-sdk"
$picotoolStage = Join-Path $StageRoot "picotool-cache"
$buildDir = Join-Path $StageRoot "build"
$vsDevCmd = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"

function Invoke-BoundedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $env:ComSpec
    $processInfo.Arguments = "/d /s /c `"$Command`""
    $processInfo.WorkingDirectory = $projectRoot
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $processInfo
    [void]$process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        throw "$Description timed out after $TimeoutSeconds seconds"
    }
    if ($process.ExitCode -ne 0) {
        $stdout = $stdoutTask.Result
        $stderr = $stderrTask.Result
        if (-not [string]::IsNullOrWhiteSpace($stdout)) {
            Write-Host $stdout
        }
        if (-not [string]::IsNullOrWhiteSpace($stderr)) {
            [Console]::Error.WriteLine($stderr)
        }
        throw "$Description failed with exit code $($process.ExitCode)"
    }
}

$activeBuildProcesses = Get-Process cl,cmake,nmake,msbuild -ErrorAction SilentlyContinue
if (-not $activeBuildProcesses) {
    Get-Process mspdbsrv -ErrorAction SilentlyContinue | Stop-Process -Force
}

foreach ($required in @($sdkSource, $vsDevCmd, (Join-Path $ToolchainRoot "bin\arm-none-eabi-gcc.exe"))) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required build dependency was not found: $required"
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $sourceStage "ports\rp2040-zero") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $sourceStage "Core\Src") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $sourceStage "Core\Inc") | Out-Null

Copy-Item -LiteralPath (Join-Path $projectRoot "ports\rp2040-zero\firmware") `
    -Destination (Join-Path $sourceStage "ports\rp2040-zero") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "Core\Src\blossom_asset.c") `
    -Destination (Join-Path $sourceStage "Core\Src\blossom_asset.c") -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "Core\Inc\blossom_asset.h") `
    -Destination (Join-Path $sourceStage "Core\Inc\blossom_asset.h") -Force

if (-not (Test-Path -LiteralPath $sdkStage)) {
    Copy-Item -LiteralPath $sdkSource -Destination $sdkStage -Recurse
}
if ((Test-Path -LiteralPath $picotoolSource) -and -not (Test-Path -LiteralPath $picotoolStage)) {
    Copy-Item -LiteralPath $picotoolSource -Destination $picotoolStage -Recurse
}

$firmwareSource = Join-Path $sourceStage "ports\rp2040-zero\firmware"
$configure = "set `"PICO_SDK_PATH=$sdkStage`" && set `"PICO_TOOLCHAIN_PATH=$ToolchainRoot`" && cmake -S `"$firmwareSource`" -B `"$buildDir`" -G `"NMake Makefiles`" -DPICO_BOARD=pico"
if (Test-Path -LiteralPath $picotoolStage) {
    $configure += " -DPICOTOOL_FETCH_FROM_GIT_PATH=`"$picotoolStage`""
}
$vsPrefix = "`"$vsDevCmd`" -arch=x64 -host_arch=x64 >nul && "
Invoke-BoundedCommand `
    -Command ($vsPrefix + $configure) `
    -TimeoutSeconds $ConfigureTimeoutSeconds `
    -Description "RP2040 firmware configure"
Invoke-BoundedCommand `
    -Command ($vsPrefix + "cmake --build `"$buildDir`"") `
    -TimeoutSeconds $BuildTimeoutSeconds `
    -Description "RP2040 firmware build"

$uf2 = Join-Path $buildDir "codex_pager_rp2040.uf2"
$outputDir = Join-Path $projectRoot "build-rp2040"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
Copy-Item -LiteralPath $uf2 -Destination (Join-Path $outputDir "codex_pager_rp2040.uf2") -Force
Get-FileHash -Algorithm SHA256 -LiteralPath $uf2
