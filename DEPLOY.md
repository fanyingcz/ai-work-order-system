# 部署说明（智能工单系统）

> 2026-09-07 由砚整理。目标是拿到一个**能点开的 live demo URL**，
> 贴进冷邮件、Contra 主页、Upwork profile。

---

## 一、本次改了什么

| 文件 | 改动 | 原因 |
|---|---|---|
| `db/database.py` | 连接参数改为**环境变量优先**（`DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME`） | 原密码硬编码在代码里两处，推 GitHub = 泄露 |
| `api.py` | 1) 启动时 `load_dotenv()`<br>2) 挂载两个前端静态目录<br>3) SPA 深链接回退<br>4) 规则表为空时自动导入 `data/rules` | 单容器同时提供前后端；新库不再是空壳 |
| `requirements.txt` | 去除 BOM；新增 `python-dotenv`、`cryptography` | 原文件有 BOM，云端 pip 可能解析失败；PyMySQL 连 MySQL 8 需要 cryptography |
| 新增 `.env` / `.env.example` | 本地配置与脱敏模板 | `.env` 已进 `.gitignore` |
| 新增 `Dockerfile` | 单容器：FastAPI + 两个已构建前端 | 前端 dist 已在仓库，镜像无需 Node |
| 新增 `docker-compose.yml` | app + MySQL 8.0 | 本地一键起全栈 |
| 新增 `.dockerignore` / `.gitignore` | 排除 node_modules、`__pycache__`、`.env` | 镜像体积与安全 |
| `frontend/.gitignore`、`worker-frontend/.gitignore` | 去掉 `dist` 规则 | Vite 生成的子目录规则优先级高于根目录，不去掉的话构建产物根本进不了仓库，线上会只剩 API |
| `tools/init_workers.py` | 改写为 `ensure_workers()` 函数，可被启动流程调用 | 原来只能手工跑脚本建 workers 表 |
| `api.py` | 启动时补齐 `error_feedbacks` 与 `workers` 两张表 | 云端全新库缺这两张表，统计页和派单会直接 500 |

**路由**（同域，前端用相对路径 `/api/v1`，所以前端代码一行未改）：

| 路径 | 内容 |
|---|---|
| `/` | 报修端 / 管理端（`frontend/dist`） |
| `/worker` | 工人端（`worker-frontend/dist`） |
| `/api/v1` | 接口 |
| `/docs` | Swagger |

---

## 二、环境变量

| 变量 | 本地默认 | 说明 |
|---|---|---|
| `DB_HOST` | `localhost` | 容器内为 `db` |
| `DB_PORT` | `3306` | |
| `DB_USER` | `root` | |
| `DB_PASSWORD` | 空 | **必填**，本地值已写入 `.env` |
| `DB_NAME` | `AI_Work_Order` | |
| `DB_SSL` | 空 | 填 `1` 启用 TLS（TiDB Cloud 必填）；本地 MySQL 留空 |
| `DB_SSL_CA` | 空 | 指定 CA 证书路径，一般不用 |
| `ds_apikey` | 空 | DeepSeek API Key，原来就从环境变量读 |

---

## 三、三种跑法

### 跑法 A：本地无 Docker（你现在就能验证）

```bash
cd smart-workorder-system        # 即本仓库根目录
pip install -r requirements.txt      # 你的环境里应该已装大部分
python api.py
# 打开 http://localhost:8000         （报修端）
#      http://localhost:8000/worker  （工人端）
#      http://localhost:8000/docs
```

⚠️ 数据库密码现在从 `.env` 读——如果启动时连不上库，检查 `.env` 是否在、
`DB_PASSWORD` 是否正确（原来硬编码的那个值已经写进去了）。

### 跑法 B：本地 Docker（推荐，最贴近云端）

需先装 **Docker Desktop**（<https://www.docker.com/products/docker-desktop/>）：

```bash
docker compose up --build
```

- 宿主 MySQL 端口映射为 **3307**，避免和你本机已装的 MySQL 抢 3306
- 首次启动会自动建表并导入 `data/rules` 的规则数据
- 应用端口 8000

### 跑法 C：云端（拿公网 URL，真正用于 demo）

云端平台从 GitHub 构建，**不需要你本地有 Docker**：

1. `git init` 并把本项目推成 GitHub 仓库（建议 **Private**，理由见第六节）
2. 在 **Render** 或 **Railway** 新建服务，选这个仓库
3. 加一个 MySQL（Render 没有托管 MySQL，用外部；Railway 有原生 MySQL 8）
4. 在服务环境变量里填 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME/ds_apikey`，
   用 TiDB 时还要填 `DB_SSL=1`
5. 构建命令默认读 `Dockerfile`，端口 8000

#### 平台与数据库选型（2026-09-07 核实自官方定价页 / 官方文档）

| 方案 | 月成本 | 优点 | 风险 |
|---|---|---|---|
| **Railway**（推荐）<br>Web + 原生 MySQL 8 | 约 **US$5–10**<br>Hobby $5 含等额用量 | 真 MySQL 8，本项目 DDL（外键 / InnoDB / utf8mb4_unicode_ci）**零兼容风险** | 要绑卡；用量计费 |
| Render Starter + TiDB Cloud Starter 免费库 | **US$7** | 常驻不休眠 | TiDB 兼容性**未实测**：外键、`ENGINE=InnoDB`、utf8mb4_unicode_ci 三项我不敢打包票 |
| Render Free + TiDB 免费库 | **US$0** | 一分钱不花 | 15 分钟休眠，冷启动 30–60 秒——招聘方点开要干等，观感差 |

数据源：render.com/pricing（官方，Web 服务 Free/Starter $7、数据库**仅 Postgres 与 Key Value，无 MySQL**）；
TiDB 官方文档（Starter 免费档 5 GiB + 50M RU/月，免卡，**强制 TLS**，端口 4000，用户名带 `xxxxxxxx.` 前缀）；
Railway 免费额度多方口径不一（$1–$5/月），已按保守的 $5 计。

> **我的判断**：demo 是用来争取面试的，打不开或转圈一分钟比每月多花 HK$55 贵得多。
> 建议 Railway，或 Render Starter + TiDB。纯免费档只适合自己先验证，不适合贴进邮件。

---

## 四、上线前必做的安全检查

- [ ] 确认 `.env` **没有**被提交（`git status` 里看不到它）
- [ ] `git grep -n -i "password\s*=\s*[\"'][^\"']"` 应无结果（代码中无硬编码密码）
- [ ] `ds_apikey` 只存在于平台的环境变量面板，不在代码里
- [ ] 两个 `dist/` 已提交（Docker 构建不装 Node，缺了会退化成纯 API）

---

## 五、实测结果（2026-09-07，本机 uvicorn 真跑，非静态审查）

| 路径 | 结果 | 说明 |
|---|---|---|
| `/` | 200 | 主端 index.html |
| `/worker` | **307 → /worker/** | 工人端入口，补尾斜杠 |
| `/worker/`、`/worker/orders` | 200 | history 深链接正常 |
| `/orders`、`/nonexist` | 200 | 主端 SPA 回退正常 |
| `/docs` | 200 | Swagger |
| `/assets/index-C4zCJJ-g.js`（主端） | 200 | |
| `/assets/index-DppasFQI.js`（工人端） | 200 | 与主端无重名，合并查找可行 |
| `/api/v1/health` | 200 | `{"status":"running","version":"2.0.0"}` |
| `/api/v1/categories` | 200 | 规则数据真的读出来了 |
| `/api/v1/stats` | 200 | 21 条工单，说明 DB 链路通 |

**踩过的坑（已修，勿回退）**：最初用 `app.mount("/", StaticFiles(...))` 托管前端，
结果根挂载会把**所有**未命中路径吞掉并返回 404 —— `/worker` 报 404、
history 深链接也全 404。改成"先查真实静态文件 → 再按前缀回退 index.html"的
单条 catch-all 路由才对。

---

## 六、上线前必做的安全检查

- [ ] 确认 `.env` **没有**被提交（`git status` 里看不到它）
- [ ] `git grep -n -i "password\s*=\s*[\"'][^\"']"` 应无结果（代码中无硬编码密码）
- [ ] `ds_apikey` 只存在于平台的环境变量面板，不在代码里
- [ ] 两个 `dist/` 已提交（Docker 构建不装 Node，缺了会退化成纯 API）

> 本仓库是**已脱敏**版本，可安全公开：地址、电话、工人名均为合成值，
> 报修描述里内嵌的地址也已重写（详见 README 的 Sample data 一节）。
> 真实业务数据在另一份未公开的工程副本里，**不要**把那份推上来。

### 仍需你出面的事（我做不了）

1. **平台账号**：Railway / Render 注册 + 绑卡（Hobby 档 US$5–7/月）
2. **MySQL 实例**：建好后把主机/端口/用户名/密码给我，我写进环境变量
3. **DeepSeek Key**：`ds_apikey`，没有的话 demo 的 AI 分类会失败
4. **推送**：若本机 git 凭据过期，需要一个有 `repo` 权限的 GitHub PAT

## 七、已知限制（我的判断，未逐条实测）

1. **镜像从未真正构建过**——你这台机器没有 Docker。Dockerfile 只做了静态审查，
   依赖清单与本地实测运行是通的，但 `docker build` 首次跑仍可能有环境差异。
2. **TiDB 兼容性未验证**——外键与 `ENGINE=InnoDB` 在 TiDB 上的行为我没实测过，
   选这条路线要预留一轮返工。Railway 原生 MySQL 8 则无此风险。
3. **规则自举依赖 `init_rules_from_json`**——我只在规则表为空时调用它，
   若库里已有数据则跳过，不会覆盖现有规则。云端新库会自动灌入 `data/rules`。
4. **本地 21 条工单不会上云**——新库是空的，demo 里只有规则数据。这是好事：
   真实报修内容不对外暴露。
