# HSR Team Builder Agent

《崩坏：星穹铁道》阵容搭配推荐 Agent：根据角色池、目标关卡和光锥，生成推荐阵容、配队思路、替代方案与养成建议。

## 功能

- 先获取米哈游官网最新版本号，再按版本检索配队攻略。
- 优先检索 B站 UP 主视频与米游社攻略帖；检索不足时再用通用网页搜索兜底。
- 输出固定 Markdown 结构：推荐阵容、配队思路、替代方案、养成建议、注意事项。
- 强制标注依据版本、来源作者与链接，识别并提示可能过期的攻略。
- 区分同名不同形态角色，例如丹恒 / 丹恒·饮月 / 丹恒·腾荒、三月七 / 长夜月、银狼 / 银狼 LV.999、刃 / 千冶·刃、知更鸟（晴歌）、砂金（戏浪）。

## 技术栈

- Python 3.10+
- LangGraph ReAct + LangChain
- DeepSeek（`deepseek-chat`）
- Starlette + SSE
- httpx + BeautifulSoup

## 运行

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .
copy .env.example .env        # 填入 DEEPSEEK_API_KEY
python app.py
```

打开 <http://127.0.0.1:8001>。

也可以使用 LangGraph 开发服务器：

```bash
pip install -e ".[dev]"
langgraph dev
```

## 工具

| 工具 | 作用 |
| --- | --- |
| `get_latest_version` | 从米哈游官网获取当前最新版本号 |
| `search_bilibili` | 搜索 B站 UP 主配队视频 |
| `search_miyoushe` | 搜索米游社攻略帖 |
| `search_web` | 通用网页搜索（兜底） |
| `fetch_webpage` | 抓取攻略正文 |

## 目录结构

```text
hsr-team-agent/
├── app.py                 # Starlette 网页服务 + SSE 接口
├── langgraph.json         # LangGraph 启动配置
├── pyproject.toml         # 依赖与项目配置
├── src/agent/
│   ├── config.py          # 环境变量配置
│   ├── graph.py           # ReAct 智能体与系统提示词
│   └── tools.py           # 版本获取、B站/米游社检索、网页抓取
└── web/
    └── index.html         # 配队助手页面
```

## 说明

- 不编造角色、数值或版本信息；检索不到时会如实说明素材不足。
- `.env` 含 API Key，已被 `.gitignore` 忽略，不会提交到仓库。
