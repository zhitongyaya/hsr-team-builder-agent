# HSR AI Agents

围绕《崩坏：星穹铁道》的两个 AI Agent 项目，基于 **LangGraph + DeepSeek**，分别面向玩家社区舆情分析与阵容搭配推荐。

> 仓库只包含源码与 `.env.example`，真实 API Key 请在本地 `.env` 中配置，不会提交到仓库。

## 项目一览

| 项目 | 目录 | 解决的问题 | 技术栈 |
| --- | --- | --- | --- |
| 星铁社区舆情分析智能体 | [hsr-sentiment-agent](./hsr-sentiment-agent) | 多渠道玩家反馈收集、清洗、情感分类、诉求归类与舆情简报 | Python、LangGraph、DeepSeek、Starlette、SSE、httpx、BeautifulSoup |
| 星铁阵容搭配推荐 Agent | [hsr-team-agent](./hsr-team-agent) | 版本感知的配队推荐、替代方案、养成建议与来源追溯 | Python、LangGraph ReAct、DeepSeek、httpx、BeautifulSoup |

## 快速开始

### 1. 星铁社区舆情分析智能体

```bash
cd hsr-sentiment-agent
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # 填入 DEEPSEEK_API_KEY
python app.py
```

打开 <http://127.0.0.1:8100>。

### 2. 星铁阵容搭配推荐 Agent

```bash
cd hsr-team-agent
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env        # 填入 DEEPSEEK_API_KEY
python app.py
```

打开 <http://127.0.0.1:8001>；也可以执行 `langgraph dev` 在 LangGraph Studio 中调试。

## 设计思路

- **舆情分析**：把分散在米游社、B站、贴吧、NGA、TapTap 的讨论收敛成一个可重复运行的分析流程，输出带来源标注的 Markdown 简报。
- **配队推荐**：先确认官方最新版本，再检索 B站 / 米游社攻略，固定输出结构并标注来源，避免攻略过期和来源不明。
- **共同约束**：不编造评论、角色、数值或版本信息；检索不到时如实说明素材缺口。

## 目录结构

```text
.
├── hsr-sentiment-agent/   # 星铁社区舆情分析智能体
└── hsr-team-agent/        # 星铁阵容搭配推荐 Agent
```

## 安全说明

- `.env` 已被 `.gitignore` 忽略，仓库中只有 `.env.example`。
- 如果曾在本地截图或日志中暴露 Key，请及时在 DeepSeek 控制台轮换。
