from pathlib import Path


TOOLS = Path(__file__).resolve().parent


def test_hook_templates_support_current_and_future_project_names() -> None:
    for name in ("codex_pager_global_hook.py", "codex_notify_pager.py"):
        source = (TOOLS / name).read_text(encoding="utf-8")
        assert '"咸鱼接单"' in source
        assert '"saltyfish"' in source
        assert "Path.cwd()" in source
