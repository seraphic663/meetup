import { requestJson, ApiError } from './api.js';
import { COLORS, ST_AVAIL, ST_BUSY, TUTORIAL_STEPS } from './constants.js';
import {
  clearParticipantAccess,
  clearSessionAccess,
  getLastName,
  getSavedParticipantName,
  getSessionAccess,
  getSessionAuthHeaders,
  rememberLastName,
  removeHistoryItem,
  saveCreatorToken,
  saveParticipantAccess,
  saveParticipantName,
  saveSessionFlags,
  saveToHistory,
} from './history.js';
import { $, clone, dayDiff, dfmt, esc, getDates, getHours, getSlotSummary, getState, isSlotEnabled, normalizeAvail, showScreen, toast } from './helpers.js';
import { getUserPreferences, saveUserPreferences } from './preferences.js';
import { buildSummaryCell, cellStyle, getNextColor, renderGrid, renderHistoryCard, renderHistoryScreen, renderJoin, renderMain, updateCollapseButton, updateRemarkCounter, updateRemarkHint } from './render.js';
import { renderAISummary } from './summary.js';
import { state } from './state.js';

function getApiMessage(error, fallback) {
  if (error instanceof ApiError) return error.message || fallback;
  return fallback;
}

function sessionHeaders(sessionId = state.SID) {
  return getSessionAuthHeaders(sessionId);
}

function applyUserViewDefaults() {
  state.layout = state.userPrefs.layout;
  state.collapsed = state.userPrefs.collapsed;
}

function syncSettingsDraftButtons() {
  $('prefLayoutTR')?.classList.toggle('active', state.settingsDraft.layout === 'tr');
  $('prefLayoutPR')?.classList.toggle('active', state.settingsDraft.layout === 'pr');
  $('prefCollapseOff')?.classList.toggle('active', !state.settingsDraft.collapsed);
  $('prefCollapseOn')?.classList.toggle('active', state.settingsDraft.collapsed);
}

function openUserSettings() {
  state.settingsDraft = { ...state.userPrefs };
  syncSettingsDraftButtons();
  $('settingsOverlay')?.classList.add('open');
}

function closeUserSettings() {
  $('settingsOverlay')?.classList.remove('open');
}

function overlayBgSettings(event) {
  if (event.target === $('settingsOverlay')) closeUserSettings();
}

function setSettingsLayout(mode) {
  state.settingsDraft.layout = mode === 'tr' ? 'tr' : 'pr';
  syncSettingsDraftButtons();
}

function setSettingsCollapse(collapsed) {
  state.settingsDraft.collapsed = Boolean(collapsed);
  syncSettingsDraftButtons();
}

function saveUserViewPreferences() {
  state.userPrefs = saveUserPreferences(state.settingsDraft);
  applyUserViewDefaults();
  if (!document.getElementById('mainScreen')?.classList.contains('hidden')) {
    renderMainScreen();
  }
  closeUserSettings();
  toast('用户设置已保存');
}

function fillHourOptions(select, fromHour, toHour) {
  if (!select) return;
  const currentValue = select.value;
  select.innerHTML = '';
  for (let hour = fromHour; hour <= toHour; hour += 1) {
    const option = document.createElement('option');
    option.value = hour;
    option.textContent = `${String(hour).padStart(2, '0')}:00`;
    select.appendChild(option);
  }
  if ([...select.options].some(option => option.value === currentValue)) {
    select.value = currentValue;
  }
}

function syncBoundaryTimeControls(prefix, changedField = '') {
  const startSelect = $(`${prefix}HourS`);
  const endSelect = $(`${prefix}HourE`);
  const firstSelect = $(`${prefix}FirstHourS`);
  const lastSelect = $(`${prefix}LastHourE`);
  const dateStart = $(`${prefix}DateS`)?.value || '';
  const dateEnd = $(`${prefix}DateE`)?.value || '';
  if (!startSelect || !endSelect || !firstSelect || !lastSelect) return;

  const baseStart = Number(startSelect.value || 9);
  const nextEnd = Math.max(Number(endSelect.value || 21), baseStart + 1);
  if (Number(endSelect.value || 0) !== nextEnd) endSelect.value = String(nextEnd);

  fillHourOptions(firstSelect, baseStart, nextEnd - 1);
  fillHourOptions(lastSelect, baseStart + 1, nextEnd);

  let firstValue = Number(firstSelect.value || baseStart);
  let lastValue = Number(lastSelect.value || nextEnd);
  firstValue = Math.min(Math.max(firstValue, baseStart), nextEnd - 1);
  lastValue = Math.max(Math.min(lastValue, nextEnd), baseStart + 1);

  if (dateStart && dateStart === dateEnd && firstValue >= lastValue) {
    if (changedField === 'first') {
      lastValue = Math.min(nextEnd, firstValue + 1);
    } else {
      firstValue = Math.max(baseStart, lastValue - 1);
    }
  }

  firstSelect.value = String(firstValue);
  lastSelect.value = String(lastValue);
}

function readTimeControls(prefix) {
  return {
    hourS: Number($(`${prefix}HourS`).value),
    hourE: Number($(`${prefix}HourE`).value),
    firstHourS: Number($(`${prefix}FirstHourS`).value),
    lastHourE: Number($(`${prefix}LastHourE`).value),
  };
}

function validateTimeWindow(dateS, dateE, hourS, hourE, firstHourS, lastHourE) {
  if (hourS >= hourE) return '截止时间须晚于起始时间';
  if (firstHourS < hourS || firstHourS >= hourE) return '首日开始时间不正确';
  if (lastHourE <= hourS || lastHourE > hourE) return '末日结束时间不正确';
  if (dateS && dateE && dateS === dateE && firstHourS >= lastHourE) return '同一天的首尾截断时间不正确';
  return '';
}

function getCurrentParticipant() {
  return state.S?.participants?.find(item => item.id === state.ME) || null;
}

function applySession(session) {
  state.S = session;
  state.S.participants.forEach(participant => {
    participant.avail = normalizeAvail(participant.avail);
  });
  saveSessionFlags(state.SID, {
    legacyCanDelete: Boolean(state.S?.capabilities?.canDeleteSession && !state.S?.viewer?.isCreator && !getSessionAccess(state.SID).creatorToken),
  });

  if (state.S.viewer?.participantId) {
    state.ME = state.S.viewer.participantId;
    state.ME_NAME = state.S.viewer.participantName || '';
    saveParticipantAccess(state.SID, {
      participantId: state.S.viewer.participantId,
      participantName: state.S.viewer.participantName || '',
    });
  } else if (state.ME && !state.S.participants.some(participant => participant.id === state.ME)) {
    state.ME = null;
    state.ME_NAME = '';
    state.myAvail = {};
    state.myRemark = '';
    clearParticipantAccess(state.SID);
  }
}

function hydrateCurrentUser(participantId, fallbackName = '') {
  state.ME = participantId;
  const participant = state.S?.participants?.find(item => item.id === state.ME);
  state.ME_NAME = participant?.name || fallbackName || '';
  state.myAvail = participant?.avail ? clone(participant.avail) : {};
  state.myRemark = (participant?.remark || '').slice(0, 200);
  saveParticipantName(state.SID, state.ME_NAME);
  saveToHistory(state.SID, state.S.name, state.S.dateS, state.S.dateE);
}

function restoreParticipant(autoEnter = false) {
  const access = getSessionAccess(state.SID);
  const savedId = access.participantId;
  const savedName = access.participantName || getSavedParticipantName(state.SID);
  const savedParticipant = (savedId && state.S?.participants?.find(item => item.id === savedId))
    || (savedName && state.S?.participants?.find(item => item.name === savedName));
  if (!savedParticipant) return false;
  hydrateCurrentUser(savedParticipant.id, savedParticipant.name);
  if (autoEnter) {
    applyUserViewDefaults();
    renderMainScreen();
    showScreen('mainScreen');
    startPoll();
  }
  return true;
}

function syncCurrentParticipant() {
  if (!state.ME || !state.S) return;
  const participant = state.S.participants.find(item => item.id === state.ME);
  if (!participant) return;
  participant.avail = clone(state.myAvail);
  participant.remark = state.myRemark;
}

function renderMainScreen() {
  renderMain();
  renderSessionControls();
  bindRemarkInput();
  attachEvents();
}

function bindRemarkInput() {
  const remark = $('myRemark');
  if (remark) remark.oninput = onRemarkInput;
}

function renderSessionControls() {
  const canManage = Boolean(state.S?.capabilities?.canManageSession);
  const canLeave = Boolean(state.S?.capabilities?.canLeaveSession);
  $('manageBtn')?.classList.toggle('hidden', !canManage);
  $('deleteSessionBtn')?.classList.toggle('hidden', !canManage);
  $('leaveSessionBtn')?.classList.toggle('hidden', !canLeave || canManage);
}

function showHome() {
  renderHistoryCard();
  showScreen('homeScreen');
}

function goToSession(sid) {
  location.href = `/?s=${sid}`;
}

function goToHome() {
  stopPoll();
  syncCurrentParticipant();
  void saveAvail();
  showHome();
}

function goToSetup() {
  showScreen('setupScreen');
}

function goToHistory() {
  renderHistoryScreen();
  showScreen('historyScreen');
}

function initForm() {
  const startSelect = $('sHourS');
  const endSelect = $('sHourE');
  const firstSelect = $('sFirstHourS');
  const lastSelect = $('sLastHourE');
  const manageStartSelect = $('manageHourS');
  const manageEndSelect = $('manageHourE');
  const manageFirstSelect = $('manageFirstHourS');
  const manageLastSelect = $('manageLastHourE');

  fillHourOptions(startSelect, 0, 23);
  fillHourOptions(manageStartSelect, 0, 23);
  fillHourOptions(endSelect, 1, 24);
  fillHourOptions(manageEndSelect, 1, 24);

  startSelect.value = 9;
  endSelect.value = 21;
  if (firstSelect) firstSelect.value = 9;
  if (lastSelect) lastSelect.value = 21;
  if (manageStartSelect) manageStartSelect.value = 9;
  if (manageEndSelect) manageEndSelect.value = 21;
  if (manageFirstSelect) manageFirstSelect.value = 9;
  if (manageLastSelect) manageLastSelect.value = 21;
  const now = new Date();
  const later = new Date(now);
  later.setDate(now.getDate() + 3);
  $('sDateS').value = dfmt(now);
  $('sDateE').value = dfmt(later);
  $('sMyName').value = getLastName();

  syncBoundaryTimeControls('s');
  syncBoundaryTimeControls('manage');

  ['HourS', 'HourE', 'DateS', 'DateE'].forEach(field => {
    $(`s${field}`)?.addEventListener('change', () => syncBoundaryTimeControls('s'));
    $(`manage${field}`)?.addEventListener('change', () => syncBoundaryTimeControls('manage'));
  });
  $('sFirstHourS')?.addEventListener('change', () => syncBoundaryTimeControls('s', 'first'));
  $('sLastHourE')?.addEventListener('change', () => syncBoundaryTimeControls('s', 'last'));
  $('manageFirstHourS')?.addEventListener('change', () => syncBoundaryTimeControls('manage', 'first'));
  $('manageLastHourE')?.addEventListener('change', () => syncBoundaryTimeControls('manage', 'last'));

  const tagInput = $('tagInp');
  tagInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      addTag();
    }
    if (event.key === 'Backspace' && !event.target.value) removeLastTag();
  });
  tagInput.addEventListener('focus', () => $('tagWrap').classList.add('focused'));
  tagInput.addEventListener('blur', () => $('tagWrap').classList.remove('focused'));

  $('sPrompt').addEventListener('input', updatePromptCount);
  $('managePrompt')?.addEventListener('input', updateManagePromptCount);
  updatePromptCount();
  updateManagePromptCount();
}

async function createSession() {
  const name = $('sName').value.trim();
  const dateS = $('sDateS').value;
  const dateE = $('sDateE').value;
  const { hourS, hourE, firstHourS, lastHourE } = readTimeControls('s');
  const myName = $('sMyName').value.trim();
  const creatorPrompt = ($('sPrompt')?.value || '').trim().slice(0, 200);
  const createBtn = $('createBtn');

  if (!name) return toast('请输入活动名称');
  if (!dateS || !dateE) return toast('请选择日期');
  if (dateS > dateE) return toast('开始日期不能晚于结束日期');
  const timeError = validateTimeWindow(dateS, dateE, hourS, hourE, firstHourS, lastHourE);
  if (timeError) return toast(timeError);
  if (!myName) return toast('请输入你的昵称（发起人）');
  if (dayDiff(dateS, dateE) > 14) return toast('日期范围最多14天');

  createBtn.textContent = '创建中…';
  createBtn.disabled = true;

  try {
    const created = await requestJson('/api/session', {
      method: 'POST',
      body: {
        name,
        dateS,
        dateE,
        hourS,
        hourE,
        firstHourS,
        lastHourE,
        creatorName: myName,
        creatorPrompt,
        expectedNames: state.tags.filter(tag => tag !== myName),
      },
    });
    saveCreatorToken(created.id, created.creatorToken);

    const joined = await requestJson(`/api/session/${created.id}/join`, {
      method: 'POST',
      headers: sessionHeaders(created.id),
      body: { name: myName, color: COLORS[0] },
    });
    saveParticipantAccess(created.id, {
      participantId: joined.participantId,
      participantName: joined.participantName || myName,
      participantToken: joined.participantToken,
    });
    rememberLastName(myName);
    location.href = `/?s=${created.id}&auto_join=1`;
  } catch (error) {
    toast(getApiMessage(error, '创建失败，请重试'));
    createBtn.textContent = '创建调查并进入填写';
    createBtn.disabled = false;
  }
}

function focusTagInput(event) {
  if (!event.target.classList.contains('tag-x')) $('tagInp').focus();
}

function addTag() {
  const value = $('tagInp').value.trim();
  if (!value || state.tags.includes(value)) return;
  if (state.tags.length >= 12) return toast('最多12人');
  state.tags.push(value);
  $('tagInp').value = '';
  renderTags();
}

function removeTag(name) {
  state.tags = state.tags.filter(tag => tag !== name);
  renderTags();
}

function removeLastTag() {
  if (!state.tags.length) return;
  state.tags.pop();
  renderTags();
}

function renderTags() {
  $('tagWrap').querySelectorAll('.tag').forEach(node => node.remove());
  [...state.tags].reverse().forEach(tag => {
    const wrapper = document.createElement('div');
    wrapper.className = 'tag';
    wrapper.innerHTML = `${esc(tag)}<button class="tag-x" onclick="removeTag(decodeURIComponent('${encodeURIComponent(tag)}'))" type="button">×</button>`;
    $('tagWrap').insertBefore(wrapper, $('tagWrap').firstChild);
  });
}

function updatePromptCount() {
  const input = $('sPrompt');
  const value = (input.value || '').slice(0, 200);
  if (value !== input.value) input.value = value;
  $('sPromptCount').textContent = `${value.length}/200`;
}

function fillPromptTemplate(text) {
  $('sPrompt').value = String(text || '').slice(0, 200);
  updatePromptCount();
  $('sPrompt').focus();
}

function pickChip(element, name) {
  document.querySelectorAll('.nchip').forEach(node => node.classList.remove('active'));
  element.classList.add('active');
  state.pickedJoinName = name;
  $('jName').value = name;
}

async function joinSession() {
  const name = ($('jName').value.trim() || state.pickedJoinName || '').trim();
  if (!name) return toast('请选择或输入你的昵称');

  const existing = state.S.participants.find(item => item.name === name);
  const color = existing ? existing.color : getNextColor();

  try {
    const updated = await requestJson(`/api/session/${state.SID}/join`, {
      method: 'POST',
      headers: sessionHeaders(),
      body: { name, color },
    });
    saveParticipantAccess(state.SID, {
      participantId: updated.participantId,
      participantName: updated.participantName || name,
      participantToken: updated.participantToken,
    });
    applySession(updated.session);
    hydrateCurrentUser(updated.participantId, updated.participantName || name);
    applyUserViewDefaults();
    renderMainScreen();
    showScreen('mainScreen');
    startPoll();
    toast(existing ? `欢迎回来，${state.ME_NAME} 👋` : '点格子循环：有空（彩色）→ 没空（红✕）→ 不确定/未填（灰色）');
  } catch (error) {
    toast(getApiMessage(error, '加入失败，请重试'));
  }
}

async function resumeSession() {
  const saved = getSavedParticipantName(state.SID);
  if (!saved) return;
  $('jName').value = saved;
  await joinSession();
}

function viewOnly() {
  state.ME = null;
  state.ME_NAME = '';
  state.myAvail = {};
  state.myRemark = '';
  saveToHistory(state.SID, state.S.name, state.S.dateS, state.S.dateE);
  applyUserViewDefaults();
  renderMainScreen();
  showScreen('mainScreen');
  startPoll();
}

function switchUser() {
  stopPoll();
  state.ME = null;
  state.ME_NAME = '';
  state.myAvail = {};
  state.myRemark = '';
  renderJoin();
  showScreen('joinScreen');
}

function setLayout(mode) {
  state.layout = mode;
  $('btnTR').classList.toggle('active', mode === 'tr');
  $('btnPR').classList.toggle('active', mode === 'pr');
  renderGrid();
  attachEvents();
}

function setCollapseState(collapsed) {
  state.collapsed = Boolean(collapsed);
  updateCollapseButton();
  document.querySelectorAll('tr.other-row').forEach(row => row.classList.toggle('collapsed', state.collapsed));
  document.querySelectorAll('.other-col').forEach(node => {
    node.style.display = state.collapsed ? 'none' : '';
  });
  document.querySelectorAll('.toggle-btn-row td').forEach(cell => {
    cell.textContent = state.collapsed ? '展开其他人' : '收起其他人';
  });
}

function collapseOthers() {
  setCollapseState(true);
}

function expandOthers() {
  setCollapseState(false);
}

function toggleCollapse() {
  setCollapseState(!state.collapsed);
}

function onRemarkInput(event) {
  state.myRemark = (event?.target?.value || '').slice(0, 200);
  syncCurrentParticipant();
  updateRemarkCounter();
  updateRemarkHint('保存中…');
  clearTimeout(state.remarkSaveT);
  state.remarkSaveT = setTimeout(async () => {
    await saveAvail();
    updateRemarkHint('已保存');
  }, 350);
}

function attachEvents() {
  if (!state.ME) return;
  document.querySelectorAll('.ci.ed').forEach(cell => {
    cell.addEventListener('mousedown', onDown, { passive: false });
    cell.addEventListener('mouseenter', onEnter);
    cell.addEventListener('touchstart', onTouchStart, { passive: false });
    cell.addEventListener('touchmove', onTouchMove, { passive: false });
  });
}

function onDown(event) {
  event.preventDefault();
  startDrag(event.currentTarget);
}

function onTouchStart(event) {
  event.preventDefault();
  startDrag(event.currentTarget);
}

function onEnter(event) {
  if (!state.drag.on) return;
  const cell = event.currentTarget;
  if (Number(cell.dataset.col) !== state.drag.col) return;
  const key = `${cell.dataset.date}-${cell.dataset.hour}`;
  if (key === state.drag.lastKey) return;
  state.drag.lastKey = key;
  applyCell(cell.dataset.date, Number(cell.dataset.hour), state.drag.fillTo, cell);
}

function onTouchMove(event) {
  if (!state.drag.on) return;
  event.preventDefault();
  const cell = document.elementFromPoint(event.touches[0].clientX, event.touches[0].clientY)?.closest('.ci.ed');
  if (!cell || Number(cell.dataset.col) !== state.drag.col) return;
  const key = `${cell.dataset.date}-${cell.dataset.hour}`;
  if (key === state.drag.lastKey) return;
  state.drag.lastKey = key;
  applyCell(cell.dataset.date, Number(cell.dataset.hour), state.drag.fillTo, cell);
}

function startDrag(cell) {
  const date = cell.dataset.date;
  const hour = Number(cell.dataset.hour);
  const col = Number(cell.dataset.col);
  const current = getState(state.myAvail[date] || {}, hour);
  const next = (current + 1) % 3;
  state.drag = { on: true, fillTo: next, col, lastKey: `${date}-${hour}` };
  applyCell(date, hour, next, cell);
}

function applyCell(date, hour, status, cell) {
  if (!state.myAvail[date]) state.myAvail[date] = {};
  state.myAvail[date][String(hour)] = status;
  if (cell) {
    const me = getCurrentParticipant();
    cell.setAttribute('style', cellStyle(status, me?.color || '#07C160'));
    cell.textContent = status === ST_BUSY ? '✕' : '';
  }
}

function endDrag() {
  if (!state.drag.on) return;
  state.drag.on = false;
  syncCurrentParticipant();
  refreshSummary();
  clearTimeout(state.saveT);
  state.saveT = setTimeout(() => {
    void saveAvail();
  }, 400);
}

async function saveAvail() {
  if (!state.ME || !state.SID) return;
  try {
    await requestJson(`/api/session/${state.SID}/avail`, {
      method: 'PUT',
      headers: sessionHeaders(),
      body: { name: state.ME_NAME, avail: state.myAvail, remark: state.myRemark },
    });
  } catch (_) {
    updateRemarkHint('保存失败');
  }
}

function refreshSummary() {
  const participants = state.S.participants;
  const currentUserIndex = participants.findIndex(participant => participant.id === state.ME);
  const maxParticipants = participants.length;

  getDates(state.S).forEach(date => {
    const myDayAvail = state.ME ? (state.myAvail[date] || {}) : {};
    getHours(state.S).forEach(hour => {
      if (!isSlotEnabled(state.S, date, hour)) return;
      const summary = getSlotSummary(participants, currentUserIndex, myDayAvail, date, hour);
      const row = document.querySelector(`table.sg.m-tr[data-date="${date}"] tr[data-h="${hour}"] .si`);
      if (row) row.outerHTML = buildSummaryCell(summary.availableCount, summary.busyCount, maxParticipants, summary);
    });

    if (state.layout === 'pr') {
      const summaryRow = document.querySelector(`tr.sum-row[data-date="${date}"]`);
      if (summaryRow) {
        const cells = summaryRow.querySelectorAll('td.td-h');
        getHours(state.S).forEach((hour, index) => {
          if (!isSlotEnabled(state.S, date, hour)) return;
          const summary = getSlotSummary(participants, currentUserIndex, state.myAvail[date] || {}, date, hour);
          if (cells[index]) cells[index].innerHTML = buildSummaryCell(summary.availableCount, summary.busyCount, maxParticipants, summary);
        });
      }

      participants.forEach((participant, index) => {
        const cell = document.querySelector(`table.sg.m-pr[data-date="${date}"] tr[data-pi="${index}"] .td-psum .si`);
        if (!cell) return;
        const avail = index === currentUserIndex ? (state.myAvail[date] || {}) : (participant.avail[date] || {});
        const availableCount = getHours(state.S).filter(hour => isSlotEnabled(state.S, date, hour) && getState(avail, hour) === ST_AVAIL).length;
        const style = availableCount > 0 ? 'background:#E8F8F0;color:#0F766E' : 'background:#F5F5F5;color:#CBD5E1';
        cell.setAttribute('style', style);
        cell.innerHTML = `${availableCount > 0 ? availableCount : ''}${participant.isRequired ? '<span class="si-person-tag">关键</span>' : ''}`;
      });
    }
  });
}

function startPoll() {
  stopPoll();
  state.pollT = setInterval(() => {
    void doPoll();
  }, 3000);
}

function stopPoll() {
  clearInterval(state.pollT);
  state.pollT = null;
}

async function doPoll() {
  if (state.drag.on || !state.SID) return;
  let freshSession;
  try {
    freshSession = await requestJson(`/api/session/${state.SID}`, { headers: sessionHeaders() });
  } catch (_) {
    return;
  }
  const previousCount = state.S.participants.length;
  const previousViewerId = state.ME;
  applySession(freshSession);

  if (previousViewerId && !state.ME) {
    toast('你已不在这张表中，当前切换为查看模式');
    renderMainScreen();
    return;
  }

  if (state.ME) {
    const current = getCurrentParticipant();
    if (current) {
      state.ME_NAME = current.name;
      if (!state.drag.on) {
        state.myAvail = clone(current.avail || {});
        state.myRemark = (current.remark || '').slice(0, 200);
      }
    }
  }

  if (state.S.participants.length !== previousCount) {
    renderMainScreen();
    return;
  }

  renderMainScreen();
}

function showTutorial() {
  state.tutorialStep = 0;
  showTutorialStep();
  $('tutorialOverlay').classList.add('show');
}

function showTutorialStep() {
  const step = TUTORIAL_STEPS[state.tutorialStep];
  $('tutStep').textContent = step.emoji;
  $('tutTitle').textContent = step.title;
  $('tutDesc').textContent = step.desc;
  const button = $('tutBtn');
  button.textContent = state.tutorialStep < TUTORIAL_STEPS.length - 1 ? '下一步 →' : '开始使用';
  button.onclick = () => {
    if (state.tutorialStep < TUTORIAL_STEPS.length - 1) {
      state.tutorialStep += 1;
      showTutorialStep();
      return;
    }
    skipTutorial();
  };
}

function skipTutorial() {
  $('tutorialOverlay').classList.remove('show');
  localStorage.setItem('mqa_tutorial_done', 'true');
}

async function openAISummary() {
  if (!state.SID) return toast('无法获取会话信息');
  $('aiSummaryOverlay').classList.add('open');
  $('aiContent').innerHTML = '<div class="ai-loading">生成中</div>';
  try {
    const response = await requestJson(`/api/session/${state.SID}/summary`);
    $('aiContent').innerHTML = renderAISummary(response.summary);
  } catch (error) {
    $('aiContent').innerHTML = `<div class="ai-item-text">${getApiMessage(error, '生成失败，请稍后重试。')}</div>`;
  }
}

function closeAISummary() {
  $('aiSummaryOverlay').classList.remove('open');
}

function overlayBgAI(event) {
  if (event.target === $('aiSummaryOverlay')) closeAISummary();
}

function getShareUrl() {
  return `${location.origin}/?s=${state.SID}`;
}

function openShare() {
  $('shUrl').textContent = getShareUrl();
  $('shPeopleStat').textContent = `当前已有 ${state.S.participants.length} 人填写数据。`;
  $('shareOverlay').classList.add('open');
}

function closeShare() {
  $('shareOverlay').classList.remove('open');
}

function overlayBg(event) {
  if (event.target === $('shareOverlay')) closeShare();
}

function copyUrl() {
  const url = getShareUrl();
  const done = () => {
    toast('已复制，发到群里即可');
    closeShare();
  };
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(url).then(done).catch(() => fallbackCopy(url, done));
    return;
  }
  fallbackCopy(url, done);
}

function fallbackCopy(url, callback) {
  const textarea = Object.assign(document.createElement('textarea'), { value: url });
  textarea.style.cssText = 'position:fixed;opacity:0;top:0;left:0;width:1px;height:1px';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    document.execCommand('copy');
    callback();
  } catch (_) {
    toast('请长按链接手动复制');
  }
  textarea.remove();
}

function renderManageParticipants() {
  const list = $('manageParticipantsList');
  if (!list) return;
  list.innerHTML = state.manageParticipants.map(participant => `
    <div class="manage-participant-row">
      <span class="manage-participant-dot" style="background:${participant.color}"></span>
      <input class="fi manage-participant-input" type="text" maxlength="10" value="${esc(participant.name)}"
        oninput="updateManageParticipantName('${participant.id}', this.value)">
      <label class="manage-required-toggle">
        <input type="checkbox" ${participant.isRequired ? 'checked' : ''} onchange="updateManageParticipantRequired('${participant.id}', this.checked)">
        <span>关键成员</span>
      </label>
      <button class="btn-s manage-row-remove" type="button" onclick="removeManageParticipant('${participant.id}')">移除</button>
    </div>
  `).join('');
}

function updateManagePromptCount() {
  const input = $('managePrompt');
  const value = (input?.value || '').slice(0, 200);
  if (input && value !== input.value) input.value = value;
  $('managePromptCount').textContent = `${value.length}/200`;
}

function addManageParticipant() {
  const next = {
    id: `tmp_${Date.now()}_${state.manageParticipants.length}`,
    name: '',
    color: COLORS[state.manageParticipants.length % COLORS.length],
    isRequired: false,
  };
  state.manageParticipants.push(next);
  renderManageParticipants();
}

function updateManageParticipantName(id, name) {
  state.manageParticipants = state.manageParticipants.map(participant => (
    participant.id === id ? { ...participant, name: String(name || '').slice(0, 10) } : participant
  ));
}

function updateManageParticipantRequired(id, isRequired) {
  state.manageParticipants = state.manageParticipants.map(participant => (
    participant.id === id ? { ...participant, isRequired: Boolean(isRequired) } : participant
  ));
}

function removeManageParticipant(id) {
  state.manageParticipants = state.manageParticipants.filter(participant => participant.id !== id);
  renderManageParticipants();
}

function openManageSession() {
  if (!state.S?.capabilities?.canManageSession) return toast('只有创建者可以管理整张表');
  $('manageName').value = state.S.name || '';
  $('manageDateS').value = state.S.dateS || '';
  $('manageDateE').value = state.S.dateE || '';
  $('manageHourS').value = state.S.hourS;
  $('manageHourE').value = state.S.hourE;
  syncBoundaryTimeControls('manage');
  $('manageFirstHourS').value = String(state.S.firstHourS ?? state.S.hourS);
  $('manageLastHourE').value = String(state.S.lastHourE ?? state.S.hourE);
  syncBoundaryTimeControls('manage');
  $('managePrompt').value = state.S.creatorPrompt || '';
  $('manageExpectedNames').value = (state.S.expectedNames || []).join('\n');
  state.manageParticipants = state.S.participants.map(participant => ({
    id: participant.id,
    name: participant.name,
    color: participant.color,
    isRequired: Boolean(participant.isRequired),
  }));
  updateManagePromptCount();
  renderManageParticipants();
  $('manageOverlay').classList.add('open');
}

function closeManageSession() {
  $('manageOverlay').classList.remove('open');
}

function overlayBgManage(event) {
  if (event.target === $('manageOverlay')) closeManageSession();
}

function parseNameList(value) {
  return String(value || '')
    .split(/[\n,，]/)
    .map(item => item.trim())
    .filter(Boolean);
}

async function saveManagedSession() {
  try {
    const dateS = $('manageDateS').value;
    const dateE = $('manageDateE').value;
    const { hourS, hourE, firstHourS, lastHourE } = readTimeControls('manage');
    const timeError = validateTimeWindow(dateS, dateE, hourS, hourE, firstHourS, lastHourE);
    if (timeError) return toast(timeError);

    const payload = {
      name: $('manageName').value.trim(),
      dateS,
      dateE,
      hourS,
      hourE,
      firstHourS,
      lastHourE,
      creatorPrompt: ($('managePrompt').value || '').trim().slice(0, 200),
      expectedNames: parseNameList($('manageExpectedNames').value),
      participants: state.manageParticipants.map(participant => ({
        id: participant.id.startsWith('tmp_') ? '' : participant.id,
        name: participant.name.trim(),
        color: participant.color,
        isRequired: Boolean(participant.isRequired),
      })),
    };
    const updated = await requestJson(`/api/session/${state.SID}`, {
      method: 'PATCH',
      headers: sessionHeaders(),
      body: payload,
    });
    applySession(updated.session);
    if (state.ME) hydrateCurrentUser(state.ME, state.ME_NAME);
    renderMainScreen();
    renderJoin();
    closeManageSession();
    toast('表格已更新');
  } catch (error) {
    toast(getApiMessage(error, '保存失败，请重试'));
  }
}

async function deleteCurrentSession() {
  if (!state.S?.capabilities?.canDeleteSession) return toast('只有创建者可以删除整张表');
  if (!window.confirm('确认删除整张表？此操作无法撤销。')) return;
  try {
    await requestJson(`/api/session/${state.SID}`, {
      method: 'DELETE',
      headers: sessionHeaders(),
    });
    clearSessionAccess(state.SID);
    removeHistoryItem(state.SID);
    toast('表格已删除');
    setTimeout(() => { location.href = '/'; }, 500);
  } catch (error) {
    toast(getApiMessage(error, '删除失败，请重试'));
  }
}

async function leaveCurrentSession() {
  const access = getSessionAccess(state.SID);
  const participantId = state.S?.viewer?.participantId || access.participantId;
  if (!participantId) return toast('当前没有可退出的参与身份');
  if (!window.confirm('确认从这张表中退出吗？')) return;
  try {
    await requestJson(`/api/session/${state.SID}/participants/${participantId}`, {
      method: 'DELETE',
      headers: sessionHeaders(),
    });
    clearParticipantAccess(state.SID);
    state.ME = null;
    state.ME_NAME = '';
    state.myAvail = {};
    state.myRemark = '';
    const fresh = await requestJson(`/api/session/${state.SID}`, { headers: sessionHeaders() });
    applySession(fresh);
    renderJoin();
    showScreen('joinScreen');
    toast('你已退出这张表');
  } catch (error) {
    toast(getApiMessage(error, '退出失败，请重试'));
  }
}

async function deleteSessionFromHistory(sid) {
  if (!window.confirm('确认删除这张表？此操作无法撤销。')) return;
  try {
    await requestJson(`/api/session/${sid}`, {
      method: 'DELETE',
      headers: sessionHeaders(sid),
    });
    clearSessionAccess(sid);
    removeHistoryItem(sid);
    renderHistoryScreen();
    renderHistoryCard();
    toast('表格已删除');
  } catch (error) {
    toast(getApiMessage(error, '删除失败，请重试'));
  }
}

async function leaveSessionFromHistory(sid) {
  const access = getSessionAccess(sid);
  if (!access.participantId) return toast('当前没有可退出的参与身份');
  if (!window.confirm('确认退出这张表吗？')) return;
  try {
    await requestJson(`/api/session/${sid}/participants/${access.participantId}`, {
      method: 'DELETE',
      headers: sessionHeaders(sid),
    });
    clearParticipantAccess(sid);
    renderHistoryScreen();
    renderHistoryCard();
    toast('已退出该表格');
  } catch (error) {
    toast(getApiMessage(error, '退出失败，请重试'));
  }
}

async function init() {
  document.addEventListener('mouseup', endDrag);
  document.addEventListener('touchend', endDrag);

  const params = new URLSearchParams(location.search);
  state.SID = params.get('s');
  state.AUTO_JOIN = params.get('auto_join') === '1';
  state.userPrefs = getUserPreferences();
  state.settingsDraft = { ...state.userPrefs };
  applyUserViewDefaults();
  initForm();

  if (state.SID) {
    try {
      applySession(await requestJson(`/api/session/${state.SID}`, { headers: sessionHeaders() }));
      if (state.AUTO_JOIN && restoreParticipant(true)) return;
      renderJoin();
      showScreen('joinScreen');
    } catch (_) {
      toast('会话不存在或已过期');
      setTimeout(() => { location.href = '/'; }, 2000);
    }
    return;
  }

  showHome();
}

Object.assign(window, {
  addTag,
  closeAISummary,
  closeUserSettings,
  closeShare,
  copyUrl,
  createSession,
  fillPromptTemplate,
  focusTagInput,
  goToHistory,
  goToHome,
  goToSession,
  goToSetup,
  leaveCurrentSession,
  leaveSessionFromHistory,
  joinSession,
  openManageSession,
  openAISummary,
  openShare,
  openUserSettings,
  overlayBg,
  overlayBgAI,
  overlayBgManage,
  overlayBgSettings,
  pickChip,
  expandOthers,
  collapseOthers,
  removeManageParticipant,
  removeTag,
  resumeSession,
  saveManagedSession,
  saveUserViewPreferences,
  setLayout,
  setSettingsCollapse,
  setSettingsLayout,
  showTutorial,
  skipTutorial,
  switchUser,
  toggleCollapse,
  updateManageParticipantName,
  updateManageParticipantRequired,
  viewOnly,
  addManageParticipant,
  closeManageSession,
  deleteCurrentSession,
  deleteSessionFromHistory,
});

void init();
