import sys
from pathlib import Path


def find_tools_dir() -> Path:
    candidates = (
        Path.cwd() / "codex_usb_pager" / "tools",
        Path.cwd() / "tools",
        Path.home() / "Documents" / "saltyfish" / "codex_usb_pager" / "tools",
        Path.home() / "Documents" / "咸鱼接单" / "codex_usb_pager" / "tools",
    )
    for candidate in candidates:
        if (candidate / "pager_hook_runtime.py").exists():
            return candidate
    raise FileNotFoundError("Codex pager tools directory was not found")


TOOLS_DIR = find_tools_dir()
sys.path.insert(0, str(TOOLS_DIR))

from pager_hook_runtime import main


if __name__ == "__main__":
    raw_payload = sys.argv[1] if len(sys.argv) > 1 else "{}"
    raise SystemExit(main("DONE", raw_payload))
