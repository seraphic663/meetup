# 群约小助手

多人时间协调工具。创建一张时间表，参与者各自填写有空 / 没空，一眼看出最优时段。

**线上地址：** https://web-production-3853a.up.railway.app

---

## 功能

- 创建时间调查表，生成分享链接
- 参与者点格子填写可用时间（有空 / 没空 / 未填）
- 热力图叠加，直观显示时段重合度
- AI 智能总结（DeepSeek），给出最优时段建议
- 历史记录（localStorage，最近 5 条）
- 使用教程引导

---

## 本地运行

**依赖：** Python 3.10+

```powershell
pip install flask gunicorn requests

# 设置 AI Key（可选，不设置则 AI 总结不可用）
$env:DEEPSEEK_API_KEY = "sk-xxxx"

python run.py
# 访问 http://localhost:5000
```

或使用交互式启动脚本（会提示输入 API Key）：

```powershell
.\启动.ps1
```

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
| 前端 | 原生 HTML / CSS / JS，单文件 |
| 后端 | Flask 3 + SQLite |
| AI | DeepSeek API (`deepseek-chat`) |
| 部署 | Railway + Gunicorn |

---

## 文件结构

```
server.py        # Flask 后端
index.html       # 前端（单文件）
run.py           # 本地启动脚本
启动.ps1         # Windows 交互式启动
Procfile         # Railway 部署配置
requirements.txt
sessions/        # SQLite 数据库目录（本地）
```
