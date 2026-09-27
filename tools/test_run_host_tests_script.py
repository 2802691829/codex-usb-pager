from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parent / "run_host_tests.ps1"
).read_text(encoding="utf-8")


def test_host_test_runner_has_a_hard_timeout() -> None:
    assert "--timeout 5" in SCRIPT
    assert "$LASTEXITCODE -ne 0" in SCRIPT
    assert "RedirectStandardOutput = $true" in SCRIPT
    assert "RedirectStandardError = $true" in SCRIPT


def test_host_test_runner_rebuilds_before_ctest() -> None:
    assert "cmake`\" --build" in SCRIPT
    assert "--clean-first" in SCRIPT
    assert "Invoke-BoundedBuild" in SCRIPT
    assert SCRIPT.rindex("Invoke-BoundedBuild") < SCRIPT.index(
        "& $ctest --test-dir"
    )


def test_host_test_runner_does_not_use_start_process() -> None:
    assert "Start-Process" not in SCRIPT
