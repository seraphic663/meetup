# 群约小助手

多人时间协调工具。创建一张时间表，参与者各自填写有空 / 没空，一眼看出最优时段。

**线上地址：** https://web-production-3853a.up.railway.app

---

## 功能

- 创建时间调查表，生成分享链接
- 发起人可设置提示语，所有参与者可见
- 参与者点格子填写可用时间（有空 / 没空 / 未填）
- 热力图叠加，直观显示时段重合度
- AI 智能总结（DeepSeek），给出最优时段建议
- 历史记录（localStorage，最近 5 条）
- 使用教程引导

---

## 3 分钟启动（本地）

**依赖：** Python 3.10+

```powershell
pip install -r requirements.txt

# 可选：仅在当前终端会话注入 API Key（不要写入代码文件）
$env:DEEPSEEK_API_KEY = "<YOUR_DEEPSEEK_API_KEY>"

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
3. Railway 自动部署，用 `Procfile` 里的 gunicorn 命令启动

数据存储在 SQLite（`sessions/sessions.db`），Railway 重启后数据会丢失，如需持久化需挂载 Volume 并设置 `DB_PATH` 环境变量。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | 原生 HTML / CSS / JS（已拆分） |
| 后端 | Flask 3 + SQLite |
| AI | DeepSeek API (`deepseek-chat`) |
| 部署 | Railway + Gunicorn |

---

## 文件结构

```
server.py        # Flask 后端
index.html       # 页面结构
styles.css       # 样式
app.js           # 交互逻辑
run.py           # 本地启动脚本
启动.ps1         # Windows 启动脚本
Procfile         # Railway 部署配置
requirements.txt
sessions/        # SQLite 数据库目录（本地）
```

---

## 常见问题（FAQ）

### 1) AI 总结失败怎么办？
- 先确认 `DEEPSEEK_API_KEY` 已在当前环境注入。
- 未注入时，核心排期功能仍可正常使用。

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

4. 手测关键链路（至少 1 次）
   - 创建会话
   - 加入会话
   - 填写可用性 + 备注
   - 查看总结（含 AI / 无 AI 两种情况至少其一）

5. 执行安全扫描

```powershell
python scripts/security_guard.py --workspace --history
```

---

## 安全收口（A）

已落地：
- 仅通过环境变量读取 `DEEPSEEK_API_KEY`（不在代码中硬编码）
- 提供本地扫描脚本：`scripts/security_guard.py`
- 提供应急与历史治理文档：`docs/安全收口执行清单_2026-03-19.md`
- 提供提交前防护：`.githooks/pre-commit`

建议先安装提交前钩子：

```powershell
./scripts/install_git_hooks.ps1
```

建议每次发布前执行：

```powershell
python scripts/security_guard.py --workspace --history
```

若扫描发现历史泄露，按执行清单完成：密钥轮换、历史清理、协作者同步。
