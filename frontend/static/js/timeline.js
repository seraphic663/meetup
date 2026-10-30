import { requestJson } from './api.js';
import { getSessionAuthHeaders } from './history.js';
import { $, esc, getDates, getDayTimeWindow, toast } from './helpers.js';
import { applyUserTheme, saveUserPreferences } from './preferences.js';
import { state } from './state.js';

const STEPS = [5, 10, 15, 20, 30, 60];
const VERTICAL_PX_PER_MINUTE = 0.8;
const MIN_VERTICAL_RESIZE_MINUTES = 45;
let step = 15;
let orientation = 'horizontal';
let activeType = '';
let loadedKey = '';
let ownBlocks = {};
let editing = null;
let drag = null;
let pendingStep = null;
let selectedSummary = null;
let ownBlocksDirty = false;
let ownIntervalsSignature = '';
let intervalSaveTimer = null;
let intervalSaveInFlight = false;
let intervalEditRevision = 0;
let intervalSaveFailed = false;
let settingsOpen = false;

export function initTimeline() {
  const panel = $('timelinePanel');
  if (!panel || panel.dataset.ready) return;
  panel.dataset.ready = 'true';
  panel.addEventListener('click', onClick);
  panel.addEventListener('input', onInput);
  panel.addEventListener('change', onChange);
  panel.addEventListener('pointerdown', onPointerDown);
  panel.addEventListener('pointermove', onPointerMove);
  panel.addEventListener('pointerup', onPointerUp);
  panel.addEventListener('pointercancel', cancelPointer);
}
export function startTimeline() {
  step = state.userPrefs.step;
  orientation = state.userPrefs.orientation;
  activeType = '';
  loadedKey = '';
  ownBlocks = {};
  editing = null;
  drag = null;
  pendingStep = null;
  selectedSummary = null;
  settingsOpen = false;
  ownBlocksDirty = false;
  ownIntervalsSignature = '';
  clearTimeout(intervalSaveTimer);
  intervalSaveInFlight = false;
  intervalEditRevision = 0;
  intervalSaveFailed = false;
}

export function renderTimeline() {
  if (!state.S) return;
  const panel = $('timelinePanel');
  const key = (state.SID || '') + ':' + (state.ME || 'viewer');
  const sessionChanged = key !== loadedKey;
  const previousScroll = panel.querySelector('.td-scroll');
  const noteInput = panel.querySelector('[data-note]');
  const restoreNoteFocus = noteInput && document.activeElement === noteInput;
  const noteSelection = restoreNoteFocus ? [noteInput.selectionStart, noteInput.selectionEnd] : null;
  const scrollLeft = previousScroll?.scrollLeft || 0;
  const scrollTop = previousScroll?.scrollTop || 0;
  ensureOwnBlocks();
  const canEdit = Boolean(state.ME);
  const axisStart = Number(state.S.hourS) * 60;
  const axisEnd = Number(state.S.hourE) * 60;
  const width = axisEnd - axisStart;
  const guideText = !canEdit
    ? '查看各参与者标记的时间区间。'
    : !activeType
      ? '选“不方便”或“更偏好”后拖动新建；再点选中项可取消。'
      : orientation === 'vertical'
        ? '空白处拖动新建；短条移动，长条可调两端；点条编辑备注。'
        : '空白处拖动新建；拖条移动，拖两端调整；点条编辑备注。';
  panel.innerHTML =
    '<section class="td-shell">' +
      '<div class="td-toolbar-row">' +
        '<header class="td-head"><b>时间安排</b></header>' +
        '<div class="td-tools">' +
        '<div class="td-legend" role="group" aria-label="时间条类型">' + toolButton('busy', '不方便') + toolButton('preferred', '更偏好') + '</div>' +
        '<div class="td-quick-actions">' +
          '<div class="td-settings' + (settingsOpen ? ' open' : '') + '">' +
            '<button class="td-settings-trigger" type="button" data-settings-toggle aria-expanded="' + settingsOpen + '" aria-label="时间表设置" title="时间表设置"><span aria-hidden="true">⚙︎</span><span class="sr-only">时间表设置</span></button>' +
            (settingsOpen ? '<div class="td-settings-menu">' +
            '<section class="td-settings-group"><span class="td-settings-label">其他参与者</span><div class="td-segmented" role="group" aria-label="其他参与者">' +
              '<button class="td-segmented-btn' + (!state.collapsed ? ' active' : '') + '" id="btnExpandOthers" type="button" aria-pressed="' + (!state.collapsed) + '" onclick="expandOthers()">展开</button>' +
              '<button class="td-segmented-btn' + (state.collapsed ? ' active' : '') + '" id="btnCollapseOthers" type="button" aria-pressed="' + state.collapsed + '" onclick="collapseOthers()">折叠</button>' +
            '</div></section>' +
            '<section class="td-settings-group"><span class="td-settings-label">时间轴方向</span><div class="td-segmented" role="group" aria-label="时间轴方向">' +
              orientationButton('horizontal', '横向') + orientationButton('vertical', '竖向') + '</div></section>' +
            '<section class="td-settings-group"><label class="td-settings-label" for="tdStepSelect">时间粒度</label><select class="td-step-select" id="tdStepSelect" data-step-select aria-label="时间粒度">' +
              STEPS.map(value => '<option value="' + value + '"' + (step === value ? ' selected' : '') + '>' + value + ' 分钟</option>').join('') +
            '</select></section>' +
            '<section class="td-settings-group"><span class="td-settings-label">外观</span><div class="td-segmented" role="group" aria-label="外观">' +
              themeButton('light', '日间') + themeButton('dark', '夜间') + '</div></section>' +
            '</div>' : '') +
          '</div>' +
          '<button class="td-home-button" type="button" onclick="goToHome()">回首页</button>' +
        '</div>' +
        '</div>' +
      '</div>' +
      '<p class="td-guide">' + guideText + '</p>' +
      renderSummaryDetail() +
      '<div class="td-scroll td-scroll-' + orientation + '"><div class="td-days td-days-' + orientation + '">' + getDates(state.S).map(date => renderDay(date, axisStart, axisEnd, width)).join('') + '</div></div>' +
      renderEditor() + renderStepDialog() +
    '</section>';
  const nextScroll = panel.querySelector('.td-scroll');
  nextScroll.scrollLeft = sessionChanged ? 0 : scrollLeft;
  nextScroll.scrollTop = sessionChanged ? 0 : scrollTop;
  if (restoreNoteFocus) {
    const nextNote = panel.querySelector('[data-note]');
    nextNote?.focus();
    if (nextNote && noteSelection) nextNote.setSelectionRange(...noteSelection);
  }
}

export function isTimelineDragging() {
  return Boolean(drag);
}

function toolButton(type, label) {
  return '<button type="button" data-type="' + type + '" class="td-tool td-tool-' + type +
    (activeType === type ? ' active' : '') + '" aria-pressed="' + (activeType === type) + '" ' +
    (state.ME ? '' : 'disabled') + '><i></i>' + label + '</button>';
}

function orientationButton(value, label) {
  return '<button type="button" data-orientation="' + value + '" class="td-segmented-btn' +
    (orientation === value ? ' active' : '') + '" aria-pressed="' + (orientation === value) + '">' + label + '</button>';
}

function themeButton(value, label) {
  return '<button type="button" data-theme="' + value + '" class="td-segmented-btn' +
    (state.userPrefs.theme === value ? ' active' : '') + '" aria-pressed="' + (state.userPrefs.theme === value) + '">' + label + '</button>';
}

function renderStepDialog() {
  if (!pendingStep) return '';
  const value = pendingStep.nextStep;
  const canRound = state.quickDemo || Boolean(state.S?.capabilities?.canManageSession);
  return '<div class="td-modal-backdrop"><section class="td-step-dialog" role="dialog" aria-modal="true" aria-labelledby="tdStepTitle">' +
    '<h3 id="tdStepTitle">调整到 ' + value + ' 分钟粒度？</h3>' +
    '<p>有 ' + pendingStep.conflicts + ' 段时间的起止点不符合新粒度。' +
      (canRound ? '你可以选择怎样处理：' : '切换粒度不会改变已有时间，之后的编辑会按新粒度吸附。') + '</p>' +
    (canRound ? '<button type="button" class="td-choice" data-round-step>自动舍入已有时间 <small>将起止点吸附到最近的 ' + value + ' 分钟刻度</small></button>' : '') +
    '<button type="button" class="td-choice" data-preserve-step>保留已有时间 <small>区间时间不变，之后新建、移动和调整按 ' + value + ' 分钟吸附</small></button>' +
    '<button type="button" class="td-cancel-step" data-cancel-step>取消切换</button>' +
    '</section></div>';
}

function ensureOwnBlocks() {
  const key = (state.SID || '') + ':' + (state.ME || 'viewer');
  const me = state.S?.participants?.find(person => person.id === state.ME);
  const serverSignature = JSON.stringify(me?.intervals || []);
  if (key === loadedKey && (state.quickDemo || ownBlocksDirty || serverSignature === ownIntervalsSignature)) return;
  if (key !== loadedKey) {
    ownBlocksDirty = false;
    intervalSaveFailed = false;
  }
  loadedKey = key;
  ownBlocks = {};
  if (!state.ME) return;
  ownIntervalsSignature = serverSignature;
  getDates(state.S).forEach(date => {
    ownBlocks[date] = (me?.intervals || []).filter(interval => interval.date === date).map(block => ({
      id: block.id,
      start: Number(block.startMinute),
      end: Number(block.endMinute),
      type: block.type,
      note: block.note || '',
    }));
  });
}

function getVisibleParticipants() {
  const participants = state.S?.participants || [];
  return state.collapsed ? participants.filter(person => person.id === state.ME) : participants;
}

function getParticipantBlocks(person, date) {
  if (person.id === state.ME) return ownBlocks[date] || [];
  return (person.intervals || []).filter(interval => interval.date === date).map(block => ({
    id: block.id,
    start: Number(block.startMinute),
    end: Number(block.endMinute),
    type: block.type,
    note: block.note || '',
  }));
}

function renderDay(date, axisStart, axisEnd, width) {
  if (orientation === 'vertical') return renderVerticalDay(date, axisStart, axisEnd);
  const window = getDayTimeWindow(state.S, date);
  const dayStart = window.start * 60;
  const dayEnd = window.end * 60;
  const day = new Date(date + 'T00:00:00');
  const label = (day.getMonth() + 1) + '月' + day.getDate() + '日 · ' +
    ['日', '一', '二', '三', '四', '五', '六'][day.getDay()];
  let labels = '';
  let rules = '';
  for (let minute = axisStart; minute <= axisEnd; minute += 60) {
    const x = minute - axisStart;
    rules += '<i class="td-rule" style="left:' + x + 'px"></i>';
    if (minute < axisEnd) labels += '<span class="td-hour' + (minute === axisStart ? ' td-hour-first' : '') + '" style="left:' + x + 'px">' + time(minute) + '</span>';
  }
  const before = Math.max(0, dayStart - axisStart);
  const after = Math.max(0, axisEnd - dayEnd);
  const zones = (before ? '<i class="td-disabled" style="left:0;width:' + before + 'px"></i>' : '') +
    (after ? '<i class="td-disabled" style="left:' + (dayEnd - axisStart) + 'px;width:' + after + 'px"></i>' : '');

  const rows = getVisibleParticipants().map(person => {
    const mine = person.id === state.ME;
    const blocks = getParticipantBlocks(person, date);
    const bars = blocks.map(block => renderBlock(block, axisStart, axisEnd, date, mine)).join('');
    return '<div class="td-row" style="grid-template-columns:82px ' + width + 'px">' +
      '<span class="td-name' + (mine ? ' mine' : '') + '">' + esc(person.name) + (mine ? '（我）' : '') + '</span>' +
      '<div class="td-track' + (mine && state.ME ? ' editable' : '') + '" data-date="' + date +
        '" data-editable="' + Boolean(mine && state.ME) + '" style="width:' + width + 'px">' +
        zones + rules + bars + '</div></div>';
  }).join('');
  const segments = getTimelineSummarySegments(date, axisStart, axisEnd);
  const summaryBars = segments.map(segment =>
    renderSummarySegment(segment, axisStart, false, 'busy') +
    renderSummarySegment(segment, axisStart, false, 'preferred')).join('');

  return '<article class="td-day"><h3>' + label + '</h3>' +
    '<div class="td-canvas" style="min-width:' + (width + 82) + 'px">' +
      '<div class="td-row td-axis" style="grid-template-columns:82px ' + width + 'px">' +
        '<span class="td-name">参与者</span><div class="td-axis-track" style="width:' + width + 'px">' + zones + labels + rules + '</div>' +
      '</div>' + (rows || '<p class="td-empty">还没有参与者</p>') +
      '<div class="td-row td-summary-row" style="grid-template-columns:82px ' + width + 'px">' +
        '<span class="td-name td-summary-name">汇总</span><div class="td-summary-track" data-date="' + date + '" style="width:' + width + 'px">' +
          zones + rules + summaryBars + '</div></div>' +
    '</div></article>';
}

function renderVerticalDay(date, axisStart, axisEnd) {
  const window = getDayTimeWindow(state.S, date);
  const dayStart = window.start * 60;
  const dayEnd = window.end * 60;
  const axisHeight = (axisEnd - axisStart) * VERTICAL_PX_PER_MINUTE;
  const day = new Date(date + 'T00:00:00');
  const label = (day.getMonth() + 1) + '月' + day.getDate() + '日 · ' +
    ['日', '一', '二', '三', '四', '五', '六'][day.getDay()];
  const people = getVisibleParticipants();
  const columnCount = Math.max(1, people.length);
  const headers = people.map(person => {
    const mine = person.id === state.ME;
    return '<span class="td-vperson' + (mine ? ' mine' : '') + '">' + esc(person.name) + (mine ? '（我）' : '') + '</span>';
  }).join('');
  const labels = [];
  const rules = [];
  for (let minute = axisStart; minute <= axisEnd; minute += 60) {
    const y = (minute - axisStart) * VERTICAL_PX_PER_MINUTE;
    rules.push('<i class="td-vrule" style="top:' + y + 'px"></i>');
    if (minute < axisEnd) labels.push('<span class="td-vhour" style="top:' + y + 'px">' + time(minute) + '</span>');
  }
  const lanes = people.map(person => {
    const mine = person.id === state.ME;
    const blocks = getParticipantBlocks(person, date);
    const bars = blocks.map(block => renderVerticalBlock(block, axisStart, axisEnd, date, mine)).join('');
    const before = Math.max(0, dayStart - axisStart) * VERTICAL_PX_PER_MINUTE;
    const after = Math.max(0, axisEnd - dayEnd) * VERTICAL_PX_PER_MINUTE;
    const zones = (before ? '<i class="td-vdisabled" style="top:0;height:' + before + 'px"></i>' : '') +
      (after ? '<i class="td-vdisabled" style="top:' + ((dayEnd - axisStart) * VERTICAL_PX_PER_MINUTE) + 'px;height:' + after + 'px"></i>' : '');
    return '<div class="td-vtrack' + (mine && state.ME ? ' editable' : '') + '" data-date="' + date +
      '" data-editable="' + Boolean(mine && state.ME) + '" style="height:' + axisHeight + 'px">' + zones + bars + '</div>';
  }).join('');
  const before = Math.max(0, dayStart - axisStart) * VERTICAL_PX_PER_MINUTE;
  const after = Math.max(0, axisEnd - dayEnd) * VERTICAL_PX_PER_MINUTE;
  const summaryZones = (before ? '<i class="td-vdisabled" style="top:0;height:' + before + 'px"></i>' : '') +
    (after ? '<i class="td-vdisabled" style="top:' + ((dayEnd - axisStart) * VERTICAL_PX_PER_MINUTE) + 'px;height:' + after + 'px"></i>' : '');
  const segments = getTimelineSummarySegments(date, axisStart, axisEnd);
  const summaryBars = segments.map(segment =>
    renderSummarySegment(segment, axisStart, true, 'busy') +
    renderSummarySegment(segment, axisStart, true, 'preferred')).join('');
  const summaryLane = '<div class="td-vsummary-track" data-date="' + date + '" style="height:' + axisHeight + 'px">' + summaryZones + summaryBars + '</div>';
  return '<article class="td-day td-day-vertical"><h3>' + label + '</h3>' +
    '<div class="td-vcanvas" style="--td-vheight:' + axisHeight + 'px;--td-vcolumns:' + columnCount + '">' +
      '<div class="td-vheader"><span class="td-vaxis-title">时间</span>' + (headers || '<span>参与者</span>') + '<span class="td-vsum-title">汇总</span></div>' +
      '<div class="td-vbody"><div class="td-vaxis" style="height:' + axisHeight + 'px">' + labels.join('') + '</div>' +
        '<div class="td-vlanes" style="height:' + axisHeight + 'px">' + rules.join('') +
          (lanes || '<div class="td-vtrack td-empty" style="height:' + axisHeight + 'px">还没有参与者</div>') + summaryLane + '</div></div>' +
    '</div></article>';
}

function getTimelineSummarySegments(date, axisStart, axisEnd) {
  const window = getDayTimeWindow(state.S, date);
  const start = Math.max(axisStart, window.start * 60);
  const end = Math.min(axisEnd, window.end * 60);
  if (end <= start) return [];

  const boundaries = new Set([start, end]);
  (state.S.participants || []).forEach(person => {
    const blocks = getParticipantBlocks(person, date);
    blocks.forEach(block => {
      if (block.start > start && block.start < end) boundaries.add(block.start);
      if (block.end > start && block.end < end) boundaries.add(block.end);
    });
  });

  const points = [...boundaries].sort((a, b) => a - b);
  const segments = [];
  for (let index = 0; index < points.length - 1; index += 1) {
    const segmentStart = points[index];
    const segmentEnd = points[index + 1];
    const summary = getTimelineSummary(date, segmentStart);
    const key = JSON.stringify([summary.busyCount, summary.preferredCount]);
    const previous = segments[segments.length - 1];
    if (previous && previous.end === segmentStart && previous.key === key) {
      previous.end = segmentEnd;
    } else {
      segments.push({ date, start: segmentStart, end: segmentEnd, summary, key });
    }
  }
  return segments;
}

function renderSummarySegment(segment, axisStart, vertical, kind) {
  const { start, end, summary } = segment;
  const duration = end - start;
  const participantCount = state.S.participants.length;
  const count = kind === 'busy' ? summary.busyCount : summary.preferredCount;
  const ratio = participantCount ? count / participantCount : 0;
  const size = duration * (vertical ? VERTICAL_PX_PER_MINUTE : 1);
  const title = time(start) + '–' + time(end) + ' · 不方便 ' + summary.busyCount + '/' + participantCount + '人 · 偏好 ' +
    summary.preferredCount + '/' + participantCount + '人';
  const selected = selectedSummary?.date === segment.date && selectedSummary?.start === start && selectedSummary?.end === end;
  const kindLabel = kind === 'busy' ? '不方便' : '偏好';
  const position = vertical
    ? 'left:' + (kind === 'busy' ? '4px' : '43px') + ';right:' + (kind === 'busy' ? '43px' : '4px') +
      ';top:' + ((start - axisStart) * VERTICAL_PX_PER_MINUTE) + 'px;height:' + size + 'px;--td-summary-ratio:' + ratio + ';'
    : 'left:' + (start - axisStart) + 'px;width:' + duration + 'px;' +
      (kind === 'busy' ? 'top:4px;bottom:20px;' : 'top:20px;bottom:4px;') + '--td-summary-ratio:' + ratio + ';';
  const ariaLabel = title + '；' + kindLabel + '带';
  return '<button type="button" class="td-summary-segment td-summary-' + kind + (selected ? ' selected' : '') +
    '" data-summary-segment data-kind="' + kind + '" data-date="' + esc(segment.date) + '" data-start="' + start +
    '" data-end="' + end + '" aria-pressed="' + Boolean(selected) + '" style="' + position +
    '" title="' + esc(ariaLabel) + '" aria-label="' + esc(ariaLabel) + '"></button>';
}

function getTimelineSummary(date, minute) {
  const participants = state.S.participants || [];
  const summary = { busyCount: 0, preferredCount: 0, busyNames: [], preferredNames: [] };
  participants.forEach(person => {
    const active = getParticipantBlocks(person, date).find(block => block.start <= minute && block.end > minute);
    if (!active) return;
    if (active.type === 'busy') {
      summary.busyCount += 1;
      summary.busyNames.push(person.name);
    } else if (active.type === 'preferred') {
      summary.preferredCount += 1;
      summary.preferredNames.push(person.name);
    }
  });
  return summary;
}

function renderSummaryDetail() {
  if (!selectedSummary) return '';
  const summary = getTimelineSummary(selectedSummary.date, selectedSummary.start);
  const participantCount = state.S.participants.length;
  return '<aside class="td-summary-detail" role="status">' +
    '<strong>' + time(selectedSummary.start) + '–' + time(selectedSummary.end) + '</strong>' +
    '<span>不方便：' + summary.busyCount + '/' + participantCount + '人' + (summary.busyNames.length ? '（' + esc(summary.busyNames.join('、')) + '）' : '') + '</span>' +
    '<span>偏好：' + summary.preferredCount + '/' + participantCount + '人' + (summary.preferredNames.length ? '（' + esc(summary.preferredNames.join('、')) + '）' : '') + '</span>' +
    '<button type="button" data-close-summary>关闭</button>' +
    '</aside>';
}

function renderBlock(block, axisStart, axisEnd, date, editable) {
  const dayWindow = getDayTimeWindow(state.S, date);
  const dayStart = dayWindow.start * 60;
  const dayEnd = dayWindow.end * 60;
  const left = Math.max(axisStart, dayStart, block.start);
  const right = Math.min(axisEnd, dayEnd, block.end);
  if (right <= left) return '';
  const info = [time(block.start) + '–' + time(block.end), typeName(block.type), block.note].filter(Boolean).join(' · ');
  const tag = editable ? 'button' : 'span';
  const action = editable ? ' type="button" data-block="' + esc(block.id) + '" aria-label="' + esc(info) + '"' : '';
  const handles = editable ? '<i class="td-handle td-handle-start" data-edge="start"></i><i class="td-handle td-handle-end" data-edge="end"></i>' : '';
  return '<' + tag + ' class="td-bar td-' + block.type + '"' + action + ' title="' + esc(info) +
    '" style="left:' + (left - axisStart) + 'px;width:' + (right - left) + 'px">' + handles + '</' + tag + '>';
}

function renderVerticalBlock(block, axisStart, axisEnd, date, editable) {
  const dayWindow = getDayTimeWindow(state.S, date);
  const dayStart = dayWindow.start * 60;
  const dayEnd = dayWindow.end * 60;
  const top = Math.max(axisStart, dayStart, block.start);
  const bottom = Math.min(axisEnd, dayEnd, block.end);
  if (bottom <= top) return '';
  const info = [time(block.start) + '–' + time(block.end), typeName(block.type), block.note].filter(Boolean).join(' · ');
  const tag = editable ? 'button' : 'span';
  const action = editable ? ' type="button" data-block="' + esc(block.id) + '" aria-label="' + esc(info) + '"' : '';
  const canResize = editable && bottom - top >= MIN_VERTICAL_RESIZE_MINUTES;
  const handles = canResize ? '<i class="td-handle td-handle-start" data-edge="start"></i><i class="td-handle td-handle-end" data-edge="end"></i>' : '';
  const resizeClass = editable ? (canResize ? ' td-vbar-resizable' : ' td-vbar-short') : '';
  return '<' + tag + ' class="td-bar td-' + block.type + ' td-vbar' + resizeClass + '"' + action + ' title="' + esc(info) +
    '" style="top:' + ((top - axisStart) * VERTICAL_PX_PER_MINUTE) + 'px;height:' + ((bottom - top) * VERTICAL_PX_PER_MINUTE) + 'px">' + handles + '</' + tag + '>';
}

function renderEditor() {
  if (!editing) return '';
  const block = (ownBlocks[editing.date] || []).find(item => item.id === editing.id);
  if (!block) return '';
  return '<div class="td-editor">' +
    '<label>这段时间的备注<textarea data-note maxlength="200" rows="2" placeholder="可选；其他参与者可见">' + esc(block.note || '') + '</textarea></label>' +
    '<span class="td-editor-hint" aria-live="polite">' + (state.quickDemo ? '示例预览中的修改不会保存到真实表格。' : (intervalSaveFailed ? '自动保存失败，修改仍保留；请重试。' : (intervalSaveInFlight ? '保存中…' : (ownBlocksDirty ? '等待保存…' : '已保存')))) + '</span>' +
    '<div class="td-actions">' + (intervalSaveFailed ? '<button type="button" data-retry-save>重试保存</button>' : '') +
      '<button type="button" data-delete>删除时间条</button><button type="button" data-close>关闭</button></div>' +
    '</div>';
}

function scheduleIntervalSave() {
  if (state.quickDemo || !state.ME || !state.SID) return;
  ownBlocksDirty = true;
  intervalEditRevision += 1;
  intervalSaveFailed = false;
  clearTimeout(intervalSaveTimer);
  intervalSaveTimer = setTimeout(() => void saveIntervals(), 500);
}

function commitIntervalChanges() {
  clearTimeout(intervalSaveTimer);
  intervalSaveTimer = null;
  void saveIntervals();
}

function getOwnIntervalRecords() {
  return getDates(state.S).flatMap(date => (ownBlocks[date] || []).map(block => ({
    id: block.id,
    date,
    startMinute: block.start,
    endMinute: block.end,
    type: block.type,
    note: block.note || '',
  })));
}

async function saveIntervals() {
  if (state.quickDemo || !state.ME || !state.SID || !ownBlocksDirty || intervalSaveInFlight) return;
  intervalSaveInFlight = true;
  const sessionId = state.SID;
  const participantId = state.ME;
  const revision = intervalEditRevision;
  const intervals = getOwnIntervalRecords();
  renderTimeline();
  try {
    const response = await requestJson(`/api/session/${sessionId}/intervals`, {
      method: 'PUT',
      headers: getSessionAuthHeaders(sessionId),
      body: { intervals },
    });
    if (state.SID !== sessionId || state.ME !== participantId) return;
    const participant = state.S?.participants?.find(item => item.id === participantId);
    const savedIntervals = response.intervals || intervals;
    if (participant) participant.intervals = savedIntervals;
    ownIntervalsSignature = JSON.stringify(savedIntervals);
    intervalSaveFailed = false;
    if (revision === intervalEditRevision) {
      ownBlocksDirty = false;
    } else {
      clearTimeout(intervalSaveTimer);
      intervalSaveTimer = setTimeout(() => void saveIntervals(), 0);
    }
  } catch (error) {
    if (state.SID === sessionId && state.ME === participantId) {
      intervalSaveFailed = true;
      toast(error?.message || '时间条保存失败，请重试');
    }
  } finally {
    intervalSaveInFlight = false;
    if (state.SID === sessionId && state.ME === participantId) renderTimeline();
  }
}

function onClick(event) {
  const target = event.target;
  if (target.closest('[data-settings-toggle]')) {
    settingsOpen = !settingsOpen;
    renderTimeline();
    return;
  }
  if (target.closest('[data-close-summary]')) {
    selectedSummary = null;
    renderTimeline();
    return;
  }
  const summaryTrack = target.closest('.td-summary-track[data-date], .td-vsummary-track[data-date]');
  if (summaryTrack) {
    const summarySegment = target.closest('[data-summary-segment]');
    let interval = summarySegment
      ? { start: Number(summarySegment.dataset.start), end: Number(summarySegment.dataset.end) }
      : null;
    if (!interval) {
      const minute = minuteAtExact(event, summaryTrack);
      interval = getTimelineSummarySegments(
        summaryTrack.dataset.date,
        Number(state.S.hourS) * 60,
        Number(state.S.hourE) * 60,
      ).find(item => minute >= item.start && minute < item.end);
    }
    if (!interval) return;
    selectedSummary = { date: summaryTrack.dataset.date, start: interval.start, end: interval.end };
    renderTimeline();
    return;
  }
  const tool = target.closest('[data-type]');
  if (tool) {
    activeType = activeType === tool.dataset.type ? '' : tool.dataset.type;
    renderTimeline();
    return;
  }
  const orientationChoice = target.closest('[data-orientation]');
  if (orientationChoice) {
    orientation = orientationChoice.dataset.orientation;
    saveTimelinePreferences({ orientation });
    editing = null;
    renderTimeline();
    return;
  }
  const themeChoice = target.closest('button[data-theme]');
  if (themeChoice) {
    const theme = themeChoice.dataset.theme;
    saveTimelinePreferences({ theme });
    applyUserTheme(theme);
    renderTimeline();
    return;
  }
  if (target.closest('[data-round-step]')) {
    finishStepChange(state.quickDemo || Boolean(state.S?.capabilities?.canManageSession));
    return;
  }
  if (target.closest('[data-preserve-step]')) {
    finishStepChange(false);
    return;
  }
  if (target.closest('[data-cancel-step]')) {
    pendingStep = null;
    $('timelinePanel')?.querySelector('.td-modal-backdrop')?.remove();
    return;
  }
  if (target.closest('[data-close]')) {
    editing = null;
    renderTimeline();
    return;
  }
  if (target.closest('[data-delete]') && editing) {
    ownBlocks[editing.date] = (ownBlocks[editing.date] || []).filter(block => block.id !== editing.id);
    editing = null;
    scheduleIntervalSave();
    commitIntervalChanges();
    renderTimeline();
    return;
  }
  if (target.closest('[data-retry-save]')) {
    clearTimeout(intervalSaveTimer);
    void saveIntervals();
  }
}

function minuteAtExact(event, track) {
  const axisStart = Number(state.S.hourS) * 60;
  const axisEnd = Number(state.S.hourE) * 60;
  const rect = track.getBoundingClientRect();
  const coordinate = orientation === 'vertical' ? event.clientY - rect.top : event.clientX - rect.left;
  const extent = orientation === 'vertical' ? rect.height : rect.width;
  const ratio = Math.max(0, Math.min(1, coordinate / extent));
  return Math.min(axisEnd - 0.001, axisStart + ratio * (axisEnd - axisStart));
}

function onInput(event) {
  if (!event.target.matches('[data-note]') || !editing) return;
  const block = (ownBlocks[editing.date] || []).find(item => item.id === editing.id);
  if (block) {
    block.note = String(event.target.value || '').slice(0, 200);
    scheduleIntervalSave();
  }
}

function onChange(event) {
  if (event.target.matches('[data-step-select]')) {
    requestStepChange(Number(event.target.value));
    return;
  }
  if (event.target.matches('[data-note]')) {
    clearTimeout(intervalSaveTimer);
    void saveIntervals();
  }
}

function requestStepChange(nextStep) {
  if (!STEPS.includes(nextStep)) return;
  if (nextStep === step) return;
  const conflicts = getDates(state.S).flatMap(date => (ownBlocks[date] || []).filter(block =>
    block.start % nextStep !== 0 || block.end % nextStep !== 0).map(block => ({ date, block })));
  if (conflicts.length) {
    pendingStep = { nextStep, conflicts: conflicts.length };
    const select = $('timelinePanel')?.querySelector('[data-step-select]');
    if (select) select.value = String(step);
    $('timelinePanel')?.insertAdjacentHTML('beforeend', renderStepDialog());
    return;
  }
  step = nextStep;
  saveTimelinePreferences({ step });
  updateStepControl();
}

function updateStepControl() {
  const panel = $('timelinePanel');
  const select = panel?.querySelector('[data-step-select]');
  if (select) select.value = String(step);
}

function finishStepChange(round) {
  if (!pendingStep) return;
  round = Boolean(round && (state.quickDemo || state.S?.capabilities?.canManageSession));
  const nextStep = pendingStep.nextStep;
  if (round) roundBlocks(nextStep);
  step = nextStep;
  saveTimelinePreferences({ step });
  pendingStep = null;
  editing = null;
  selectedSummary = null;
  if (round) scheduleIntervalSave();
  if (round) commitIntervalChanges();
  renderTimeline();
}

function saveTimelinePreferences(changes) {
  state.userPrefs = saveUserPreferences({ ...state.userPrefs, ...changes, collapsed: state.collapsed });
}

function roundBlocks(nextStep) {
  getDates(state.S).forEach(date => {
    const bounds = getTrackBounds(date);
    const ordered = [...(ownBlocks[date] || [])].sort((a, b) => a.start - b.start);
    const rounded = [];
    ordered.forEach(block => {
      let start = Math.max(bounds.start, Math.round(block.start / nextStep) * nextStep);
      let end = Math.min(bounds.end, Math.round(block.end / nextStep) * nextStep);
      const previousEnd = rounded.length ? rounded[rounded.length - 1].end : bounds.start;
      start = Math.max(start, previousEnd);
      if (end < start + nextStep) end = start + nextStep;
      if (end > bounds.end) {
        end = bounds.end;
        start = Math.max(previousEnd, end - nextStep);
      }
      if (end > start) rounded.push({ ...block, start, end });
    });
    ownBlocks[date] = compact(rounded);
  });
}

function onPointerDown(event) {
  const track = event.target.closest('.td-track[data-editable="true"], .td-vtrack[data-editable="true"]');
  if (!track || event.button !== 0) return;
  const date = track.dataset.date;
  const bounds = getTrackBounds(date);
  const point = minuteAt(event, track, false);
  const bar = event.target.closest('[data-block]');
  const block = bar && (ownBlocks[date] || []).find(item => item.id === bar.dataset.block);
  if (!block && !activeType) return;
  if (!block && (point < bounds.start || point >= bounds.end)) return;
  selectedSummary = null;
  const edge = event.target.closest('[data-edge]')?.dataset.edge || '';
  drag = {
    track, date, pointerId: event.pointerId,
    startCoord: orientation === 'vertical' ? event.clientY : event.clientX,
    anchor: snap(point), current: snap(point), kind: block ? (edge ? 'resize-' + edge : 'move') : 'create',
    origin: block ? { ...block } : null, type: block?.type || activeType, moved: false,
  };
  event.preventDefault();
  track.setPointerCapture?.(event.pointerId);
  drawPreview();
}

function onPointerMove(event) {
  if (!drag || event.pointerId !== drag.pointerId) return;
  drag.current = minuteAt(event, drag.track, true);
  const coord = orientation === 'vertical' ? event.clientY : event.clientX;
  if (Math.abs(coord - drag.startCoord) > 2) drag.moved = true;
  drawPreview();
}

function onPointerUp(event) {
  if (!drag || event.pointerId !== drag.pointerId) return;
  const finished = drag;
  finished.current = minuteAt(event, finished.track, true);
  finished.track.querySelector('.td-preview')?.remove();
  drag = null;
  if (!finished.moved && finished.kind === 'create') return;
  if (!finished.moved && finished.origin) {
    editing = { date: finished.date, id: finished.origin.id };
    renderTimeline();
    return;
  }
  const bounds = getTrackBounds(finished.date);
  let block;
  if (finished.kind === 'create') {
    let start = Math.min(finished.anchor, finished.current);
    let end = Math.max(finished.anchor, finished.current);
    if (end - start < step) {
      if (finished.current >= finished.anchor) end = Math.min(bounds.end, start + step);
      else start = Math.max(bounds.start, end - step);
      if (end - start < step) start = Math.max(bounds.start, end - step);
    }
    if (end <= start) return renderTimeline();
    block = { id: makeId(), start, end, type: finished.type, note: '' };
  } else if (finished.kind === 'move') {
    const shift = finished.current - finished.anchor;
    const duration = finished.origin.end - finished.origin.start;
    const start = Math.max(bounds.start, Math.min(bounds.end - duration, finished.origin.start + shift));
    block = { ...finished.origin, start, end: start + duration };
  } else {
    const candidate = finished.current;
    if (finished.kind === 'resize-start') {
      block = { ...finished.origin, start: Math.max(bounds.start, Math.min(finished.origin.end - step, candidate)) };
    } else {
      block = { ...finished.origin, end: Math.min(bounds.end, Math.max(finished.origin.start + step, candidate)) };
    }
  }
  placeBlock(finished.date, block, finished.origin?.id);
  editing = null;
  scheduleIntervalSave();
  commitIntervalChanges();
  renderTimeline();
}

function cancelPointer() {
  drag?.track.querySelector('.td-preview')?.remove();
  drag = null;
}

function drawPreview() {
  if (!drag) return;
  const bounds = getTrackBounds(drag.date);
  let start;
  let end;
  if (drag.kind === 'create') {
    start = Math.min(drag.anchor, drag.current);
    end = Math.max(drag.anchor, drag.current);
    if (end - start < step) end = Math.min(bounds.end, start + step);
  } else if (drag.kind === 'move') {
    const shift = drag.current - drag.anchor;
    const duration = drag.origin.end - drag.origin.start;
    start = Math.max(bounds.start, Math.min(bounds.end - duration, drag.origin.start + shift));
    end = start + duration;
  } else {
    start = drag.kind === 'resize-start' ? Math.max(bounds.start, Math.min(drag.origin.end - step, drag.current)) : drag.origin.start;
    end = drag.kind === 'resize-end' ? Math.min(bounds.end, Math.max(drag.origin.start + step, drag.current)) : drag.origin.end;
  }
  const axisStart = Number(state.S.hourS) * 60;
  let preview = drag.track.querySelector('.td-preview');
  if (!preview) {
    preview = document.createElement('span');
    preview.className = 'td-bar td-' + drag.type + ' td-preview' + (orientation === 'vertical' ? ' td-vbar' : '');
    drag.track.appendChild(preview);
  }
  if (orientation === 'vertical') {
    preview.style.top = ((start - axisStart) * VERTICAL_PX_PER_MINUTE) + 'px';
    preview.style.height = Math.max(step * VERTICAL_PX_PER_MINUTE, (end - start) * VERTICAL_PX_PER_MINUTE) + 'px';
  } else {
    preview.style.left = (start - axisStart) + 'px';
    preview.style.width = Math.max(step, end - start) + 'px';
  }
}

function minuteAt(event, track, clampToDay) {
  const axisStart = Number(state.S.hourS) * 60;
  const axisEnd = Number(state.S.hourE) * 60;
  const rect = track.getBoundingClientRect();
  const coord = orientation === 'vertical' ? event.clientY - rect.top : event.clientX - rect.left;
  const extent = orientation === 'vertical' ? rect.height : rect.width;
  const ratio = Math.max(0, Math.min(1, coord / extent));
  let minute = snap(axisStart + ratio * (axisEnd - axisStart));
  if (clampToDay) {
    const bounds = getTrackBounds(track.dataset.date);
    minute = Math.max(bounds.start, Math.min(bounds.end, minute));
  }
  return minute;
}

function placeBlock(date, block, excludedId) {
  const next = [];
  (ownBlocks[date] || []).forEach(old => {
    if (old.id === excludedId) return;
    if (old.end <= block.start || old.start >= block.end) next.push(old);
    else {
      if (old.start < block.start) next.push({ ...old, id: makeId(), end: block.start });
      if (old.end > block.end) next.push({ ...old, id: makeId(), start: block.end });
    }
  });
  next.push(block);
  ownBlocks[date] = compact(next);
}

function compact(blocks) {
  const result = [];
  [...blocks].sort((a, b) => a.start - b.start).forEach(block => {
    const last = result[result.length - 1];
    if (last && last.end === block.start && last.type === block.type && last.note === block.note) {
      last.end = block.end;
    } else result.push({ ...block });
  });
  return result;
}

function getTrackBounds(date) {
  const window = getDayTimeWindow(state.S, date);
  return { start: window.start * 60, end: window.end * 60 };
}

function snap(minutes) {
  return Math.round(minutes / step) * step;
}

function typeName(type) {
  return type === 'busy' ? '不方便' : '更偏好';
}

function time(minutes) {
  return String(Math.floor(minutes / 60)).padStart(2, '0') + ':' + String(minutes % 60).padStart(2, '0');
}

function makeId() {
  return globalThis.crypto?.randomUUID?.() || 'td-' + Date.now() + '-' + Math.random().toString(36).slice(2, 9);
}
