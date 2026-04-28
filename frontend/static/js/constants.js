export const COLORS = [
  '#FF6B35',
  '#4ECDC4',
  '#45B7D1',
  '#9B59B6',
  '#E67E22',
  '#27AE60',
  '#E91E63',
  '#3498DB',
  '#F39C12',
  '#1ABC9C',
  '#E74C3C',
  '#16A085',
];

export const WD = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

export const ST_EMPTY = 0;
export const ST_AVAIL = 1;
export const ST_BUSY = 2;

export const TUTORIAL_STEPS = [
  { emoji: '1️⃣', title: '点击格子循环切换状态', desc: '绿色 = 有空，红✕ = 没空，灰色 = 未填。每点一次循环切换。' },
  { emoji: '2️⃣', title: '拖拽批量填写', desc: '按住并上下拖动，快速填充多个相同的时段。' },
  { emoji: '3️⃣', title: '切换布局查看', desc: '时间为行 vs 人员为行，两种视角全面了解情况。' },
  { emoji: '4️⃣', title: '分享链接邀请', desc: '复制链接，发微信群，朋友点链接选名字就能填。' },
];

export const CHANGELOG_ITEMS = [
  { version: '1.6.3', title: 'AI 模型配置收口版', date: '2026-04-28', summary: '统一抽出 DEEPSEEK_MODEL，AI 草稿与 AI 总结共用同一模型配置。' },
  { version: '1.6.2', title: '兜底收缩与旧兼容清理版', date: '2026-04-15', summary: '收缩 AI 起草本地兜底，移除旧表格开放删除兼容路径。' },
  { version: '1.6.1', title: '数据库存储重构版', date: '2026-04-13', summary: 'SQLite 切换为多表业务结构，API 与前端主流程保持稳定。' },
  { version: '1.6.0', title: '设计质感升级版', date: '2026-04-10', summary: '升级整体视觉质感，创建页调整为左 AI 辅助、右人工确核布局。' },
  { version: '1.5.2', title: 'AI 起草建表版', date: '2026-04-10', summary: '支持一句话生成创建草稿，自动识别时间、参与者与关键成员预设。' },
  { version: '1.5.1', title: '关键成员约束版', date: '2026-04-10', summary: '支持创建者标记关键成员，并让表格汇总与 AI 推荐按关键成员约束优先排序。' },
  { version: '1.5.0', title: '首尾截断与偏好版', date: '2026-04-10', summary: '支持首尾截断时间、不可填写区显示、用户默认视图设置，并修复管理弹窗时间选择。' },
  { version: '1.4.3', title: '本地启动修复版', date: '2026-04-09', summary: '修复本地运行时静态脚本 404 与时间下拉框失效问题。' },
  { version: '1.4.2', title: '表格管理版', date: '2026-04-09', summary: '创建者可改整张表、删整表、改参与者名单，参与者可主动退出。' },
  { version: '1.4.1', title: '模块化硬化版', date: '2026-03-30', summary: '前端模块化拆分，CI、备份和 API 基线补齐。' },
  { version: '1.4.0', title: '会话打磨版', date: '2026-03-29', summary: 'UI 与会话流程整体打磨，进入阶段性跃迁。' },
];
