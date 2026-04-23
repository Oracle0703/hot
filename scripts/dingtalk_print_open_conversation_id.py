from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="通过钉钉 Stream Mode 监听群事件，并打印 openConversationId。"
    )
    parser.add_argument("--client-id", required=True, help="钉钉应用 ClientId")
    parser.add_argument("--client-secret", required=True, help="钉钉应用 ClientSecret")
    parser.add_argument(
        "--event-type",
        default="chat_update_title",
        help="要重点观察的事件类型，默认 chat_update_title",
    )
    return parser


def _normalize_event_data(raw_data: object) -> dict[str, object]:
    if isinstance(raw_data, Mapping):
        return dict(raw_data)
    if isinstance(raw_data, str):
        try:
            decoded = json.loads(raw_data)
        except json.JSONDecodeError:
            return {"raw": raw_data}
        if isinstance(decoded, Mapping):
            return dict(decoded)
        return {"raw": decoded}
    return {"raw": raw_data}


def _extract_open_conversation_id(data: Mapping[str, object]) -> str | None:
    value = data.get("openConversationId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def main() -> int:
    args = build_parser().parse_args()

    try:
        import dingtalk_stream
    except ImportError:
        print(
            "缺少依赖 dingtalk-stream，请先执行: python -m pip install dingtalk-stream",
            file=sys.stderr,
        )
        return 1

    target_event_type = args.event_type

    class EventHandler(dingtalk_stream.EventHandler):
        async def process(self, event: object):
            headers = getattr(event, "headers", None)
            event_type = getattr(headers, "event_type", "unknown")
            event_id = getattr(headers, "event_id", "unknown")
            event_data = _normalize_event_data(getattr(event, "data", {}))
            open_conversation_id = _extract_open_conversation_id(event_data)

            print(
                json.dumps(
                    {
                        "event_type": event_type,
                        "event_id": event_id,
                        "openConversationId": open_conversation_id,
                        "data": event_data,
                    },
                    ensure_ascii=False,
                )
            )

            if event_type == target_event_type and open_conversation_id:
                print(f"\n找到 openConversationId: {open_conversation_id}\n")

            return dingtalk_stream.AckMessage.STATUS_OK, "OK"

    credential = dingtalk_stream.Credential(args.client_id, args.client_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)
    client.register_all_event_handler(EventHandler())

    print("已连接钉钉 Stream Mode。")
    print(f"当前重点监听事件: {target_event_type}")
    print("下一步: 去目标群里修改一次群名称，或触发你订阅的群事件。")
    client.start_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
