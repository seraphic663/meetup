# 群约小助手

多人时间协调工具。参与者用连续时间条标记不方便和偏好时段，汇总结果直接对齐时间轴。

版本演进记录见 [docs/更新日志.md](docs/更新日志.md)。以后每次 GitHub 更新都需要同步维护这份文档。

**线上地址：** https://find-time.up.railway.app/

---

## 功能

- 创建时间调查表，生成分享链接
- AI 快速起草建表：一句话生成草稿，回填现有创建表单后由用户确认；AI 不可用时保留当前表单默认值并提示手动调整
- 创建后自动把发起人加入表格并进入填写页
- 发起人可设置提示语，所有参与者可见
- 支持首尾截断时间，跨天活动可设置首日开始和末日结束
- 参与者可拖动创建、移动和调整时间条，并为每段时间添加一条备注
- 时间粒度可设置为 5、10、15、20、30 或 60 分钟；普通参与者切换时保留已有时间，发起人可选择舍入
- 横向与竖向时间轴可切换，支持展开或折叠其他参与者
- 汇总按连续时间段展示：红带覆盖明确标记的不方便时间并集，绿带深浅表示明确偏好人数比例
- 创建者可修改整张表并维护参与者名单
- 创建者可标记关键成员，汇总和 AI 推荐会优先考虑关键成员约束
- 参与者可退出自己加入过的表格
- 热力图叠加，直观显示时段重合度
- AI 智能总结（优先 DeepSeek，未配置时自动降级为本地总结）
- 快速预览提供一张示例表，展示正式填写、汇总和横竖布局
- 参与者可保存适用于全部时间段的整体说明，其他持分享链接的人可查看
- 历史栏常驻展示：支持最近 5 条 localStorage 历史，也可粘贴旧分享链接或表格 ID 恢复打开旧表
- 使用教程引导
- 用户偏好（默认布局、默认折叠状态）
- 适配移动端与桌面端布局
- 前端模块化拆分（入口 / 状态 / API / 渲染 / 历史）
- 请求级日志、请求 ID 与统一 API 错误结构

---

## 3 分钟启动（本地）

**依赖：** Python 3.10+

```powershell
pip install -r requirements.txt

# 可选：仅在当前终端会话注入 API Key（不要写入代码文件）
$env:DEEPSEEK_API_KEY = "<YOUR_DEEPSEEK_API_KEY>"

# 可选：覆盖默认模型（默认即 deepseek-v4-flash）
$env:DEEPSEEK_MODEL = "deepseek-v4-flash"

python run.py
# 访问 http://localhost:5000
# 健康检查 http://localhost:5000/healthz
```

或直接执行：

```powershell
.\启动.ps1
```

> 安全建议：API Key 只放在平台环境变量（本地终端 / Railway Variables），不要写入仓库文件、脚本常量或提交记录。

可参考变量模板：`.env.example`（仅变量名示例，不含真实密钥）。

---

## 部署（Railway）

1. Fork 本仓库，在 Railway 新建项目连接 GitHub
2. 在服务的 **Variables** 标签页添加：
   - `DEEPSEEK_API_KEY` = 你的 DeepSeek API Key
   - `DEEPSEEK_MODEL` = `deepseek-v4-flash`（可选，默认已是这个值）
3. Railway 自动部署，用 `Procfile` 里的 gunicorn 命令启动；如果 Railway 服务里仍保留旧 Start Command `gunicorn server:app ...`，根目录 `server.py` 会兼容转发到 `backend.server:app`

数据存储在 SQLite（本地默认 `sessions/sessions.db`），当前表为 `sessions / session_expected_names / session_required_names / participants / time_intervals`。本次首次启动会清除旧排期数据并创建区间存储；参与者重新加入后，时间条保存在数据库中。Railway production 的 `web` 服务已将 `web-volume` 挂载到 `/app/sessions`，与后端默认数据库路径 `/app/sessions/sessions.db` 对齐，因此无需设置 `DB_PATH`。Volume 可让数据库跨 Railway 发布和重启保留；它不替代独立备份，备份与恢复步骤见 [docs/backup_restore.md](docs/backup_restore.md)。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | 原生 HTML / CSS / JS（响应式界面） |
| 后端 | Flask 3 + SQLite（多表存储） |
| AI | DeepSeek API (`deepseek-v4-flash`，可通过 `DEEPSEEK_MODEL` 覆盖) |
| 部署 | Railway + Gunicorn |
| CI | GitHub Actions |

---

## 文件结构

```
backend/               # Flask 后端实现（含 storage.py 存储层）
frontend/              # HTML / CSS 与前端模块
docs/                  # 项目文档
tests/                 # 接口冒烟测试
scripts/               # 安全扫描与辅助脚本
server.py              # Railway 旧 server:app 启动命令兼容入口
run.py                 # 本地启动脚本
启动.ps1               # Windows 启动脚本
Procfile               # Railway 部署配置
requirements.txt
sessions/              # SQLite 数据库目录（本地）
```

---

## 常见问题（FAQ）

### 1) AI 总结失败怎么办？
- 先确认 `DEEPSEEK_API_KEY` 已在当前环境注入。
- 如需切换模型，确认 `DEEPSEEK_MODEL` 填写的是平台支持的模型名。
- 未注入或调用失败时，会自动返回本地总结，核心排期功能仍可正常使用。

### 2) 为什么不能把 API Key 写在项目里？
- 仓库、日志、截图和历史提交都可能泄露密钥。
- 推荐使用系统环境变量或部署平台密钥管理。

### 3) 部署后如何判断服务正常？
- 访问 `/healthz`，返回 `{"ok": true, ...}` 即代表服务可用。

---

## 发布前检查（门禁）

1. 执行 API 冒烟测试

```powershell
python -m unittest tests/test_api_smoke.py -v
```

2. 验证服务探活
   - 启动后访问 `/healthz`，返回 `200` 且 `ok=true`

3. 验证环境变量
   - `DEEPSEEK_API_KEY` 已配置（本地/部署平台）
   - 如需覆盖默认模型，`DEEPSEEK_MODEL` 已配置为有效模型名

4. 手测关键链路（至少 1 次）
   - 创建会话
   - AI 起草草稿并人工确认创建（可在无 API Key 时验证保留默认值的本地回退）
   - 加入会话
   - 填写可用性，输入个人备注后点击“保存并公开”
   - 确认已公开备注能被其他访问者看到，且备注本人可以修改
   - 创建者管理参与者与关键成员
   - 查看总结（含 AI / 无 AI 两种情况至少其一）

5. 执行安全扫描

```powershell
python scripts/security_guard.py --workspace --history
```

6. 备份数据库
   - 参考 [docs/backup_restore.md](docs/backup_restore.md)

---

## 安全收口（A）

已落地：
- 仅通过环境变量读取 `DEEPSEEK_API_KEY`（不在代码中硬编码）
- AI 模型名统一通过 `DEEPSEEK_MODEL` 配置，默认使用 `deepseek-v4-flash`
- 提供本地扫描脚本：`scripts/security_guard.py`
- 提供应急与历史治理文档：`docs/安全收口执行清单.md`
- 提供提交前防护：`.githooks/pre-commit`
- 提供 CI 基线：`.github/workflows/ci.yml`
- 提供备份恢复 SOP：`docs/backup_restore.md`

建议先安装提交前钩子：

```powershell
./scripts/install_git_hooks.ps1
```

建议每次发布前执行：

```powershell
python scripts/security_guard.py --workspace --history
```

若扫描发现历史泄露，按执行清单完成：密钥轮换、历史清理、协作者同步。
