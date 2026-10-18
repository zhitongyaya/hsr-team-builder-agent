"""星铁配队助手 —— 网页服务（基于 Starlette）。

单进程、同源：既提供网页，又直接运行智能体并流式返回结果，无跨域问题。

启动：
    python app.py
浏览器打开：
    http://127.0.0.1:8001
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import FileResponse, StreamingResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402

from agent.graph import graph  # noqa: E402


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def text_of(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and p.get("type") == "text":
                parts.append(p.get("text", ""))
        return "".join(parts)
    return ""


async def index(request: Request) -> FileResponse:
    return FileResponse(BASE_DIR / "web" / "index.html")


async def run(request: Request) -> StreamingResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    text = (body.get("text") or "").strip()

    async def gen():
        if not text:
            yield sse("error", {"text": "请先描述你的角色池与目标。"})
            yield sse("done", {})
            return
        yield sse("status", {"text": f"收到需求：{text}"})
        try:
            async for chunk in graph.astream(
                {"messages": [{"role": "user", "content": text}]},
                stream_mode="updates",
                config={"recursion_limit": 30},
            ):
                for _node, value in chunk.items():
                    messages = (value or {}).get("messages") or []
                    for m in messages:
                        mtype = getattr(m, "type", None) or type(m).__name__.lower()
                        tool_calls = getattr(m, "tool_calls", None) or []
                        for tc in tool_calls:
                            yield sse(
                                "tool_call",
                                {"name": tc.get("name", ""), "args": tc.get("args", {})},
                            )
                        if mtype in ("tool", "toolmessage"):
                            yield sse(
                                "tool_result",
                                {
                                    "name": getattr(m, "name", "") or "",
                                    "content": text_of(m.content),
                                },
                            )
                        elif mtype in ("ai", "aimessage"):
                            txt = text_of(m.content)
                            if txt.strip():
                                yield sse("assistant", {"content": txt})
            yield sse("done", {})
        except Exception as exc:  # noqa: BLE001
            yield sse("error", {"text": f"{type(exc).__name__}: {exc}"})
            yield sse("done", {})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


routes = [
    Route("/", index),
    Route("/api/run", run, methods=["POST"]),
]

app = Starlette(routes=routes)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
