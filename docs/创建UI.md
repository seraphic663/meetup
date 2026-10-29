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

### 5. 主表格中的备注

主表格页为当前参与者提供个人备注输入框。备注是本地草稿，点击“保存并公开”后才通过现有可用性保存接口提交；提交后会显示在“已公开备注”卡片中，持分享链接的人可以查看，只有备注本人可以继续编辑。轮询不会覆盖正在编辑或提交中的草稿。

这项能力不新增数据库表或接口，已有会话的备注和可用时间会按原数据继续读取。

### 6. 常量与状态

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

无分享参数时，首页是 HTML 默认可见页面；创建、历史、加入和排期页面初始隐藏。初始化时若 URL 带有表格 ID，脚本再加载对应调查；否则首页保持显示，避免首次加载先闪现创建表单。

首页主内容收窄并居中。品牌标题、简介、功能特点和主要操作组成首屏；简介保持单行，窄屏按视口宽度缩小字号。“创建新表”单独占一行，“快速预览”和“查看使用教程”并列占第二行，并保持下划线文字链接样式。创建按钮与粘贴链接输入区使用相同最大宽度，左右边线对齐。历史记录与粘贴链接恢复入口共用一个“历史记录”分区，折叠更新日志排在其后；使用细分隔线分区，不再使用卡片外壳、阴影或圆角底板。

### 主面板 `hero-panel`

包含标题与一句简介、行内功能说明、分两行排列的创建/预览/教程操作。简介保持短句，不插入手工换行；首页不再显示“多人时间协调”标签，功能说明用短分隔点串联。品牌主色使用蓝色；红、绿时间条继续表示不方便与偏好，新分配的参与者识别色避开绿色。

对应样式在 [frontend/styles.css](d:/temp/meetup/frontend/styles.css)，结构在 [frontend/index.html](d:/temp/meetup/frontend/index.html)。常用类名为 `.hero-panel`、`.home-logo`、`.hero-highlights` 和 `.hero-actions`。

### 历史与更新区 `home-cards`

历史记录和默认折叠的更新日志保持常驻，以普通分区呈现。粘贴链接/ID 恢复与最近表格共用一个历史区；最近表格使用分隔列表行，空状态使用简短说明。常用类名为 `.hc-history` 和 `.hc-log`。

排期页顶部使用浅底标题栏，表名、日期摘要和操作居中排列；成员徽标、工具栏及时间条控件以居中分组呈现。竖屏时间轴的日期网格在可用空间内居中，参与者较多时由图表自身横向滚动，页面本身不横向溢出。编辑表单保持字段左对齐，方便快速扫描和填写。

## 当前创建页 UI 结构

创建页在：

- [frontend/index.html](d:/temp/meetup/frontend/index.html)

桌面端最大宽度约 1020px。品牌标题跨两栏置顶居中；下方左栏至少 180px，放 AI 起草和参与者卡片，右栏至少 360px，放活动信息。两列内容保持等高，列间距 16px、行间距 20px，创建按钮在两列下方居中。双栏最小尺寸加间距放不下时（约 576px 以下），创建页改为单列，顺序为品牌标题、AI 起草、活动信息、参与者、创建按钮。活动信息中的日期、每日时间范围和首尾截断字段始终成对并排，包括单列页面下的活动信息卡。

- 顶部全宽品牌标题 `setup-brand`
- 左侧辅助区 `setup-intro` 与参与者卡片
- 右侧活动信息卡片 `setup-form`
- 底部居中的创建按钮

### 品牌区与左侧辅助区

品牌区包含：

- 无卡片外框的品牌标题 `logo-area`：日历图标与产品名同排居中，不显示标题下的说明文字

左侧辅助区包含 AI 快速起草卡 `setup-note` 和参与者卡片。

当前 `setup-note` 承载 AI 快速起草：用户输入一句话后，草稿会回填右侧表单，并在左侧展示识别来源、识别结果和提醒。描述框宽度保持随栏宽固定，只随内容垂直增高，并限制最大高度以避免挤占整页。这里是辅助创建入口，不是第二套创建流程。

发起人提示语输入框也会随内容自动增高，只允许纵向变化，并限制最大高度。

发起人提示语不再提供“工作日晚间优先、线下优先、连续 1 小时”快捷模板；创建页也不重复展示面向群友的填写说明。

预设昵称只在加入页作为快捷选项；新用户可点选后进入，也可手动输入。加入接口仍接受名单外昵称，因此该名单不限制可加入人员，也不用于身份核验。

### 右侧表单区

桌面端左右分栏，底部操作居中。窄屏顺序：

1. 品牌标题
2. AI 起草
3. 活动信息
4. 参与者
5. 创建按钮

这里的结构和字段都写在：

- [frontend/index.html](d:/temp/meetup/frontend/index.html)

样式集中在：

- [frontend/styles.css](d:/temp/meetup/frontend/styles.css)

行为集中在：

- [frontend/static/js/app.js](d:/temp/meetup/frontend/static/js/app.js)

## 时间区间填写

时间轴是创建、填写、查看和汇总的统一界面。参与者可拖动创建时间条、移动时间条或调整两端；点击时间条可填写一条备注。个人的“整体说明”适用于全部时间段，与某一条时间区间的备注分开。

时间粒度可选 5、10、15、20、30 或 60 分钟。切换粒度时若现有端点与新刻度不吻合，普通参与者只能保留已有时间，之后的新建、移动和调整按新粒度吸附；发起人可选择将自己现有时间舍入到最近刻度，或保留原时间，也可取消切换。竖向视图中，短于 45 分钟的时间条整条用于移动，较长时间条可拖动上下端点。

主工具栏保留“展开他人”和“折叠他人”。个人时间条填充透明度统一为 50%；每个日期的连续汇总带分成红、绿两条，分别以不方便人数/参与者总数、偏好人数/参与者总数映射填充透明度。未标记表示尚未填写，不代表可参加。折叠的参与者仍计入汇总；点击汇总区间可查看两种状态的精确人数。视觉占比不改变 AI 总结当前“有人明确标记不方便即视为冲突”的推荐规则；整体说明仍与时间条备注分开保存。

首页的“快速预览（示例表）”打开一张无需填写活动信息的示例表，直接展示时间条、汇总和两种布局。真实参与者时间条会保存到服务端并供其他参与者查看。

实现位置：`frontend/static/js/timeline.js` 负责时间条交互与区间保存，`frontend/static/timeline.css` 负责横向和竖向时间轴，`frontend/index.html` 定义主界面。

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
