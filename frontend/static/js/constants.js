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
  { version: '4.3', title: '本地启动修复版', date: '2026-04-09', summary: '修复本地运行时静态脚本 404 与时间下拉框失效问题。' },
  { version: '4.2', title: '表格管理版', date: '2026-04-09', summary: '创建者可改整张表、删整表、改参与者名单，参与者可主动退出。' },
  { version: '4.1', title: '模块化硬化版', date: '2026-03-30', summary: '前端模块化拆分，CI、备份和 API 基线补齐。' },
  { version: '4.0', title: '会话打磨版', date: '2026-03-29', summary: 'UI 与会话流程整体打磨，进入阶段性跃迁。' },
  { version: '3.3', title: '发起人提示版', date: '2026-03-26', summary: '支持发起人为表格补充提示语。' },
];
