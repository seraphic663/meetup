import { CHANGELOG_ITEMS, COLORS, ST_AVAIL, ST_BUSY, WD } from './constants.js';
import { getLastName, getSavedParticipantName, getSessionAccess, loadHistory } from './history.js';
import { state } from './state.js';
import { $, describeTimeWindow, esc, fmtRange, getDates, getHours, getSlotSummary, getState, isSlotEnabled, lerp, pad } from './helpers.js';

export function renderHistoryCard() {
  const history = loadHistory();
  renderHomeChangelog();
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
    ? history.map(item => {
      const access = getSessionAccess(item.id);
      const actions = [
        `<button class="history-action-btn" type="button" onclick="event.stopPropagation(); goToSession('${item.id}')">打开</button>`,
      ];

      if (access.creatorToken || access.legacyCanDelete) {
        actions.push(`<button class="history-action-btn danger" type="button" onclick="event.stopPropagation(); deleteSessionFromHistory('${item.id}')">删除整表</button>`);
      } else if (access.participantToken && access.participantId) {
        actions.push(`<button class="history-action-btn" type="button" onclick="event.stopPropagation(); leaveSessionFromHistory('${item.id}')">退出参与</button>`);
      }

      const role = access.creatorToken ? '创建者' : (access.legacyCanDelete ? '旧表格' : (access.participantToken ? '参与者' : '访客'));
      return `<div class="history-entry">
        <span class="history-entry-copy">
          <span class="history-entry-title">${esc(item.name)}</span>
          <span class="history-entry-meta">${item.dateS} — ${item.dateE} · ${role}</span>
        </span>
        <span class="history-entry-actions">${actions.join('')}</span>
      </div>`;
    }).join('')
    : '<div class="history-entry-meta" style="text-align:center;padding:20px">还没有历史记录呢</div>';
}

export function renderHomeChangelog() {
  const target = $('homeChangelogList');
  if (!target) return;
  target.innerHTML = CHANGELOG_ITEMS.map(item => `
    <div class="log-item">
      <div class="log-item-head">
        <span class="log-item-version">v${esc(item.version)}</span>
        <span class="log-item-date">${esc(item.date)}</span>
      </div>
      <div class="log-item-title">${esc(item.title)}</div>
      <div class="log-item-summary">${esc(item.summary)}</div>
    </div>
  `).join('');
}

export function updateCollapseButton() {
  $('btnExpandOthers')?.classList.toggle('active', !state.collapsed);
  $('btnCollapseOthers')?.classList.toggle('active', state.collapsed);
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
  const creatorName = state.S.creatorName ? ` · 创建者 ${esc(state.S.creatorName)}` : '';
  $('mSub').innerHTML = `<span class="live-dot"></span>${fmtRange(state.S)} · ${describeTimeWindow(state.S)}${state.ME ? ' · 点击切换状态' : ' · 查看模式'}${creatorName}`;
  $('btnTR').classList.toggle('active', state.layout === 'tr');
  $('btnPR').classList.toggle('active', state.layout === 'pr');
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
      const isMe = participant.id === state.ME;
      return `<span class="pbadge${isMe ? ' me' : ''}${participant.isRequired ? ' required' : ''}"><span class="pdot" style="background:${participant.color}"></span>${esc(participant.name)}${isMe ? '（我）' : ''}${participant.isRequired ? '<span class="pbadge-tag">关键</span>' : ''}</span>`;
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
  const currentUserIndex = state.ME ? participants.findIndex(participant => participant.id === state.ME) : -1;
  const hours = getHours(state.S);
  const myDayAvail = state.ME ? (state.myAvail[date] || {}) : {};

  const headColumns = participants.map((participant, index) => {
    const isMe = index === currentUserIndex;
    const isOther = !isMe;
    return `<th class="th-p${isMe ? ' is-me' : ''}${isOther ? ' other-col' : ''}" ${isOther && state.collapsed ? 'style="display:none"' : ''}>
      <span class="pname">${esc(participant.name)}${participant.isRequired ? '<span class="mini-priority">关键</span>' : ''}${isMe ? ' ✏' : ''}</span>
      <span class="pmark" style="background:${participant.color}"></span>
    </th>`;
  }).join('');

  const rows = hours.map(hour => {
    const slotEnabled = isSlotEnabled(state.S, date, hour);
    if (!slotEnabled) {
      const blockedCells = participants.map((participant, index) => {
        const isMe = index === currentUserIndex;
        const isOther = !isMe;
        return `<td class="td-c${isOther ? ' other-col' : ''}" ${isOther && state.collapsed ? 'style="display:none"' : ''}>
          <div class="ci ci-blocked${isOther && state.ME ? ' dim' : ''}" title="该时段不在填写范围内"></div>
        </td>`;
      }).join('');
      return `<tr data-date="${date}" data-h="${hour}">
        <td class="td-lbl td-lbl-blocked">${pad(hour)}:00<small>— ${pad(hour + 1)}:00</small></td>
        ${blockedCells}
        <td class="td-sum"><div class="si si-blocked" title="该时段不在填写范围内"></div></td>
      </tr>`;
    }

    const summary = getSlotSummary(participants, currentUserIndex, myDayAvail, date, hour);
    const states = participants.map((participant, index) => getState(index === currentUserIndex ? myDayAvail : (participant.avail[date] || {}), hour));

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
      <td class="td-sum">${buildSummaryCell(summary.availableCount, summary.busyCount, participants.length, summary)}</td>
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
  const currentUserIndex = state.ME ? participants.findIndex(participant => participant.id === state.ME) : -1;
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
      if (!isSlotEnabled(state.S, date, hour)) {
        return `<td class="td-h${isOther ? ' other-col' : ''}" ${isOther && state.collapsed ? 'style="display:none"' : ''}>
          <div class="ci ci-blocked${isOther && state.ME ? ' dim' : ''}" title="该时段不在填写范围内"></div>
        </td>`;
      }
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
        <span class="pn${isMe ? ' is-me' : ''}">${esc(participant.name)}${participant.isRequired ? '<span class="mini-priority">关键</span>' : ''}${isMe ? ' ✏' : ''}</span>
        <span class="pm" style="background:${participant.color}"></span>
      </td>
      ${cells}
      <td class="td-psum${isOther ? ' other-col' : ''}" ${isOther && state.collapsed ? 'style="display:none"' : ''}>
        <div class="si${participant.isRequired ? ' si-person-required' : ''}" style="${sumStyle}">${availableCount > 0 ? availableCount : ''}${participant.isRequired ? '<span class="si-person-tag">关键</span>' : ''}</div>
      </td>
    </tr>`;
  }).join('');

  const summaryRow = hours.map(hour => {
    if (!isSlotEnabled(state.S, date, hour)) {
      return '<td class="td-h"><div class="si si-blocked" title="该时段不在填写范围内"></div></td>';
    }
    const summary = getSlotSummary(participants, currentUserIndex, myDayAvail, date, hour);
    return `<td class="td-h">${buildSummaryCell(summary.availableCount, summary.busyCount, participants.length, summary)}</td>`;
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

function getSummaryIndicator(summary) {
  if (!summary || (summary.requiredAvailableCount === 0 && summary.requiredBusyCount === 0 && summary.requiredUnknownCount === 0)) {
    return '';
  }
  if (summary.requiredBusyCount > 0) {
    return `<span class="si-meta conflict" title="关键成员冲突：${esc(summary.requiredBusyNames.join('、'))}">关键冲突</span>`;
  }
  if (summary.requiredAvailableCount > 0) {
    return `<span class="si-meta pass" title="关键成员有空：${esc(summary.requiredAvailableNames.join('、'))}">关键优先</span>`;
  }
  return `<span class="si-meta pending" title="关键成员尚未填写，不直接否决">关键待定</span>`;
}

export function buildSummaryCell(availableCount, busyCount, participantCount, summary = null) {
  if (participantCount === 0) return '<div class="si"></div>';
  if (availableCount === 0 && busyCount === 0) {
    return `<div class="si">${getSummaryIndicator(summary)}</div>`;
  }
  const ratio = availableCount / participantCount;
  const background = availableCount > 0 ? lerp('#C2EFD4', '#07C160', ratio) : '#F5F5F5';
  const color = ratio > 0.55 ? '#fff' : (availableCount > 0 ? '#065C30' : '#CCC');
  const text = availableCount > 0 ? `${availableCount}/${participantCount}` : '';
  const dot = busyCount > 0 ? `<span class="si-busy" title="${busyCount}人没空"></span>` : '';
  const summaryClass = summary?.requiredBusyCount ? ' si-conflict' : (summary?.requiredAvailableCount ? ' si-priority' : '');
  return `<div class="si${summaryClass}" style="background:${background};color:${color}">${text}${dot}${getSummaryIndicator(summary)}</div>`;
}

export function getNextColor() {
  return COLORS[state.S.participants.length % COLORS.length];
}
