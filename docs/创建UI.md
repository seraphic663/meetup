# 创建 UI 说明

## 文档目的

这份文档用于说明当前前端 UI 的文件结构、页面组成与定位方式。  
如果后续需要让另一个人或另一个 AI 修改 UI，应该先看这份文档，再进入具体文件。

## 当前页面结构概览

项目当前前端主要分成 5 个页面区域：

1. 首页 `homeScreen`
2. 历史页 `historyScreen`
3. 创建页 `setupScreen`
4. 进入会话页 `joinScreen`
5. 主表格页 `mainScreen`

当前 UI 采用高密度紧凑样式：`frontend/styles.css` 已整理为 v2 分区结构，把原来的紧凑覆盖层合并进对应模块规则。后续如果要继续调密度，优先按文件内分区修改相关模块，不要再追加新的全局覆盖层。

这些页面都定义在：

- [frontend/index.html](d:/temp/meetup/frontend/index.html)

页面的显示与隐藏由 JS 控制，不是多页面跳转。

## 文件分工

### 1. HTML 结构

核心文件：

- [frontend/index.html](d:/temp/meetup/frontend/index.html)

职责：

- 定义所有页面区块的 DOM 结构
- 定义按钮、输入框、弹层、卡片的静态骨架
- 通过 `id` 和类名为 JS / CSS 提供挂载点

如果你要改：

- 首页卡片顺序、标题、文案、块级结构：先看这个文件
- 创建页表单字段顺序：先看这个文件
- 新增一个说明块或删除一个卡片：先看这个文件

### 2. 全局样式

核心文件：

- [frontend/styles.css](d:/temp/meetup/frontend/styles.css)

职责：

- 管所有页面的布局、卡片、按钮、输入框、首页视觉、表格样式
- 定义首页 `hero-panel`、右侧 `hc` 卡片、创建页 `.card`、表单 `.fi/.fg/.fl` 等

如果你要改：

- 首页左右布局、卡片间距、按钮大小、输入框高度、留白节奏：先看这个文件
- 创建页是否紧凑、卡片内边距是否过大：先看这个文件
- 首页不好看但结构没问题：优先改这里，不要先改 JS

### 3. 页面逻辑

核心文件：

- [frontend/static/js/app.js](d:/temp/meetup/frontend/static/js/app.js)

职责：

- 页面切换
- 创建表格
- AI 草稿生成并回填表单
- 管理整表、退出、删除、保存填写等行为

如果你要改：

- 创建按钮行为
- AI 起草按钮行为
- 表单值如何读写
- 首页按钮跳转到哪里

这些都在这个文件里找。

### 4. 局部渲染

核心文件：

- [frontend/static/js/render.js](d:/temp/meetup/frontend/static/js/render.js)

职责：

- 渲染最近表格
- 渲染首页更新日志
- 渲染进入会话页和主表格页内容

如果你要改：

- 最近表格列表长什么样
- 首页更新日志列表怎么渲染
- 主表格的行列和汇总块怎么输出

优先看这个文件。

### 5. 常量与状态

相关文件：

- [frontend/static/js/constants.js](d:/temp/meetup/frontend/static/js/constants.js)
- [frontend/static/js/state.js](d:/temp/meetup/frontend/static/js/state.js)

职责：

- 常量、颜色、更新日志首页摘要
- 前端全局状态

如果只是改 UI，一般不需要先动这两个文件。  
只有在新增一个新的展示状态或首页版本摘要时才需要改。

## 当前首页 UI 结构

首页在：

- [frontend/index.html](d:/temp/meetup/frontend/index.html)

当前结构是两列：

- 左侧主面板：`hero-panel`
- 右侧功能卡片区：`home-cards`

### 左侧主面板 `hero-panel`

包含：

- 产品标识 `hero-badge`
- Logo / 标题 / 简介 `home-logo`
- 精简版“如何使用” `hero-guide`
- 三个特性指标 `hero-metrics`
- 主按钮 `btn-hero`

对应样式主要在：

- [frontend/styles.css](d:/temp/meetup/frontend/styles.css)

可通过这些类名定位：

- `.hero-panel`
- `.home-logo`
- `.hero-guide`
- `.hero-metrics`
- `.hero-actions`

### 右侧卡片区 `home-cards`

当前保留：

- 创建新表
- 历史栏（恢复旧表 + 最近表格）
- 更新日志

对应 HTML 在：

- [frontend/index.html](d:/temp/meetup/frontend/index.html)

对应样式主要在：

- [frontend/styles.css](d:/temp/meetup/frontend/styles.css)

可通过这些类名定位：

- `.home-cards`
- `.hc`
- `.hc-primary`
- `.hc-log`

## 当前创建页 UI 结构

创建页在：

- [frontend/index.html](d:/temp/meetup/frontend/index.html)

主要由两列构成：

- 左侧辅助区 `setup-intro`
- 右侧表单区 `setup-form`

### 左侧辅助区

包含：

- 产品介绍卡 `logo-area`
- 创建说明卡 `setup-note`

当前 `setup-note` 承载 AI 快速起草：用户输入一句话后，草稿会回填右侧表单，并在左侧展示识别来源、识别结果和提醒。这里是辅助创建入口，不是第二套创建流程。

### 右侧表单区

当前顺序：

1. 活动信息
2. 参与者
3. 创建按钮

这里的结构和字段都写在：

- [frontend/index.html](d:/temp/meetup/frontend/index.html)

样式集中在：

- [frontend/styles.css](d:/temp/meetup/frontend/styles.css)

行为集中在：

- [frontend/static/js/app.js](d:/temp/meetup/frontend/static/js/app.js)

## 如何快速定位某个 UI 问题

### 场景 1：首页不好看

先看：

- [frontend/index.html](d:/temp/meetup/frontend/index.html)
- [frontend/styles.css](d:/temp/meetup/frontend/styles.css)

判断方式：

- 如果是结构问题，例如卡片太多、顺序不合理、信息层级混乱：改 `index.html`
- 如果是视觉问题，例如太空、太散、按钮太大、边距太宽：改 `styles.css`

### 场景 2：创建页太松散或太拥挤

先看：

- [frontend/styles.css](d:/temp/meetup/frontend/styles.css)

重点搜这些类名：

- `.setup-form`
- `.setup-form .card`
- `.fg`
- `.fl`
- `.fi`
- `.fi-row`
- `.prompt-input`
- `.tag-wrap`

### 场景 3：AI 起草按钮行为不对

先看：

- [frontend/static/js/app.js](d:/temp/meetup/frontend/static/js/app.js)

重点搜：

- `generateCreateDraft`
- `applyCreateDraftToForm`
- `renderCreateDraftPanel`
- `createSession`

### 场景 4：历史栏或最近表格显示异常

先看：

- [frontend/index.html](d:/temp/meetup/frontend/index.html)
- [frontend/static/js/render.js](d:/temp/meetup/frontend/static/js/render.js)
- [frontend/static/js/app.js](d:/temp/meetup/frontend/static/js/app.js)
- [frontend/static/js/history.js](d:/temp/meetup/frontend/static/js/history.js)

重点搜：

- `renderHistoryCard`
- `renderHistoryScreen`
- `restoreSessionFromHome`
- `parseSessionIdInput`
- `removeSessionFromHistory`
- `removeHistoryItem`

注意：首页“历史栏”是常驻入口，上半部支持粘贴旧分享链接或表格 ID，下半部展示当前域名下 `localStorage` 最近记录。即使最近记录为空，也要显示空状态，不要隐藏整块历史栏。首页“删除”只移除本地最近记录，用于清理过期或不存在的表格入口；创建者删除远端整表仍走 `deleteSessionFromHistory` / `deleteCurrentSession`。

## 如果要指导另一个人或 AI 修改 UI，应怎样描述

建议按下面顺序交代，不要只说“改首页好看一点”。

### 1. 先说目标页面

例如：

- 修改首页 `homeScreen`
- 修改创建页 `setupScreen`
- 修改主表格页 `mainScreen`

### 2. 再说问题类型

例如：

- 结构问题：卡片太多，信息分散
- 节奏问题：留白太大，不够紧凑
- 层级问题：主按钮不够突出，说明太抢眼
- 协作问题：不知道从哪个文件下手

### 3. 再给出文件入口

例如：

- 结构先看 [frontend/index.html](d:/temp/meetup/frontend/index.html)
- 样式先看 [frontend/styles.css](d:/temp/meetup/frontend/styles.css)
- 行为先看 [frontend/static/js/app.js](d:/temp/meetup/frontend/static/js/app.js)
- 列表渲染先看 [frontend/static/js/render.js](d:/temp/meetup/frontend/static/js/render.js)

### 4. 再给出定位关键词

例如：

- 首页主面板：`hero-panel`
- 首页卡片：`home-cards`、`hc`
- 创建页表单：`setup-form`
- AI 起草：`generateCreateDraft`、`aiDraftPanel`

### 5. 最后说明约束

建议明确这些约束：

- 优先复用现有结构，不重做整页
- 优先减法，不继续加更多卡片
- 改 UI 时先动 CSS，结构不对再动 HTML
- 不要为了单个视觉改动引入新的状态层

## 推荐协作描述模板

如果以后要让别人或另一个 AI 改 UI，可以直接照这个模板说：

1. 目标页面是首页 `homeScreen`
2. 当前问题是右侧卡片太碎，信息层级不清晰
3. 请先看 [frontend/index.html](d:/temp/meetup/frontend/index.html) 中首页结构，再看 [frontend/styles.css](d:/temp/meetup/frontend/styles.css) 中 `.hero-panel`、`.home-cards`、`.hc`
4. 优先把说明信息并回左侧主面板，减少右侧卡片数量
5. 不要新增新的 JS 状态，不要重做首页交互

## 一句话总结

改这个项目的 UI，先分清：

- 结构在 `index.html`
- 视觉在 `styles.css`
- 行为在 `app.js`
- 列表渲染在 `render.js`

先定位，再下刀，避免“为了改一点 UI 把整个页面逻辑翻掉”。

## 附录：高级 UI 维护与审查基线（面向未来的 AI 与人类）

作为经历过打磨的交互沉淀，后续对 UI 的任何改动必须遵守以下基线：

1. **克制动效（Subtle Animations）**：所有 Hover 和 Focus 必须包含 `transition: all 0.3s ease;`，位移不超过 `-2px` 到 `-4px`，阴影使用基于 `--brand` 或 `--shadow` 的带透明度扩张，**绝对禁止**突兀的颜色跳变。
2. **空间留白（Breathing Room）**：卡片内边距（Padding）和输入框高度是精心调优的，新增表单元素时直接复用 `.fi` 和 `.fg`，不要用内联样式微调。
3. **色彩聚焦（Focus Rings）**：在输入框或按键聚焦时，必须提供 `box-shadow: 0 0 0 3px var(--brand-soft);` 类似的光晕反馈，杜绝浏览器默认黑框。
4. **无框架原则（Zero-Framework Policy）**：当前所有的响应式布局（Flex/Grid）和组件样式（Card/Button/Input）均内建于 `styles.css` 中并使用 CSS 变量。如果觉得哪个组件不够用，在现有变量体系内扩展，**严禁**为图省事引入 Tailwind、Bootstrap 等外部 CSS 库。
5. **性能第一**：确保不要在 `scroll`、`mousemove` 等高频事件中做大范围的 DOM 重新渲染。视图切换始终沿用现有的 `hidden` 类名控制，而非销毁/重建。

**审查口诀**：加功能前向后看，变样式前查变量；动效不准晃瞎眼，新加卡片抄老款。
