from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parent / "build_rp2040.ps1"
).read_text(encoding="utf-8")


def test_build_clears_orphaned_pdb_service_without_killing_active_builds() -> None:
    assert "Get-Process cl,cmake,nmake,msbuild" in SCRIPT
    assert "Get-Process mspdbsrv" in SCRIPT
    assert "Stop-Process -Force" in SCRIPT
    assert "if (-not $activeBuildProcesses)" in SCRIPT


def test_build_steps_have_hard_timeouts_and_kill_the_process_tree() -> None:
    assert "Invoke-BoundedCommand" in SCRIPT
    assert "WaitForExit" in SCRIPT
    assert "taskkill.exe /PID $process.Id /T /F" in SCRIPT
    assert "ConfigureTimeoutSeconds" in SCRIPT
    assert "BuildTimeoutSeconds" in SCRIPT
    assert "RedirectStandardOutput = $true" in SCRIPT
    assert "RedirectStandardError = $true" in SCRIPT
    assert "[Console]::Error.WriteLine" in SCRIPT


def test_configure_and_build_are_separate_commands() -> None:
    assert "-Description \"RP2040 firmware configure\"" in SCRIPT
    assert "-Description \"RP2040 firmware build\"" in SCRIPT
