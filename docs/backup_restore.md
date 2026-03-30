# 群约小助手｜SQLite 备份与恢复 SOP

日期：2026-03-29  
适用范围：当前仓库默认数据存储 `sessions/sessions.db`

---

## 1. 目标

本 SOP 用于处理以下场景：

- 发布前手工备份
- 数据异常后的快速恢复
- Railway 挂载 Volume 后的持久化数据管理

原则：

- **先停服务，再复制数据库**
- **先备份当前库，再做恢复覆盖**
- **恢复后必须做可读性验证**

---

## 2. 默认数据位置

本地默认路径：

```text
sessions/sessions.db
```

如果部署环境配置了 `DB_PATH`，以该环境变量为准。

---

## 3. 备份前检查

执行备份前先确认：

1. 当前服务已停止写入，避免复制过程中产生不一致数据
2. 已确认本次备份目标目录存在
3. 已记录备份时间、操作人、备份原因

建议备份目录：

```text
backups/
```

---

## 4. 本地备份步骤

## 4.1 Windows PowerShell

1. 停止本地服务
2. 执行：

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item sessions\sessions.db "backups\sessions_$ts.db"
```

3. 校验备份文件已生成：

```powershell
Get-ChildItem backups
```

## 4.2 备份验收

满足以下条件才算备份成功：

- `backups/` 下出现新的 `.db` 文件
- 备份文件大小大于 0
- 文件时间与当前操作时间一致

---

## 5. 本地恢复步骤

## 5.1 恢复前动作

恢复前必须先做一次“当前库临时备份”，避免误恢复后无法回退。

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item sessions\sessions.db "backups\before_restore_$ts.db"
```

## 5.2 执行恢复

假设目标恢复文件为 `backups\sessions_20260329_210000.db`：

```powershell
Copy-Item backups\sessions_20260329_210000.db sessions\sessions.db -Force
```

## 5.3 恢复后验证

1. 启动服务
2. 检查探活：

```text
GET /healthz
```

3. 手工验证：

- 打开一个已知存在的调查链接
- 确认参与者和时段数据可读取
- 随机修改一条可用性数据并确认可保存

如果验证失败：

- 立即停止服务
- 用 `before_restore_*.db` 回滚

---

## 6. Railway 场景说明

如果线上仍使用临时文件系统，重启后 SQLite 数据会丢失。  
要把 SQLite 用在 Railway 上，至少满足两个条件：

1. 已挂载持久化 Volume
2. `DB_PATH` 指向该 Volume 内的数据库文件

建议流程：

- 发布前先在 Volume 内复制一份数据库备份
- 恢复时先停止服务，再用备份文件覆盖当前数据库
- 恢复后先跑 `/healthz`，再做一次真实页面验证

如果后续线上并发或数据重要性继续提高，应评估迁移到 PostgreSQL，而不是继续放大 SQLite 的运维负担。

---

## 7. 建议备份频率

当前项目建议最小频率：

- 线上每次发布前：1 次
- 线上每次结构性改动前：1 次
- 本地做清库、手工调试、数据迁移前：1 次

如果开始有真实持续用户，建议提升为：

- 每日固定备份
- 发布前额外备份

---

## 8. 演练记录模板

建议每次恢复演练都记录：

```text
时间：
操作人：
环境：本地 / Railway
备份文件：
恢复目标：
验证结果：
是否回滚：
备注：
```

---

## 9. 最低验收标准

P0 完成标准不是“文档存在”，而是以下三点都成立：

- 可以按文档完成一次本地备份
- 可以按文档完成一次本地恢复
- 恢复后能通过 `/healthz` 和一次真实页面验证
