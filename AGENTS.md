# AGENTS

本文件用于指导在本仓库中协作的 ChatGPT / Codex 类代理，避免过度设计，优先交付可验证、可维护的改动。

## 核心原则

1. 先做最小可用，不做“顺手补完整平台”。
2. 优先复用现有页面、现有接口、现有状态结构，不为单一功能重建一套体系。
3. 如果一个需求可以靠“一个新接口 + 现有表单回填”完成，就不要扩成“完整 DSL / 工作流引擎 / 配置系统”。
4. 默认让用户确认关键结果，不要让 AI 直接替用户落库、发起流程或修改核心数据。
5. 如果新增复杂度主要是为了覆盖极少数输入表达、未来可能需求或想象中的扩展点，先不要做。

## 设计边界

### 后端

- 优先增加薄接口，不要在单次迭代里引入多层 service / repository / parser framework。
- 能用清晰的函数解决，就不要抽象出过多对象层级。
- 优先保证失败可回退，而不是追求一次性“全自动理解”。
- 如果规则解析已经明显变长，优先停在“够用”，不要继续堆更多语法分支。

### 前端

- 优先把新能力接入现有表单和现有提交流程。
- 不要为了一个新卡片、新弹层就引入新的全局状态模型或 UI 框架层。
- 如果功能只是辅助创建，优先“填回现有表单”，不要做第二套平行创建流。

### AI 功能

- AI 默认输出草稿，不直接执行最终动作。
- 必须提供人工审核入口。
- 必须允许回退到非 AI 路径。
- 不要为了“更聪明”而先写大段本地拟 NLP 系统，除非这是当前需求不可回避的核心。

## 过度设计识别清单

出现以下信号时，应优先判断为可能过度设计：

- 为一个新功能同时新增多套状态源、多个真值来源
- 单个文件因一个功能增长出大段解析、协调、兜底逻辑
- 为未来扩展预先设计过多抽象，但当前只有一个调用方
- 为覆盖少量边缘表达写出大量规则分支
- 已有人工确认环节，却仍试图把自动化做成“完全自治”

## 推荐做法

- 先实现最短主链路
- 先补最关键的接口测试
- 明确哪些复杂度是“当前业务必要”，哪些只是“想得太远”
- 在提交说明或报告里直接指出新增复杂度的成本

## 更新注意事项

- 每次修改功能、交互、后端接口、数据结构、部署方式、安全基线、测试基线或重要文档时，都要同步检查并按需更新：
  - `README.md`：对外功能、启动、部署、发布前检查是否仍准确。
  - `docs/更新日志.md`：版本总览和对应版本详情必须同时更新。
  - `frontend/static/js/constants.js`：如果首页更新日志要展示该版本，`CHANGELOG_ITEMS` 必须同步。
  - `docs/backup_restore.md`：涉及数据库、存储路径、备份恢复方式时必须同步。
  - `docs/数据库重构方案.md`：涉及存储结构、迁移策略或表结构时必须同步。
  - `docs/创建UI.md`：涉及创建页、AI 起草、表单结构或主要交互时必须同步。
  - `docs/过度设计审查报告.md`：涉及复杂度收口、兜底策略、AI 规则或架构边界时必须同步。
- 版本号采用 `a.x.y`：
  - `a`：产品代际主版本，除非项目定位发生大变化，否则不要轻易增加。
  - `x`：产品阶段跃迁，例如核心流程、数据结构、重要 UI/交互体系发生明显变化。
  - `y`：同一阶段内的连续增强、修复、文档整理或安全收口。
- 新版本编号必须以前一条版本为基准递增，不要回插到旧版本之后；如果只是未提交的工作区更新，对应提交可暂写 `当前工作区`。
- 版本名要概括核心变化，不要写成泛泛的“优化版”“更新版”。
- 同一轮改动里如果只改文档，不需要强行升版本；如果文档是在记录已发生的功能/架构变化，应补齐版本记录。
- 更新记录要写“用户可感知或维护者必须知道的变化”，不要把每个微小代码移动都写成版本升级点。
- 如果新增测试或改变发布门禁，必须同步 README 的发布前检查。
- 如果发现版本记录、首页展示和实际代码状态不一致，优先修正记录，不要为同步记录额外重构业务代码。

## 禁止倾向

- 不要把简单需求包装成“平台化升级”
- 不要无证据地为未来需求预埋大框架
- 不要把 AI 辅助功能做成不可审查的黑箱流程
- 不要在没有用户要求时做大规模重构

## 当前项目事实

### 运行与部署

- 当前主线分支是 `master`，远端 `origin/HEAD` 指向 `origin/master`。除非用户明确要求，不要另建 `main` 分支。
- Railway 推荐入口是 `Procfile` 中的 `gunicorn backend.server:app ...`。
- 根目录 `server.py` 是兼容入口，只为旧 Railway Start Command `gunicorn server:app ...` 转发到 `backend.server:app`。不要把它扩展成第二套应用入口。
- 本地启动用 `python run.py` 或 `.\启动.ps1`，默认访问 `http://localhost:5000`。
- SQLite 默认路径是 `sessions/sessions.db`。`sessions/` 是运行数据目录，已被忽略；不要在没有用户明确要求时删除数据库。
- Railway 未挂载 Volume 时重启会丢失 SQLite 数据。涉及持久化时优先看 `docs/backup_restore.md` 和 `DB_PATH`。

### 后端结构

- 主后端在 `backend/server.py`，负责 Flask app、API、鉴权、摘要、静态资源路由。
- 存储层在 `backend/storage.py`，当前是多表 SQLite：`sessions / session_expected_names / session_required_names / participants / time_intervals`。1.7.0 首次启动时会按授权重置旧排期数据；后续通过 `PRAGMA user_version` 避免重复清理。
- AI 创建草稿逻辑在 `backend/create_draft.py`。AI 不可用时只返回 defaults 和说明，不再写复杂本地 NLP 规则。
- 当前接口主链路包括：创建会话、AI 草稿、读取会话、加入、保存个人时间条与整体说明、管理整表、删除整表、删除参与者、AI 总结、健康检查。

### 前端结构

- 前端是原生 HTML / CSS / ES modules，不引入框架。
- `frontend/index.html` 定义全部页面骨架。
- `frontend/static/js/app.js` 仍是最大协调文件，包含页面切换、创建、加入、填写、拖拽、轮询、弹窗、删除/退出、分享等。它是当前最大技术债，后续拆分要小步做。
- `frontend/static/js/render.js` 负责历史栏、更新日志、加入页、参与者徽标与说明渲染。
- `frontend/static/js/timeline.js` 负责唯一的时间轴填写、横竖布局、折叠状态、连续区间汇总和时间条保存。
- `frontend/static/js/history.js` 负责 localStorage 历史和访问令牌缓存。
- `frontend/styles.css` 已整理为 v2 分区样式，紧凑 UI 已合并进对应模块规则。不要再在末尾追加大块覆盖层。

## 已遭遇问题与当前决策

### Railway 启动入口不一致

遭遇情况：Railway 服务仍使用旧的 `server:app` 启动命令，而项目真实入口已在 `backend.server:app`。

当前处理：

- 保留根目录 `server.py` 作为兼容转发。
- README 说明推荐 `Procfile`，同时说明旧 Start Command 的兼容逻辑。
- 后续不要删除根目录 `server.py`，除非确认 Railway 配置已经全部切换且用户同意移除兼容。

### 旧表恢复与历史记录

遭遇情况：

- 用户发现“恢复旧表”能力消失。
- localStorage 为空时首页原先可能不展示最近表格入口。
- 过期或不存在的表格打开后，需要提示并允许在首页清理本地记录。

当前处理：

- 首页保留常驻“历史栏”，即使没有任何旧表或最近记录也必须展示。
- 历史栏上半部支持粘贴旧分享链接或表格 ID 打开旧表。
- 历史栏下半部展示 localStorage 最近记录，空时展示空状态，不隐藏整块历史栏。
- 首页“删除”只移除本地最近记录，不删除远端整表。
- 远端整表删除必须走创建者 token，入口是 `deleteCurrentSession` / `deleteSessionFromHistory`。

后续注意：

- 不要把“恢复旧表”和“最近表格”重新拆成两个相邻卡片，除非有明确的新信息架构理由。
- 不要因为没有历史记录就隐藏历史栏。
- 修改历史栏时同步 `docs/创建UI.md`、`docs/更新日志.md` 和 `frontend/static/js/constants.js`。

### CSS 紧凑与冗余收口

遭遇情况：

- 用户要求 UI “相当紧凑”。
- 曾比较过仓库内 CSS 和 `C:\Users\31572\Downloads\styles.v2.safe-refactor.css`。
- 下载版 v2 更适合继续维护，因为它把紧凑覆盖层合并进分区规则。

当前处理：

- 仓库采用 v2 分区样式，并额外删除无用的 `.site-orb` 隐藏规则和对应 DOM。
- CSS 不再依赖“最后追加一大层覆盖”的方式维护密度。
- 当前视觉方向是高密度、少留白、卡片圆角小、工具栏和时间轴紧凑；旧逐小时格子主流程及其保存接口已移除。

后续注意：

- 调紧凑度时先改对应分区规则，不要在文件末尾继续堆 `!important` 覆盖。
- 删除样式前先搜索 HTML 和 JS 生成模板，避免误删动态类。
- 如果继续精简，优先统一重复模板和状态样式，而不是重做设计系统。

### Git 历史和提交消息

遭遇情况：

- 用户要求最近几次 commit message 改成中文。
- 其中两个英文 commit 已经存在于 `origin/master`。
- 后续又要求“提交本轮commit作为main”，但远端实际没有 `main`，只有 `master`。

当前处理：

- 最近主线提交已改为中文：
  - `精简紧凑 UI 并常驻历史栏`
  - `对齐 Railway 生产地址`
  - `修复 Railway 旧入口兼容`
- 远端主线仍是 `master`，已用 `--force-with-lease` 更新过，当前本地和远端一致。

后续注意：

- 不要假设存在 `main`。先看 `git branch -vv --all` 和 `git remote -v`。
- 如果用户说“main”，结合本仓库语境通常应理解为“主线”，即当前 `master`。
- 改写已推送历史时只能在明确需要时做，并优先用 `--force-with-lease`，不要普通 `--force`。
- 提交消息优先中文，概括用户可感知变化，不写泛泛的“update/fix”。

### 安全扫描与历史密钥

遭遇情况：

- `python scripts/security_guard.py --workspace` 通过。
- `python scripts/security_guard.py --workspace --history` 会因旧 git 历史中的 DeepSeek key 记录失败。

当前判断：

- 当前工作区没有密钥泄露。
- 历史扫描失败是旧提交问题，不是当前文件问题。

后续注意：

- 不要把真实 API Key 写进代码、文档、脚本、日志或提交消息。
- 本地和部署平台都只通过环境变量配置 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL`。
- 如果要真正解决历史扫描，需要单独做密钥轮换和 git 历史清理；这不是普通功能改动的一部分。

### 日志与运行数据

遭遇情况：

- 用户提供过 `logs.1783529951777.log` 并提到 Railway SSH。
- 工作区存在 `sessions/` 和测试生成的 `__pycache__`。

当前处理：

- `sessions/` 保留为运行数据，不随便删。
- `__pycache__` 可以在测试后清理，但必须确认路径在仓库内。

后续注意：

- 查运行问题时先看真实日志和当前服务状态，不要只凭猜测。
- 删除运行产物前区分：缓存可删，数据库默认不删。

## 常用验证命令

修改后按改动范围选择验证，不要机械全跑但要覆盖风险：

```powershell
node --check frontend\static\js\app.js
node --check frontend\static\js\render.js
node --check frontend\static\js\constants.js
python -m py_compile backend\server.py backend\create_draft.py backend\storage.py run.py server.py
python -m unittest tests/test_api_smoke.py -v
python scripts\security_guard.py --workspace
git diff --check
```

如果本地服务正在运行，可补充：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/healthz
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/styles.css
```

检查首页历史栏时，至少确认：

- 首页 HTML 包含“历史栏”。
- 不再出现 `hc-restore`。
- `historyCard` 不带 `hidden`。
- 空历史时仍有 `.history-mini-empty` 空状态。

## 修改优先级

### 可以继续小步精简

- 抽出 `render.js` 中重复的 HTML 小模板。
- 收口 `app.js` 中删除/退出、管理弹窗、分享弹窗等相关函数。
- 逐步减少静态 HTML 和动态模板里的内联 `style`。
- 补少量针对历史栏空状态、旧链接解析、失效记录清理的前端轻量测试或手动检查脚本。

### 暂时不要做

- 不要引入 React/Vue/Tailwind/Bootstrap。
- 不要把 AI 起草重新做成本地复杂 NLP 解析器。
- 不要把当前 Flask app 拆成多层 service/repository 框架。
- 不要为历史栏建立第二套远端“表格索引”系统。
- 不要为了“恢复旧表”开放无 token 删除远端整表。

## 交给下一个 AI 的复盘任务

请下一个接手本仓库的 AI 重新审视本轮遭遇的实际问题，并提出可行解决措施。复盘必须覆盖以下情况：

1. Railway 旧 Start Command 使用 `server:app`，而推荐入口是 `backend.server:app`。评估继续保留兼容入口、迁移 Railway 配置、以及未来移除兼容的条件。
2. 首页曾把“恢复旧表”和“最近表格”拆成两个相邻卡片，造成表达重复；现在已合并为常驻历史栏。评估这个信息架构是否还可以更精简，同时必须保证没有旧表时也展示历史栏。
3. 过期或不存在的表格打开后，需要回首页提示并允许删除本地记录。评估提示文案、错误状态、历史清理入口是否足够明确。
4. CSS 曾存在覆盖层堆叠和无用装饰 DOM。评估现有 v2 分区 CSS 是否还有重复选择器、内联样式、无用类、过度 `!important`。
5. `frontend/static/js/app.js` 仍然过长。评估第一刀应拆哪里，优先考虑不改变行为的模板复用、session actions、manage dialog、share dialog。
6. 最近提交消息已改中文并 force-with-lease 更新远端 `master`。评估之后的协作风险：其他人如果基于旧 `origin/master` 工作，应如何同步。
7. 工作区扫描通过但历史扫描会抓到旧 DeepSeek key。评估是否需要单独安排密钥轮换和 git 历史清理，并说明这和普通功能提交的边界。
8. 文档同步容易遗漏。评估 README、更新日志、首页 `CHANGELOG_ITEMS`、创建 UI 文档、过度设计审查报告之间的最小同步规则。

复盘输出要求：

- 先列风险和证据，再列建议。
- 每条建议必须说明成本、收益、是否需要用户确认。
- 只提出当前仓库能落地的措施，不要设计平台化重构。
- 如果要改代码，先选择一个最小闭环，不要同时拆多个模块。
