# 手办猎手 (Shouban Lieshou) MVP-0

> 日本手办跨平台套利监控桌面软件 — MVP-0 最小可跑版本

## 一、项目简介

在日本二手平台（挖煤姬 / Mercari / Yahoo 拍卖 / Suruga / Amazon JP）搜索手办，通过国内闲鱼均价 × 角色热度分级做售价预估，结合代购费、国际运费、关税计算真实成本，筛选出「利润率 ≥ X% 且 毛利 ≥ Y 元」双阈值达标的套利机会，桌面弹窗推送，并对拍卖形式商品进入「盯拍」队列分级预警 + 反推最大心理价位。

**MVP-0 核心闭环：**

```
Mock 爬虫 (Wamei 商品 + 闲鱼均价)
        ↓
IP / 角色匹配 (两表 + S/A/B/C 热度分级)
        ↓
套利引擎 (成本拆解 + 单品/打包计算 + 二分反推max_bid_jpy)
        ↓
双阈值判断 (利润率 ≥ 20% 且 毛利 ≥ 30 元)
        ↓
达标: SQLite 入库 candidate_items → 桌面推送
拍卖: 入 auction_watches 盯拍表 (6 状态机 + L1/L2/L3 三级提醒)
```

## 二、快速开始

### 环境要求
- Python 3.10+
- Windows 10/11（PySide6 桌面 UI）

### 安装依赖
```bash
pip install -r requirements.txt
```

### 先跑逻辑烟雾测试（无 UI，验证公式全链路）
```bash
python verify_logic.py
```
预期输出 7 步断言全部通过 ✅，包括：
- 火影 11 件打包 8000 日元 → 毛利 ≥ 30 且 利润率 ≥ 20%（通过阈值）
- 单品鸣人 S 级 3000 日元 → 毛利倒挂（正确不通过）
- 反向求解 max_bid_jpy（二分 80 次，回算利润率 ≈ 20% 贴线）

### 启动桌面 UI
```bash
python main.py
```
- 主界面两 Tab：候选商品 / 盯拍拍卖
- 左侧日志 + 底部进度条
- 窗口关闭 = 最小化到系统托盘（有达标会弹窗）

## 三、核心套利模型（MVP-0 默认参数见 config/settings.py）

| 项 | 默认值 | 说明 |
|----|--------|------|
| 汇率 JPY→CNY | 0.0437 | 1 日元 ≈ 0.0437 元 |
| 代购服务费 | 8% | 日本代购平台手续费 |
| 打包费 | 20 元/件 封顶 80 | 包装加固等杂费 |
| 国际运费 | 40 元/公斤, 每件按 0.6 kg 估算 | 海运/EMS 近似值 |
| 综合关税 | 5% | (基价+国际运费) × 5% |
| 闲鱼手续费 | 1.5% | 闲鱼成交抽成 |
| 利润率阈值 | 20% | `net_profit / total_cost ≥ 0.20` |
| 毛利阈值 | 30 元 | `net_profit ≥ 30` |
| 角色热度 S/A/B/C | 1.2 / 1.0 / 0.7 / 0.4 | 乘闲鱼均价得到实际预售价 |

**打包是核心套利机会**：Mock 爬虫中套装商品价格打 0.75 折模拟卖家急售，单品大多倒挂，打包才能过阈值。

## 四、目录结构

```
.
├── main.py                   # PySide6 启动入口 (bootstrap DB+种子 → QApplication)
├── verify_logic.py           # 纯逻辑烟雾测试 (7 步断言, 无 UI)
├── seed_data.py              # 6 IP × 5-8 角色种子 (海贼王/鬼灭/火影/咒术/初音/我英)
├── requirements.txt          # PySide6 / requests / bs4 / lxml / APScheduler
├── config/
│   ├── settings.py           # 路径 / 阈值 / 汇率 / 代购/运费/关税等常量
│   └── __init__.py
└── src/
    ├── models/               # SQLite DAL (单例封装 + 参数化 SQL + 线程锁)
    │   ├── database.py       # 4 张表建表: ips / characters / candidate_items / auction_watches
    │   ├── ip_model.py       # IP 增查 + 别名/关键词子串模糊匹配
    │   ├── character_model.py # 角色增查 + IP 内 price_factor 均值(打包无识别时兜底)
    │   ├── candidate_model.py # candidate_items CRUD (达标记录, 含完整计算分项快照)
    │   └── auction_watch_model.py # 盯拍 6 状态机: watching→over_threshold→bidded→won/lost/canceled/archived
    ├── services/
    │   ├── arbitrage_engine.py # ⭐核心: 单品/打包计算 + 二分reverse_max_bid_jpy
    │   └── scan_service.py     # 全链路粘合: 爬虫→IP匹配→闲鱼均价→计算→入库→推送→盯拍
    ├── crawlers/             # BaseCrawler / BaseXianyuCrawler 接口 + Mock 实现
    │   ├── base.py
    │   ├── wamei_crawler.py  # WameiMockCrawler: 6 IP 标题池 × 4 档价格 × 60% 打包打真折扣
    │   ├── xianyu_crawler.py # XianyuMockCrawler: 6 IP 均价 + 去极值 30 样本模拟
    │   └── __init__.py       # default_wamei / default_xianyu 单例
    ├── notifier/             # 桌面推送 (QSystemTrayIcon + 微信/邮件占位)
    │   └── desktop_notifier.py
    └── ui/                   # PySide6 界面
        ├── main_window.py    # MainWindow + ScanWorker(QThread) 后台扫描 + 托盘
        ├── settings_dialog.py # 扫描选项对话框 (双阈值/抓取数量/推送勾选)
        ├── auction_watch_panel.py # 盯拍表格 (11 列, 剩余时间, 状态/价格染色)
        └── widgets/
            └── candidate_table.py # 候选商品表格 (11 列, 利润率/毛利区间染色)
```

## 五、迭代路标（MVP-0 之后）

- **P0.5（优先）**：把 `wamei_crawler` / `xianyu_crawler` 的 Mock 换成真 `requests + bs4 / Playwright` 爬取挖煤姬 + 闲鱼（MVP-0 接口已抽象好，只改子类实现）
- **P1 盯拍增强**：`APScheduler` 做 L1(30min) / L2(5min) / L3(1min) 三级刷新 + 被超价即时推送 + 到时间自动下架 won/lost
- **P1 打包识别**：商品图片 OCR + 角色关键词匹配，精确识别套装包含哪些角色（当前靠 LLM / 标题正则兜底）
- **P2 平台扩展**：Mercari / Yahoo 拍卖 / Suruga-ya / Amazon JP 四个新爬虫（均继承 BaseCrawler）
- **P2 真汇率**：接中农工建实时汇率 API（替换 config 常量）
- **P3 自动出价（风险开关，默认关）**：在盯拍 `over_threshold` 状态下按 `max_bid_jpy` 自动加价（需要风控 + 白名单）

## 六、注意事项

1. MVP-0 的爬虫为 Mock 数据，确保 UI 有稳定可感知的套利结果演示效果。生产环境替换真实爬虫即可。
2. SQLite 数据库首次启动会自动建表并写入种子数据，文件默认放在 `data/app.db`（已被 `.gitignore` 忽略）。
3. 打包套利的利润空间远大于单品，实际使用中请重点关注 まとめ売り / セット売り / 点セット / BOX 商品。
