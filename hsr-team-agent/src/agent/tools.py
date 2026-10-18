"""工具模块：为「星铁阵容搭配推荐」提供检索能力。

数据来源优先级：B站 UP主视频 / 米游社攻略帖（直连官方接口）> 通用网页搜索。
新增工具只需：用 @tool 装饰器定义函数并写清文档字符串，再加入 tools 列表。
"""

from __future__ import annotations

import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"}
BILI_HEADERS = {**HEADERS, "Referer": "https://www.bilibili.com/"}

_TAG_RE = re.compile(r"<[^>]+>")


def _fmt_ts(ts) -> str:
    """将时间戳格式化为日期字符串。"""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# 官方版本号
# ---------------------------------------------------------------------------

_OFFICIAL_URL = "https://sr.mihoyo.com/"
_VERSION_RE = re.compile(r"(\d+\.\d+)\s*版本")
_NAME_RE = re.compile(r"「([^」]{2,20})」")


@tool
def get_latest_version() -> str:
    """获取《崩坏：星穹铁道》当前最新版本号（数据来源：米哈游官网）。

    这是确认「当前最新版本」的权威来源，请在开始检索之前优先调用。
    """
    try:
        resp = httpx.get(_OFFICIAL_URL, headers=HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:  # noqa: BLE001
        return f"获取失败：{type(exc).__name__}"

    versions = _VERSION_RE.findall(html)
    if not versions:
        return "未能从官网解析到版本号。"

    version = max(set(versions), key=versions.count)
    name = ""
    for candidate in _NAME_RE.findall(html):
        if "版本" not in candidate:
            name = candidate
            break

    if name:
        return f"官网最新版本：{version}「{name}」（来源：{_OFFICIAL_URL}）"
    return f"官网最新版本：{version}（来源：{_OFFICIAL_URL}）"


# ---------------------------------------------------------------------------
# B站（哔哩哔哩）UP主视频
# ---------------------------------------------------------------------------


def _search_bilibili_impl(query: str, max_results: int) -> list[str]:
    """调用 B站搜索接口，返回 UP主视频列表。"""
    with httpx.Client(headers=BILI_HEADERS, timeout=20, follow_redirects=True) as client:
        client.get("https://www.bilibili.com/")  # 取得 buvid3 等 Cookie，避免 412
        resp = client.get(
            "https://api.bilibili.com/x/web-interface/search/type",
            params={"search_type": "video", "keyword": query},
        )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 0:
        return []

    results = (payload.get("data") or {}).get("result") or []
    items: list[str] = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        title = _TAG_RE.sub("", str(entry.get("title") or "")).strip()
        if not title:
            continue
        url = entry.get("arcurl") or ""
        if not url and entry.get("bvid"):
            url = f"https://www.bilibili.com/video/{entry['bvid']}"
        desc = str(entry.get("description") or "").strip().replace("\n", " ")
        items.append(
            f"{len(items) + 1}. {title}\n"
            f"   UP主：{entry.get('author') or ''} | 播放：{entry.get('play') or 0} | "
            f"发布：{_fmt_ts(entry.get('pubdate'))}\n"
            f"   {url}\n"
            f"   {desc[:120]}"
        )
        if len(items) >= max_results:
            break
    return items


@tool
def search_bilibili(query: str, max_results: int = 6) -> str:
    """搜索 B站（哔哩哔哩）UP主的视频，用于获取配队讲解与实战演示。

    建议关键词：星穹铁道 + 最新版本 + 角色名 + 配队 / 阵容 / 攻略。

    Args:
        query: 搜索关键词，例如「星穹铁道 4.6 黄泉 配队」。
        max_results: 返回结果条数，默认 6 条。
    """
    try:
        items = _search_bilibili_impl(query, max_results)
    except Exception as exc:  # noqa: BLE001
        return f"B站检索失败：{type(exc).__name__}"
    if not items:
        return "B站没有搜索到相关视频。"
    return "B站 UP主视频：\n" + "\n".join(items)


# ---------------------------------------------------------------------------
# 米游社攻略帖
# ---------------------------------------------------------------------------

_MIYOUSHE_API = "https://bbs-api.miyoushe.com/post/wapi/searchPosts"


def _search_miyoushe_impl(query: str, max_results: int) -> list[str]:
    """调用米游社搜索接口，返回攻略帖列表。"""
    resp = httpx.get(
        _MIYOUSHE_API,
        params={"keyword": query, "size": max_results, "page": 1},
        headers=HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("retcode") != 0:
        return []

    posts = (payload.get("data") or {}).get("posts") or []
    items: list[str] = []
    for entry in posts:
        post = entry.get("post") or {}
        user = entry.get("user") or {}
        subject = (post.get("subject") or "").strip()
        if not subject:
            continue
        content = (post.get("content") or "").strip().replace("\n", " ")
        post_id = post.get("post_id")
        url = f"https://www.miyoushe.com/sr/article/{post_id}" if post_id else ""
        items.append(
            f"{len(items) + 1}. {subject}\n"
            f"   作者：{user.get('nickname') or ''} | 发布：{_fmt_ts(post.get('created_at'))}\n"
            f"   {url}\n"
            f"   {content[:150]}"
        )
        if len(items) >= max_results:
            break
    return items


@tool
def search_miyoushe(query: str, max_results: int = 6) -> str:
    """搜索米游社（崩坏：星穹铁道社区）的攻略帖，用于获取攻略博主的配队思路。

    建议关键词：星穹铁道 + 最新版本 + 角色名 + 配队 / 阵容 / 攻略。

    Args:
        query: 搜索关键词，例如「星穹铁道 4.6 黄泉 配队」。
        max_results: 返回结果条数，默认 6 条。
    """
    try:
        items = _search_miyoushe_impl(query, max_results)
    except Exception as exc:  # noqa: BLE001
        return f"米游社检索失败：{type(exc).__name__}"
    if not items:
        return "米游社没有搜索到相关帖子。"
    return "米游社攻略帖：\n" + "\n".join(items)


# ---------------------------------------------------------------------------
# 通用网页搜索（兜底）
# ---------------------------------------------------------------------------


def _search_360(query: str, max_results: int) -> list[str]:
    """用 360 搜索（so.com）抓取结果。"""
    resp = httpx.get(
        "https://www.so.com/s",
        params={"q": query},
        headers=HEADERS,
        timeout=25,
        follow_redirects=True,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[str] = []
    for li in soup.select("li.res-list"):
        a = li.select_one("h3 a")
        if a is None or not a.get("href"):
            continue
        title = a.get_text(" ", strip=True)
        link = a["href"]
        snip_el = li.select_one("p.res-desc") or li.select_one("div.res-desc") or li.select_one("p")
        snippet = snip_el.get_text(" ", strip=True) if snip_el else ""
        items.append(f"{len(items) + 1}. {title}\n   {link}\n   {snippet}")
        if len(items) >= max_results:
            break
    return items


def _search_bing(query: str, max_results: int) -> list[str]:
    """用 Bing 抓取结果（备用）。"""
    resp = httpx.get(
        "https://cn.bing.com/search",
        params={"q": query},
        headers=HEADERS,
        timeout=25,
        follow_redirects=True,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[str] = []
    for li in soup.select("li.b_algo"):
        a = li.select_one("h2 a")
        if a is None or not a.get("href"):
            continue
        title = a.get_text(" ", strip=True)
        link = a["href"]
        caption = li.select_one(".b_caption p") or li.select_one("p")
        snippet = caption.get_text(" ", strip=True) if caption else ""
        items.append(f"{len(items) + 1}. {title}\n   {link}\n   {snippet}")
        if len(items) >= max_results:
            break
    return items


@tool
def search_web(query: str, max_results: int = 6) -> str:
    """通用网页搜索（兜底）。当 B站 / 米游社 检索不到时再用。

    Args:
        query: 搜索关键词。
        max_results: 返回结果条数，默认 6 条。
    """
    try:
        items = _search_360(query, max_results)
        if not items:
            items = _search_bing(query, max_results)
    except Exception as exc:  # noqa: BLE001
        return f"网页搜索失败：{type(exc).__name__}"
    if not items:
        return "没有搜索到相关结果。"
    return "搜索结果：\n" + "\n".join(items)


# ---------------------------------------------------------------------------
# 网页正文抓取
# ---------------------------------------------------------------------------

_REDIRECT_RE = re.compile(r"""window\.location\.replace\(\s*["']([^"']+)["']\s*\)""")
_META_RE = re.compile(
    r"""http-equiv=["']refresh["'][^>]*content=["'][^"']*url=([^"'\s>]+)""", re.I
)


def _extract_redirect(html: str) -> str | None:
    """从搜索引擎跳转页中解析真实目标地址。"""
    match = _REDIRECT_RE.search(html) or _META_RE.search(html)
    return match.group(1) if match else None


@tool
def fetch_webpage(url: str, max_chars: int = 4000) -> str:
    """抓取指定网页的正文文本，用于阅读攻略原文。

    自动处理搜索引擎跳转链接；抓取失败时返回提示，不会中断回答。

    Args:
        url: 网页地址，需以 http:// 或 https:// 开头。
        max_chars: 最多返回的字符数，默认 4000。
    """
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=25, follow_redirects=True)
        resp.raise_for_status()
        if len(resp.text) < 2000:
            target = _extract_redirect(resp.text)
            if target:
                resp = httpx.get(target, headers=HEADERS, timeout=25, follow_redirects=True)
                resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:  # noqa: BLE001
        return f"抓取失败：{type(exc).__name__}"

    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    lines = (line.strip() for line in soup.get_text("\n").splitlines())
    text = "\n".join(line for line in lines if line)
    if not text:
        return "未能从该网页提取到正文。"
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(内容已截断)"
    return text


tools = [
    get_latest_version,
    search_bilibili,
    search_miyoushe,
    search_web,
    fetch_webpage,
]
