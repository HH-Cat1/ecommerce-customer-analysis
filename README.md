# 智营：智能电商数据分析平台

一个可本地运行的电商经营分析平台。平台将订单 CSV 持久化到 SQLite，计算销售额、订单数、成交客户和客单价，并提供趋势分析、品类/渠道/地区表现、RFM 客户分层、自动经营洞察和自然语言问数。

## 快速开始

需要 Python 3.10 或更高版本。

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

首次打开会自动载入 `data/sample_orders.csv` 并创建 `data/ecommerce.db`。默认是只读演示模式，访客不会改动共享数据。若要在自己的电脑上启用 CSV 导入，在本地 `.env` 增加 `ALLOW_ORDER_IMPORT=true`，再重启应用；导入会替换 SQLite 数据库中的订单明细。

## 发布成公开链接

本项目适合部署到 Streamlit Community Cloud。公开部署使用示例数据，不需要 AI 密钥；访客上传入口默认关闭，避免不同访客覆盖同一份数据库。部署会要求你登录自己的 GitHub 和 Streamlit 账号。

### 1. 把项目上传到 GitHub

先登录 GitHub，创建一个仓库，例如 `smart-ecommerce-analytics`。如果把仓库设为 Public，别人也能看到源代码；如果只想公开应用链接，可以用 Private 仓库，再在 Streamlit 应用分享设置中将应用设为 Public。

在 PowerShell 里运行下面命令。把 `<你的GitHub用户名>` 替换成你的 GitHub 用户名：

```powershell
cd "C:\Users\何\Documents\Codex\2026-10-30\xiao-xiang-mu\outputs\ecommerce-analytics"
git init
git add app.py ai_qa.py db.py generate_sample.py requirements.txt README.md .gitignore .env.example .python-version data/sample_orders.csv
git commit -m "Prepare ecommerce analytics demo"
git branch -M main
git remote add origin https://github.com/<你的GitHub用户名>/smart-ecommerce-analytics.git
git push -u origin main
```

上传前确认仓库里没有 `.env` 或 `data/ecommerce.db`。项目的 `.gitignore` 已自动排除它们。

### 2. 在 Streamlit 建立应用

1. 打开 [Streamlit Community Cloud](https://share.streamlit.io/)，用 GitHub 账号登录。
2. 点 **Create app**，选择刚才的 GitHub 仓库。
3. Branch 选 `main`，入口文件填 `app.py`。
4. 可以填写一个可用的子域名，例如 `smart-ecommerce-demo`，然后点 **Deploy**。
5. 等待部署完成后，在应用的 **Share** 设置中将可见范围设为 **Public**。

完成后，Streamlit 会显示一个 `*.streamlit.app` 网址，把它发给别人即可访问。

## 启用 AI 问数

仅当你之后想启用 AI 问数时，才需要复制 `.env.example` 为 `.env` 并填写自己的 OpenAI API 密钥：

```env
OPENAI_API_KEY=你的_API_密钥
OPENAI_MODEL=gpt-5.5
```

重新启动应用后，智能洞察页会启用 AI 问数。系统先根据问题生成 SQLite `SELECT`，通过只读校验后在当前筛选结果构成的内存副本中执行，再让模型根据查询结果组织中文回答。查询被限制为 `orders` 表、白名单函数、最长执行时间和最多 100 行结果；原始订单号和客户编号不能被查询，只允许计算其去重数量。未配置密钥时，应用会使用本地规则问答。

OpenAI API 密钥需要单独申请和配置，API 调用会产生相应的用量费用。密钥只保存在本机 `.env` 文件中，该文件已加入 Git 忽略列表。

## CSV 字段

支持英文标准字段，也支持中文字段名：

| 字段 | 含义 |
| --- | --- |
| `order_id` | 订单编号 |
| `order_date` | 下单时间 |
| `customer_id` | 客户编号 |
| `product_name` | 商品名称 |
| `category` | 商品品类 |
| `quantity` | 购买数量 |
| `unit_price` | 商品单价 |
| `channel` | 销售渠道 |
| `region` | 地区 |

销售额按 `quantity × unit_price` 计算。上传订单会写入本机 SQLite 文件；数据库文件默认不纳入 Git。

## 项目亮点

- 使用 Streamlit 构建交互式经营分析应用，支持 CSV 导入 SQLite、日期和业务维度筛选及结果导出。
- 使用 Pandas 进行数据清洗、指标计算、时间序列聚合和 RFM 客户分层。
- 使用 Plotly 展示销售趋势、品类结构、渠道表现和地区排名。
- 使用 OpenAI Responses API 实现自然语言转只读 SQL，在隔离的 SQLite 内存副本执行，并依据查询结果生成中文回答；未配置 API 密钥时支持本地规则问答。
- 根据当前数据生成趋势、品类和渠道经营提示。

## 简历描述参考

**智能电商数据分析平台 | Python、Pandas、Streamlit、SQLite、OpenAI API**

独立设计并实现电商经营分析应用，支持订单 CSV 清洗与 SQLite 持久化，计算 GMV、订单量、成交客户数及客单价；构建多维经营看板与 RFM 客户分层，结合趋势规则生成经营提示；接入 OpenAI Responses API 实现自然语言转只读 SQL，通过 SQLite 查询白名单、执行超时和结果行数限制保障查询安全，并依据查询结果生成中文回答。支持筛选结果及客户分层导出。

## 后续可扩展

1. 将本地 SQLite 替换为 MySQL/PostgreSQL，补充定时 ETL 数据链路。
2. 增加退款、成本和广告支出字段，计算净销售额、毛利率、ROI 与转化率。
3. 增加用户鉴权、审计日志和 API 用量统计。
4. 增加 Docker 部署，完善为团队可演示版本。

> 自动经营洞察仍使用本地规则。AI 问数需配置 OpenAI API 密钥；生成的 SQL 只在当前筛选结果构造的内存副本上执行，不修改持久化订单库。

