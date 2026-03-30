import { COLORS, ST_AVAIL, ST_BUSY, WD } from './constants.js';
import { loadHistory, getLastName, getSavedParticipantName } from './history.js';
import { state } from './state.js';
import { $, esc, fmtRange, getDates, getHours, getState, lerp, pad } from './helpers.js';

export function renderHistoryCard() {
  const history = loadHistory();
  if (history.length > 0) {
    $('historyCard').classList.remove('hidden');
    $('historyList').innerHTML = history.slice(0, 3).map(item => (
      `<button class="history-mini-item" type="button" onclick="event.stopPropagation(); goToSession('${item.id}')">${esc(item.name)} <span>${item.dateS}</span></button>`
    )).join('');
    $('historyDesc').textContent = `${history.length} 个最近的表格`;
    return;
  }
  $('historyCard').classList.add('hidden');
}

export function renderHistoryScreen() {
  const history = loadHistory();
  $('historyListFull').innerHTML = history.length > 0
    ? history.map(item => `<button class="history-entry" type="button" onclick="goToSession('${item.id}')">
        <span class="history-entry-copy">
          <span class="history-entry-title">${esc(item.name)}</span>
          <span class="history-entry-meta">${item.dateS} — ${item.dateE}</span>
        </span>
      </button>`).join('')
    : '<div class="history-entry-meta" style="text-align:center;padding:20px">还没有历史记录呢</div>';
}

export function updateCollapseButton() {
  $('btnCollapse').textContent = state.collapsed ? '展开他人' : '折叠他人';
  $('btnCollapse').classList.toggle('active', !state.collapsed);
}

export function renderJoin() {
  $('jEvName').textContent = state.S.name;
  $('jEvMeta').textContent = fmtRange(state.S) + (state.S.participants.length ? ` · 已有 ${state.S.participants.length} 人填写` : ' · 快来第一个填！');
  renderCreatorPrompt('join');

  const savedName = getSavedParticipantName(state.SID);
  const savedParticipant = savedName && state.S.participants.find(participant => participant.name === savedName);
  if (savedParticipant) {
    $('jResumeName').textContent = savedName;
    $('jResumeArea').classList.remove('hidden');
  } else {
    $('jResumeArea').classList.add('hidden');
  }

  const expectedNames = state.S.expectedNames || [];
  if (expectedNames.length) {
    $('jChipsArea').classList.remove('hidden');
    $('jChips').innerHTML = expectedNames.map(name => {
      const filled = state.S.participants.find(participant => participant.name === name);
      return `<div class="nchip${filled ? ' done' : ''}" onclick="${filled ? '' : `pickChip(this, decodeURIComponent('${encodeURIComponent(name)}'))`}">${esc(name)}${filled ? ' ✓' : ''}</div>`;
    }).join('');
  } else {
    $('jChipsArea').classList.add('hidden');
  }

  state.pickedJoinName = null;
  $('jName').value = getLastName();
}

export function renderMain() {
  $('mTitle').textContent = state.S.name;
  $('mSub').innerHTML = `<span class="live-dot"></span>${fmtRange(state.S)}${state.ME ? ' · 点击切换状态' : ' · 查看模式'}`;
  renderBadges();
  renderCreatorPrompt('main');

  if (state.ME) {
    $('tipBox').textContent = '💡 点格子循环切换：有空（彩色）→ 没空（红✕）→ 不确定/未填（灰色）。上下拖可批量填。';
    $('tipBox').classList.remove('hidden');
  } else {
    $('tipBox').classList.add('hidden');
  }

  renderRemarkCard();
  updateCollapseButton();
  renderGrid();
}

export function renderRemarkCard() {
  const card = $('remarkCard');
  const input = $('myRemark');
  if (!state.ME) {
    card.classList.add('hidden');
    return;
  }
  card.classList.remove('hidden');
  input.value = state.myRemark || '';
  updateRemarkCounter();
  updateRemarkHint('自动保存');
}

export function updateRemarkCounter() {
  $('remarkCount').textContent = `${(state.myRemark || '').length}/200`;
}

export function updateRemarkHint(text) {
  $('remarkSaveHint').textContent = text;
}

export function renderBadges() {
  $('statsStrip').innerHTML = `<span class="s-lbl">参与者（${state.S.participants.length}人）：</span><div class="pbadges">${
    state.S.participants.map(participant => {
      const isMe = participant.name === state.ME;
      return `<span class="pbadge${isMe ? ' me' : ''}"><span class="pdot" style="background:${participant.color}"></span>${esc(participant.name)}${isMe ? '（我）' : ''}</span>`;
    }).join('')
  }</div>`;
}

export function renderCreatorPrompt(place) {
  const prompt = (state.S?.creatorPrompt || '').trim();
  if (place === 'join') {
    if (!prompt) {
      $('jPromptCard').classList.add('hidden');
      return;
    }
    $('jPromptText').textContent = prompt;
    $('jPromptCard').classList.remove('hidden');
    return;
  }

  if (!prompt) {
    $('mPromptCard').classList.add('hidden');
    return;
  }
  $('mPromptText').textContent = prompt;
  $('mPromptCard').classList.remove('hidden');
}

export function renderGrid() {
  const scrollTop = window.scrollY;
  $('gridContent').innerHTML = getDates(state.S).map(renderDay).join('');
  window.scrollTo(0, scrollTop);
}

function renderDay(date) {
  const currentDate = new Date(`${date}T00:00:00`);
  const weekday = WD[currentDate.getDay()];
  const isWeekend = currentDate.getDay() === 0 || currentDate.getDay() === 6;
  const inner = state.layout === 'tr' ? renderDayByTime(date) : renderDayByParticipant(date);
  return `<div class="day-sec">
    <div class="day-hdr">
      <span class="day-date">${currentDate.getMonth() + 1}月${currentDate.getDate()}日</span>
      <span class="day-wd${isWeekend ? ' we' : ''}">${weekday}${isWeekend ? ' 🎉' : ''}</span>
    </div>
    <div class="g-card"><div class="g-scroll">${inner}</div></div>
  </div>`;
}

function renderDayByTime(date) {
  const participants = state.S.participants;
  const currentUserIndex = state.ME ? participants.findIndex(participant => participant.name === state.ME) : -1;
  const hours = getHours(state.S);
  const myDayAvail = state.ME ? (state.myAvail[date] || {}) : {};

  const headColumns = participants.map((participant, index) => {
    const isMe = index === currentUserIndex;
    const isOther = !isMe;
    return `<th class="th-p${isMe ? ' is-me' : ''}${isOther ? ' other-col' : ''}" ${isOther && state.collapsed ? 'style="display:none"' : ''}>
      <span class="pname">${esc(participant.name)}${isMe ? ' ✏' : ''}</span>
      <span class="pmark" style="background:${participant.color}"></span>
    </th>`;
  }).join('');

  const rows = hours.map(hour => {
    const states = participants.map((participant, index) => getState(index === currentUserIndex ? myDayAvail : (participant.avail[date] || {}), hour));
    const availableCount = states.filter(value => value === ST_AVAIL).length;
    const busyCount = states.filter(value => value === ST_BUSY).length;

    const cells = participants.map((participant, index) => {
      const isMe = index === currentUserIndex;
      const isOther = !isMe;
      const status = states[index];
      const cellClass = `ci${isMe ? ' ed' : ' ro'}${isOther && state.ME ? ' dim' : ''}`;
      const dataAttrs = isMe
        ? ` data-date="${date}" data-hour="${hour}" data-col="${index}"`
        : ` data-pi="${index}" data-date="${date}" data-hour="${hour}"`;
      return `<td class="td-c${isOther ? ' other-col' : ''}" ${isOther && state.collapsed ? 'style="display:none"' : ''}>
        <div class="${cellClass}" style="${cellStyle(status, participant.color)}"${dataAttrs}>${status === ST_BUSY ? '✕' : ''}</div>
      </td>`;
    }).join('');

    return `<tr data-date="${date}" data-h="${hour}">
      <td class="td-lbl">${pad(hour)}:00<small>— ${pad(hour + 1)}:00</small></td>
      ${cells}
      <td class="td-sum">${buildSummaryCell(availableCount, busyCount, participants.length)}</td>
    </tr>`;
  }).join('');

  const otherCount = participants.filter((_, index) => index !== currentUserIndex).length;
  const toggleRow = otherCount > 0
    ? `<tr class="toggle-btn-row" onclick="toggleCollapse()"><td colspan="${participants.length + 2}">${state.collapsed ? '展开其他人' : '收起其他人'}</td></tr>`
    : '';

  return `<table class="sg m-tr" data-date="${date}">
    <thead><tr><th class="th-lbl">时段</th>${headColumns}<th class="th-sum">汇总</th></tr></thead>
    <tbody>${rows}${toggleRow}</tbody>
  </table>`;
}

function renderDayByParticipant(date) {
  const participants = state.S.participants;
  const currentUserIndex = state.ME ? participants.findIndex(participant => participant.name === state.ME) : -1;
  const hours = getHours(state.S);
  const myDayAvail = state.ME ? (state.myAvail[date] || {}) : {};

  const headHours = hours.map(hour => `<th class="th-h">${pad(hour)}<br><span style="font-size:9px;color:#bbb">—${pad(hour + 1)}</span></th>`).join('');

  const rows = participants.map((participant, index) => {
    const isMe = index === currentUserIndex;
    const isOther = !isMe;
    const avail = isMe ? myDayAvail : (participant.avail[date] || {});
    const availableCount = hours.filter(hour => getState(avail, hour) === ST_AVAIL).length;
    const sumStyle = availableCount > 0 ? 'background:#E8F8F0;color:#0F766E' : 'background:#F5F5F5;color:#CBD5E1';

    const cells = hours.map(hour => {
      const status = getState(avail, hour);
      const cellClass = `ci${isMe ? ' ed' : ' ro'}${isOther && state.ME ? ' dim' : ''}`;
      const dataAttrs = isMe
        ? ` data-date="${date}" data-hour="${hour}" data-col="${index}"`
        : ` data-pi="${index}" data-date="${date}" data-hour="${hour}"`;
      return `<td class="td-h${isOther ? ' other-col' : ''}" ${isOther && state.collapsed ? 'style="display:none"' : ''}>
        <div class="${cellClass}" style="${cellStyle(status, participant.color)}"${dataAttrs}>${status === ST_BUSY ? '✕' : ''}</div>
      </td>`;
    }).join('');

    return `<tr data-date="${date}" data-pi="${index}"${isOther ? ` class="other-row${state.collapsed ? ' collapsed' : ''}"` : ''}>
      <td class="td-plbl">
        <span class="pn${isMe ? ' is-me' : ''}">${esc(participant.name)}${isMe ? ' ✏' : ''}</span>
        <span class="pm" style="background:${participant.color}"></span>
      </td>
      ${cells}
      <td class="td-psum${isOther ? ' other-col' : ''}" ${isOther && state.collapsed ? 'style="display:none"' : ''}>
        <div class="si" style="${sumStyle}">${availableCount > 0 ? availableCount : ''}</div>
      </td>
    </tr>`;
  }).join('');

  const summaryRow = hours.map(hour => {
    const states = participants.map((participant, index) => getState(index === currentUserIndex ? myDayAvail : (participant.avail[date] || {}), hour));
    const availableCount = states.filter(value => value === ST_AVAIL).length;
    const busyCount = states.filter(value => value === ST_BUSY).length;
    return `<td class="td-h">${buildSummaryCell(availableCount, busyCount, participants.length)}</td>`;
  }).join('');

  const otherCount = participants.filter((_, index) => index !== currentUserIndex).length;
  const toggleRow = otherCount > 0
    ? `<tr class="toggle-btn-row" onclick="toggleCollapse()"><td colspan="${hours.length + 2}">${state.collapsed ? '展开其他人' : '收起其他人'}</td></tr>`
    : '';

  return `<table class="sg m-pr" data-date="${date}">
    <thead><tr><th class="th-lbl2">人员</th>${headHours}<th class="th-sum2">小计</th></tr></thead>
    <tbody>
      ${rows}
      ${toggleRow}
      <tr class="sum-row" data-date="${date}">
        <td class="td-plbl"><span class="pn" style="color:var(--t3)">汇总</span></td>
        ${summaryRow}
        <td class="td-psum"></td>
      </tr>
    </tbody>
  </table>`;
}

export function cellStyle(status, color) {
  if (status === ST_AVAIL) return `background:${color};color:transparent;`;
  if (status === ST_BUSY) return 'background:#FFF0F0;color:#FF4D4F;';
  return 'background:#EFF0F2;color:transparent;';
}

export function buildSummaryCell(availableCount, busyCount, participantCount) {
  if (participantCount === 0 || (availableCount === 0 && busyCount === 0)) return '<div class="si"></div>';
  const ratio = availableCount / participantCount;
  const background = availableCount > 0 ? lerp('#C2EFD4', '#07C160', ratio) : '#F5F5F5';
  const color = ratio > 0.55 ? '#fff' : (availableCount > 0 ? '#065C30' : '#CCC');
  const text = availableCount > 0 ? `${availableCount}/${participantCount}` : '';
  const dot = busyCount > 0 ? `<span class="si-busy" title="${busyCount}人没空"></span>` : '';
  return `<div class="si" style="background:${background};color:${color}">${text}${dot}</div>`;
}

export function getNextColor() {
  return COLORS[state.S.participants.length % COLORS.length];
}
