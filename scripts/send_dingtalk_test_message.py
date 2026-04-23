from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.services.dingtalk_webhook_service import DingTalkWebhookService

RUNTIME_ENV_FILE = PROJECT_ROOT / 'data' / 'app.env'


def load_runtime_env_file() -> None:
    if not RUNTIME_ENV_FILE.exists():
        return

    for line in RUNTIME_ENV_FILE.read_text(encoding='utf-8-sig').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='发送一条钉钉 Webhook 测试消息')
    parser.add_argument(
        '--text',
        default='这是一条来自热点信息采集系统的钉钉测试消息。',
        help='测试消息正文',
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    load_runtime_env_file()
    settings = get_settings()
    settings = replace(settings, enable_dingtalk_notifier=True)
    service = DingTalkWebhookService(session=None, settings=settings)  # type: ignore[arg-type]

    if not settings.dingtalk_webhook.strip():
        raise SystemExit('未配置 DINGTALK_WEBHOOK')

    title = service._build_title()
    payload = {
        'msgtype': 'markdown',
        'markdown': {
            'title': title,
            'text': f'### {title}\n\n{args.text}',
        },
    }
    service._send_webhook(
        webhook=service._build_webhook_url(),
        payload=payload,
        timeout_seconds=10.0,
        secret=settings.dingtalk_secret.strip() or None,
    )
    print('钉钉测试消息发送成功。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
