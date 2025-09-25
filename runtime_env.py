from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Iterable


def get_resource_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def ensure_path_in_sys_path(path: Path) -> None:
    resolved = str(path)
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def ensure_assets(asset_names: Iterable[str]) -> None:
    src_root = get_resource_dir()
    dst_root = get_base_dir()

    for name in asset_names:
        src = src_root / name
        dst = dst_root / name

        if not src.exists():
            continue

        if src.is_dir():
            if dst.exists():
                continue
            shutil.copytree(src, dst)
        else:
            if dst.exists():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
