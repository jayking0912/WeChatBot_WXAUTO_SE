import argparse
from typing import List

from runtime_env import ensure_assets, ensure_path_in_sys_path, get_base_dir


RUNTIME_ASSETS: List[str] = [
    'config.py',
    'version.json',
    'recurring_reminders.json',
    'prompts',
    'templates',
    'emojis',
    'Demo_Image',
]


def ensure_runtime_environment() -> None:
    base_dir = get_base_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    ensure_path_in_sys_path(base_dir)
    ensure_assets(RUNTIME_ASSETS)


def main() -> None:
    parser = argparse.ArgumentParser(description='WeChatBot launcher')
    parser.add_argument('--bot', action='store_true', help='Run the bot process instead of the configuration editor.')
    args = parser.parse_args()

    ensure_runtime_environment()

    if args.bot:
        from bot import main as run_bot
        run_bot()
    else:
        from config_editor import run as run_editor
        run_editor()


if __name__ == '__main__':
    main()
