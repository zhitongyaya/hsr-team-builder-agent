# 星铁社区舆情分析智能体

一个**独立**的智能体，**只负责《崩坏：星穹铁道》玩家社区舆论分析**，配有一个专用网页。

## 它能做什么

输入一个版本或话题关键词（如「贪饕」「4.5版本」），它会自动：

1. 规划搜索关键词，联网抓取玩家社区讨论（米游社 / B站 / 贴吧 / NGA / TapTap 等）
2. 清洗无效内容，保留有效玩家反馈
3. 判断情感（正面 / 中性 / 负面）并给出抽样占比
4. 归类诉求（Bug反馈 / 平衡性建议 / 剧情美术评价 / 活动福利吐槽）
5. 提炼 TOP 热点诉求，识别舆情风险
6. 输出标准化 Markdown 舆情简报

## 它**不**做什么

- 不处理与《崩坏：星穹铁道》社区舆情无关的任何问题。
- 不编造评论、数据或来源；抓不到素材会如实告知。

## 目录结构

```
hsr-sentiment-agent/
├── agent.py            # 智能体核心：人设 + 流程 + 搜索工具 + DeepSeek
├── app.py              # 网页服务（Starlette），提供 SSE 流式接口
├── static/
│   └── index.html      # 分析页面
├── .env                # 填入 DeepSeek API Key
└── README.md
```

## 运行

```bash
# 1. 创建并激活环境
python -m venv .venv
.venv\Scripts\activate        # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
copy .env.example .env        # 填入 DEEPSEEK_API_KEY

# 4. 启动
python app.py
```

浏览器打开：**http://127.0.0.1:8100**

## 说明

- 无「头条搜索插件」，使用内置联网搜索工具（Bing）代替，简报中会标注数据来源。
- 情感占比为抽样估算，非全量统计，简报中已明确标注。
- 无法访问的渠道（如小红书、小黑盒）会在「素材缺口」章节主动说明。
