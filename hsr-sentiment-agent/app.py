"""星铁社区舆情分析 —— 网页服务（基于 Starlette）。

启动：
    python app.py
浏览器打开：
    http://127.0.0.1:8100

接口：
    GET  /              分析页面
    POST /api/analyze   SSE 流式返回分析过程与简报
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

from agent import graph  # noqa: E402


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
    return FileResponse(BASE_DIR / "static" / "index.html")


async def analyze(request: Request) -> StreamingResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    topic = (body.get("topic") or "").strip()

    async def gen():
        if not topic:
            yield sse("error", {"text": "请输入关键词。"})
            yield sse("done", {})
            return
        yield sse("status", {"text": f"开始分析：{topic}"})
        try:
            async for chunk in graph.astream(
                {"messages": [{"role": "user", "content": topic}]},
                stream_mode="updates",
                config={"recursion_limit": 30},
            ):
                for _node, value in chunk.items():
                    messages = (value or {}).get("messages") or []
                    for m in messages:
                        mtype = getattr(m, "type", None) or type(m).__name__.lower()
                        tool_calls = getattr(m, "tool_calls", None) or []
                        if tool_calls:
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
    Route("/api/analyze", analyze, methods=["POST"]),
]

app = Starlette(routes=routes)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8100"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
