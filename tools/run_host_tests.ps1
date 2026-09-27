param(
    [string]$BuildDirectory = "build-rp2040-host-blossom",
    [int]$BuildTimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$buildPath = Join-Path $projectRoot $BuildDirectory
$cmake = (Get-Command cmake -ErrorAction Stop).Source
$ctest = (Get-Command ctest -ErrorAction Stop).Source
$vsDevCmd = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"

function Invoke-BoundedBuild {
    $command = "`"$vsDevCmd`" -arch=x64 -host_arch=x64 >nul && `"$cmake`" --build `"$buildPath`" --clean-first"
    $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $env:ComSpec
    $processInfo.Arguments = "/d /s /c `"$command`""
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
    if (-not $process.WaitForExit($BuildTimeoutSeconds * 1000)) {
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        throw "Host test build timed out after $BuildTimeoutSeconds seconds"
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
        throw "Host test build failed with exit code $($process.ExitCode)"
    }
}

if (-not (Test-Path -LiteralPath $buildPath)) {
    throw "Host test build directory was not found: $buildPath"
}
if (-not (Test-Path -LiteralPath $vsDevCmd)) {
    throw "Visual Studio build environment was not found: $vsDevCmd"
}

Invoke-BoundedBuild

& $ctest --test-dir $buildPath --output-on-failure --timeout 5
if ($LASTEXITCODE -ne 0) {
    throw "Host tests failed with exit code $LASTEXITCODE"
}
