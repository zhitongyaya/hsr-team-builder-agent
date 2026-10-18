"""星铁社区舆情分析智能体（核心）。

本模块定义一个「只做《崩坏：星穹铁道》玩家社区舆情分析」的 ReAct 智能体。

- 固定人设与流程，不处理与星铁舆情无关的问题；
- 主要数据来源：B站（search_bilibili）与米游社（search_miyoushe）官方接口；
- 先经官方确认最新版本，再据此检索，保证时效性；
- 不编造评论数据，输出标准化 Markdown 舆情简报。

环境变量：
    DEEPSEEK_API_KEY   DeepSeek 平台的 API Key（必填）
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from langchain_deepseek import ChatDeepSeek
from langgraph.prebuilt import create_react_agent

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
# 工具
# ---------------------------------------------------------------------------

# ---- 官方版本号 -----------------------------------------------------------

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


# ---- B站（哔哩哔哩）------------------------------------------------------


def _search_bilibili_impl(query: str, max_results: int) -> list[str]:
    """调用 B站搜索接口，返回视频/讨论列表。"""
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
def search_bilibili(query: str, max_results: int = 8) -> str:
    """搜索 B站（哔哩哔哩）相关视频与讨论，用于采集玩家社区舆论。

    Args:
        query: 搜索关键词，例如「星穹铁道 4.6 贪饕 玩家评价」。
        max_results: 返回结果条数，默认 8 条。
    """
    try:
        items = _search_bilibili_impl(query, max_results)
    except Exception as exc:  # noqa: BLE001
        return f"B站检索失败：{type(exc).__name__}"
    if not items:
        return "B站没有搜索到相关内容。"
    return "B站内容：\n" + "\n".join(items)


# ---- 米游社 ---------------------------------------------------------------

_MIYOUSHE_API = "https://bbs-api.miyoushe.com/post/wapi/searchPosts"


def _search_miyoushe_impl(query: str, max_results: int) -> list[str]:
    """调用米游社搜索接口，返回帖子列表。"""
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
def search_miyoushe(query: str, max_results: int = 8) -> str:
    """搜索米游社（崩坏：星穹铁道社区）的帖子，用于采集玩家讨论。

    Args:
        query: 搜索关键词，例如「星穹铁道 4.6 贪饕 玩家评价」。
        max_results: 返回结果条数，默认 8 条。
    """
    try:
        items = _search_miyoushe_impl(query, max_results)
    except Exception as exc:  # noqa: BLE001
        return f"米游社检索失败：{type(exc).__name__}"
    if not items:
        return "米游社没有搜索到相关帖子。"
    return "米游社帖子：\n" + "\n".join(items)


# ---- 通用网页搜索（兜底）--------------------------------------------------

COMMON_HEADERS = HEADERS


def _search_360(query: str, max_results: int) -> list[str]:
    """用 360 搜索（so.com）抓取结果。"""
    resp = httpx.get(
        "https://www.so.com/s",
        params={"q": query},
        headers=COMMON_HEADERS,
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
        headers=COMMON_HEADERS,
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
def search_community(query: str, max_results: int = 8) -> str:
    """通用网页搜索（兜底）。当 B站 / 米游社 覆盖不足时再用。

    Args:
        query: 搜索关键词，例如「星穹铁道 4.6 贪饕 贴吧讨论」。
        max_results: 返回结果条数，默认 8 条。
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


# ---- 指定渠道定向搜索 -----------------------------------------------------

_CHANNELS = {
    "贴吧": "tieba.baidu.com",
    "NGA": "nga.cn",
    "TapTap": "taptap.cn",
    "小红书": "xiaohongshu.com",
    "小黑盒": "xiaoheihe.cn",
}


@tool
def search_channel(platform: str, query: str, max_results: int = 8) -> str:
    """在指定的玩家社区渠道内定向搜索。

    Args:
        platform: 渠道名，必须是「贴吧」「NGA」「TapTap」「小红书」「小黑盒」之一。
        query: 搜索关键词，例如「星穹铁道 4.6 贪饕 玩家评价」。
        max_results: 返回结果条数，默认 8 条。
    """
    domain = _CHANNELS.get(platform.strip())
    if not domain:
        return f"不支持的渠道：{platform}。可选：{'、'.join(_CHANNELS)}"
    try:
        items = _search_360(f"{query} site:{domain}", max_results)
        if not items:
            items = _search_bing(f"{query} site:{domain}", max_results)
    except Exception as exc:  # noqa: BLE001
        return f"{platform} 检索失败：{type(exc).__name__}"
    if not items:
        return f"{platform} 没有检索到相关内容（该渠道覆盖可能不足）。"
    return f"{platform} 检索结果：\n" + "\n".join(items)


# ---- 网页正文抓取 ---------------------------------------------------------

_REDIRECT_RE = re.compile(r"""window\.location\.replace\(\s*["']([^"']+)["']\s*\)""")
_META_RE = re.compile(
    r"""http-equiv=["']refresh["'][^>]*content=["'][^"']*url=([^"'\s>]+)""", re.I
)


def _extract_redirect(html: str) -> str | None:
    """从搜索跳转页中解析真实目标地址。"""
    m = _REDIRECT_RE.search(html) or _META_RE.search(html)
    return m.group(1) if m else None


@tool
def fetch_page(url: str, max_chars: int = 4000) -> str:
    """抓取指定网址的正文文本，用于阅读玩家讨论原文。

    自动处理搜索引擎的跳转链接；抓取失败时返回提示，不会中断分析。

    Args:
        url: 网页地址，需以 http:// 或 https:// 开头。
        max_chars: 最多返回的字符数，默认 4000。
    """
    try:
        resp = httpx.get(url, headers=COMMON_HEADERS, timeout=25, follow_redirects=True)
        resp.raise_for_status()
        if len(resp.text) < 2000:
            target = _extract_redirect(resp.text)
            if target:
                resp = httpx.get(
                    target, headers=COMMON_HEADERS, timeout=25, follow_redirects=True
                )
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
    search_channel,
    search_community,
    fetch_page,
]

_TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# 人设与流程（固定）
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """你是「星铁社区舆情分析智能体」，**只负责《崩坏：星穹铁道》的玩家社区舆论分析**。

# 职责边界（最高优先级）
- 只处理与《崩坏：星穹铁道》玩家社区舆情相关的问题。
- 用户若提出与该主题无关的问题（如写代码、其他游戏、生活问题等），你只回复一句：
  「我只负责《崩坏：星穹铁道》的玩家社区舆情分析，请提供星铁的版本或话题关键词。」
  然后停止，不做任何其他回答，也不要调用工具。

# 时效要求（重要）
- 本次会话的当前日期是 __TODAY__。
- 第一步必须调用 get_latest_version 工具，从官方获取当前最新版本号，作为本次分析的时效基准。
- 若该工具失败，退化为搜索「星穹铁道 最新版本 版本号」，并说明版本可能不准确。
- 规划关键词时必须带上最新版本号，例如「星穹铁道 <最新版本> <关键词> 玩家评价」。
- 优先采用与最新版本相关的讨论；若素材整体偏旧（版本号远低于最新版本），
  必须标注「素材版本较旧」并建议扩大检索范围。

# 数据来源（重要）
- 主要来源：**B站（search_bilibili）** 与 **米游社（search_miyoushe）**，两者都要检索（各至少一次）。
- 补充来源：**贴吧 / NGA / TapTap / 小红书 / 小黑盒**，用 search_channel 指定渠道检索；
  至少尝试其中 2-3 个（优先 贴吧、TapTap、小黑盒）。
- 兜底来源：search_community（通用网页搜索），仅在以上都覆盖不足时使用。
- 对高价值链接可用 fetch_page 抓取正文。
- 引用时必须注明来源渠道与作者，例如「B站 UP主：XXX」「米游社作者：XXX」「贴吧：XXX」。
- 若某渠道检索不到内容，如实标注「该渠道素材不足」，不得编造。

# 工作流程
1. 先确认最新版本（见上）。
2. 分别调用 search_bilibili 与 search_miyoushe 检索，关键词带上最新版本号与话题关键词。
3. 文本清洗：过滤灌水、无意义、广告与无关内容，只保留有效玩家反馈。
4. 情感判断：区分 正面 / 中性 / 负面，并给出抽样占比。
5. 诉求归类：【Bug反馈】【平衡性建议】【剧情美术评价】【活动福利吐槽】。
6. 提炼 TOP 热点诉求，识别潜在舆情风险。
7. 输出标准化 Markdown 舆情简报。

# 强制规则
- 需要社区信息时**必须调用检索工具**，**严禁编造任何评论、数据或来源**。
- 搜索结果杂乱时必须主动筛选有效玩家发言。
- 占比必须是抽样估算，且在简报中明确标注「非全量统计」。
- 某渠道素材不足时，**主动告知用户并建议扩大搜索范围**，不得用编造内容补齐。
- 不要闲聊，专注完成舆情分析任务。
- 最后一条回复必须只包含 Markdown 简报本身，不要有额外寒暄。

# 输出格式（固定）
# 《崩坏：星穹铁道》「{关键词}」玩家舆情简报

> 数据说明：基于公开可检索的玩家社区讨论抽样（样本 N 条），非全量统计，占比为估算。
> 依据版本：<版本号>（<大致时间>）

## 一、分析范围与数据来源
（渠道覆盖表：B站 / 米游社 为主要来源，贴吧 / NGA / TapTap / 小红书 / 小黑盒 标注覆盖情况）

## 二、情感分布
（表格：正面 / 中性 / 负面 + 占比 + 典型特征）

## 三、诉求分类
（表格：Bug反馈 / 平衡性建议 / 剧情美术评价 / 活动福利吐槽，含素材量说明）

## 四、TOP 热点诉求
（编号列表，3-5 条，标注热度与依据）

## 五、潜在舆情风险
（表格：风险等级 + 说明）

## 六、素材缺口与建议
（按需，主动说明哪些渠道素材不足）

## 七、来源清单
（列出实际引用到的链接，并标注 B站 UP主 / 米游社作者）

# 结尾提示
简报结束后，追加一行：如需扩展分析或补充渠道，请说明。
""".replace("__TODAY__", _TODAY)

model = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)

graph = create_react_agent(
    model=model,
    tools=tools,
    prompt=SYSTEM_PROMPT,
    name="hsr_sentiment_agent",
)
