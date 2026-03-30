import { requestJson, ApiError } from './api.js';
import { COLORS, ST_AVAIL, ST_BUSY, TUTORIAL_STEPS } from './constants.js';
import { getLastName, getSavedParticipantName, rememberLastName, saveParticipantName, saveToHistory } from './history.js';
import { $, clone, dayDiff, dfmt, esc, getDates, getHours, getState, normalizeAvail, showScreen, toast } from './helpers.js';
import { buildSummaryCell, cellStyle, getNextColor, renderGrid, renderHistoryCard, renderHistoryScreen, renderJoin, renderMain, updateCollapseButton, updateRemarkCounter, updateRemarkHint } from './render.js';
import { renderAISummary } from './summary.js';
import { state } from './state.js';

function getApiMessage(error, fallback) {
  if (error instanceof ApiError) return error.message || fallback;
  return fallback;
}

function hydrateCurrentUser(name) {
  state.ME = name;
  const participant = state.S?.participants?.find(item => item.name === state.ME);
  state.myAvail = participant?.avail ? clone(participant.avail) : {};
  state.myRemark = (participant?.remark || '').slice(0, 200);
  saveParticipantName(state.SID, state.ME);
  saveToHistory(state.SID, state.S.name, state.S.dateS, state.S.dateE);
}

function restoreParticipant(autoEnter = false) {
  const savedName = getSavedParticipantName(state.SID);
  const savedParticipant = savedName && state.S?.participants?.find(item => item.name === savedName);
  if (!savedParticipant) return false;
  hydrateCurrentUser(savedName);
  if (autoEnter) {
    renderMainScreen();
    showScreen('mainScreen');
    startPoll();
  }
  return true;
}

function syncCurrentParticipant() {
  if (!state.ME || !state.S) return;
  const participant = state.S.participants.find(item => item.name === state.ME);
  if (!participant) return;
  participant.avail = clone(state.myAvail);
  participant.remark = state.myRemark;
}

function renderMainScreen() {
  renderMain();
  bindRemarkInput();
  attachEvents();
}

function bindRemarkInput() {
  const remark = $('myRemark');
  if (remark) remark.oninput = onRemarkInput;
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
  for (let hour = 0; hour <= 23; hour += 1) {
    [startSelect, endSelect].forEach(select => {
      const option = document.createElement('option');
      option.value = hour;
      option.textContent = `${String(hour).padStart(2, '0')}:00`;
      select.appendChild(option);
    });
  }

  startSelect.value = 9;
  endSelect.value = 21;
  const now = new Date();
  const later = new Date(now);
  later.setDate(now.getDate() + 3);
  $('sDateS').value = dfmt(now);
  $('sDateE').value = dfmt(later);
  $('sMyName').value = getLastName();

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
  updatePromptCount();
}

async function createSession() {
  const name = $('sName').value.trim();
  const dateS = $('sDateS').value;
  const dateE = $('sDateE').value;
  const hourS = Number($('sHourS').value);
  const hourE = Number($('sHourE').value);
  const myName = $('sMyName').value.trim();
  const creatorPrompt = ($('sPrompt')?.value || '').trim().slice(0, 200);
  const createBtn = $('createBtn');

  if (!name) return toast('请输入活动名称');
  if (!dateS || !dateE) return toast('请选择日期');
  if (dateS > dateE) return toast('开始日期不能晚于结束日期');
  if (hourS >= hourE) return toast('截止时间须晚于起始时间');
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
        creatorPrompt,
        expectedNames: state.tags.filter(tag => tag !== myName),
      },
    });

    await requestJson(`/api/session/${created.id}/join`, {
      method: 'POST',
      body: { name: myName, color: COLORS[0] },
    });
    rememberLastName(myName);
    saveParticipantName(created.id, myName);
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
      body: { name, color },
    });
    state.S = updated;
    state.S.participants.forEach(participant => {
      participant.avail = normalizeAvail(participant.avail);
    });
    hydrateCurrentUser(name);
    renderMainScreen();
    showScreen('mainScreen');
    startPoll();
    toast(existing ? `欢迎回来，${state.ME} 👋` : '点格子循环：有空（彩色）→ 没空（红✕）→ 不确定/未填（灰色）');
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
  state.myAvail = {};
  state.myRemark = '';
  saveToHistory(state.SID, state.S.name, state.S.dateS, state.S.dateE);
  renderMainScreen();
  showScreen('mainScreen');
  startPoll();
}

function switchUser() {
  stopPoll();
  state.ME = null;
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

function toggleCollapse() {
  state.collapsed = !state.collapsed;
  updateCollapseButton();
  document.querySelectorAll('tr.other-row').forEach(row => row.classList.toggle('collapsed', state.collapsed));
  document.querySelectorAll('.other-col').forEach(node => {
    node.style.display = state.collapsed ? 'none' : '';
  });
  document.querySelectorAll('.toggle-btn-row td').forEach(cell => {
    cell.textContent = state.collapsed ? '展开其他人' : '收起其他人';
  });
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
    const me = state.S.participants.find(participant => participant.name === state.ME);
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
      body: { name: state.ME, avail: state.myAvail, remark: state.myRemark },
    });
  } catch (_) {
    updateRemarkHint('保存失败');
  }
}

function refreshSummary() {
  const participants = state.S.participants;
  const currentUserIndex = participants.findIndex(participant => participant.name === state.ME);
  const maxParticipants = participants.length;

  getDates(state.S).forEach(date => {
    const myDayAvail = state.ME ? (state.myAvail[date] || {}) : {};
    getHours(state.S).forEach(hour => {
      const states = participants.map((participant, index) => getState(index === currentUserIndex ? myDayAvail : (participant.avail[date] || {}), hour));
      const availableCount = states.filter(value => value === ST_AVAIL).length;
      const busyCount = states.filter(value => value === ST_BUSY).length;
      const row = document.querySelector(`table.sg.m-tr[data-date="${date}"] tr[data-h="${hour}"] .si`);
      if (row) row.outerHTML = buildSummaryCell(availableCount, busyCount, maxParticipants);
    });

    if (state.layout === 'pr') {
      const summaryRow = document.querySelector(`tr.sum-row[data-date="${date}"]`);
      if (summaryRow) {
        const cells = summaryRow.querySelectorAll('td.td-h');
        getHours(state.S).forEach((hour, index) => {
          const states = participants.map((participant, participantIndex) => getState(participantIndex === currentUserIndex ? (state.myAvail[date] || {}) : (participant.avail[date] || {}), hour));
          const availableCount = states.filter(value => value === ST_AVAIL).length;
          const busyCount = states.filter(value => value === ST_BUSY).length;
          if (cells[index]) cells[index].innerHTML = buildSummaryCell(availableCount, busyCount, maxParticipants);
        });
      }

      participants.forEach((participant, index) => {
        const cell = document.querySelector(`table.sg.m-pr[data-date="${date}"] tr[data-pi="${index}"] .td-psum .si`);
        if (!cell) return;
        const avail = index === currentUserIndex ? (state.myAvail[date] || {}) : (participant.avail[date] || {});
        const availableCount = getHours(state.S).filter(hour => getState(avail, hour) === ST_AVAIL).length;
        const style = availableCount > 0 ? 'background:#E8F8F0;color:#0F766E' : 'background:#F5F5F5;color:#CBD5E1';
        cell.setAttribute('style', style);
        cell.textContent = availableCount > 0 ? availableCount : '';
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
    freshSession = await requestJson(`/api/session/${state.SID}`);
  } catch (_) {
    return;
  }

  const previousCount = state.S.participants.length;
  freshSession.participants.forEach(participant => {
    participant.avail = normalizeAvail(participant.avail);
    if (participant.name === state.ME) return;
    const existing = state.S.participants.find(item => item.name === participant.name);
    if (existing) {
      existing.avail = participant.avail;
      existing.remark = participant.remark || '';
    } else {
      state.S.participants.push({ ...participant });
    }
  });

  if (state.S.participants.length > previousCount) {
    toast(`${state.S.participants[state.S.participants.length - 1].name} 加入了`);
    renderMainScreen();
    return;
  }

  state.S.participants.forEach((participant, index) => {
    if (participant.name === state.ME) return;
    getDates(state.S).forEach(date => {
      getHours(state.S).forEach(hour => {
        const status = getState(participant.avail[date] || {}, hour);
        const cell = document.querySelector(`.ci[data-pi="${index}"][data-date="${date}"][data-hour="${hour}"]`);
        if (!cell) return;
        cell.setAttribute('style', cellStyle(status, participant.color));
        cell.textContent = status === ST_BUSY ? '✕' : '';
      });
    });
  });
  refreshSummary();
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

function openShare() {
  $('shUrl').textContent = location.href;
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
  const url = location.href;
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

async function init() {
  document.addEventListener('mouseup', endDrag);
  document.addEventListener('touchend', endDrag);

  const params = new URLSearchParams(location.search);
  state.SID = params.get('s');
  state.AUTO_JOIN = params.get('auto_join') === '1';

  if (state.SID) {
    try {
      state.S = await requestJson(`/api/session/${state.SID}`);
      state.S.participants.forEach(participant => {
        participant.avail = normalizeAvail(participant.avail);
      });
      if (state.AUTO_JOIN && restoreParticipant(true)) return;
      renderJoin();
      showScreen('joinScreen');
    } catch (_) {
      toast('会话不存在或已过期');
      setTimeout(() => { location.href = '/'; }, 2000);
    }
    return;
  }

  initForm();
  showHome();
}

Object.assign(window, {
  addTag,
  closeAISummary,
  closeShare,
  copyUrl,
  createSession,
  fillPromptTemplate,
  focusTagInput,
  goToHistory,
  goToHome,
  goToSession,
  goToSetup,
  joinSession,
  openAISummary,
  openShare,
  overlayBg,
  overlayBgAI,
  pickChip,
  removeTag,
  resumeSession,
  setLayout,
  showTutorial,
  skipTutorial,
  switchUser,
  toggleCollapse,
  viewOnly,
});

void init();
