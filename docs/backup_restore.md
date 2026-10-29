# 群约小助手｜SQLite 备份与恢复 SOP

建立日期：2026-03-29 · Railway Volume 更新：2026-10-29
适用范围：当前仓库默认数据存储 `sessions/sessions.db`

说明：当前 SQLite 库按业务拆为多张表（`sessions / session_expected_names / session_required_names / participants / time_intervals`），备份与恢复仍然按单个 `.db` 文件处理。

---

## 1. 目标

本 SOP 用于处理以下场景：

- 发布前手工备份
- 数据异常后的快速恢复
- Railway 挂载 Volume 后的持久化数据管理

原则：

- **直接复制数据库文件前先停止写入；在线备份使用 SQLite Backup API，避免复制正在写入的文件**
- **先备份当前库，再做恢复覆盖**
- **恢复后必须做可读性验证**

---

## 2. 默认数据位置

本地默认相对路径：

```text
sessions/sessions.db
```

如果部署环境配置了 `DB_PATH`，以该环境变量为准。

Railway production 的 `web` 服务当前使用 `web-volume`，挂载点为 `/app/sessions`。后端默认数据库路径会解析为 `/app/sessions/sessions.db`，因此该环境不需要额外设置 `DB_PATH`；若更改挂载点或数据库路径，必须确保 `DB_PATH` 仍指向 Volume 内的文件。Volume 用于跨发布和重启持久化，不是独立备份。

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
- 创建、修改并保存一段时间条

如果验证失败：

- 立即停止服务
- 用 `before_restore_*.db` 回滚

---

## 6. Railway 场景说明

当前 Railway production 已完成以下持久化配置：

- `web-volume` 挂载到 `/app/sessions`
- 数据库位于 `/app/sessions/sessions.db`，与后端默认路径一致
- 不需要设置 `DB_PATH`；若自定义数据库位置，必须放在挂载的 Volume 内

备份和恢复仍需单独执行，Volume 本身不能替代备份。操作时：

1. 备份时停止写入，或使用 Python `sqlite3.Connection.backup()` 创建一致快照；不要在服务仍写入时直接复制或下载活动数据库文件。
2. 恢复前先为当前 Volume 数据库留一份独立快照，再在停止写入的维护窗口将备份恢复到 `/app/sessions/sessions.db`。
3. 重启 Railway 服务后检查 `/healthz`，并通过一个已知会话的 API 或页面确认参与者和可用时间仍可读取。

Railway CLI 的 `railway volume files` 可用于管理 Volume 文件。上传恢复文件时必须确认选中 production 的 `web-volume`，并避免在应用继续写入数据库时覆盖目标文件。

### 1.7.0 时间区间存储迁移

首次启动新版时，若 `PRAGMA user_version` 低于 1，应用会一次性清除旧排期数据（旧会话、参与者、令牌、个人整体说明和逐小时状态），并创建时间条存储表。此清理是有意的数据重置；后续启动不会重复执行。Railway Volume 与数据库文件继续保留，重置后可立即创建新表。

发布前应按本 SOP 留存一次在线 SQLite 快照。不要把旧数据库快照直接恢复给 1.7.0 及之后的代码：低版本数据库会再次触发重置；如确需查看旧快照，应与兼容旧 schema 的旧应用版本配合使用。

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
