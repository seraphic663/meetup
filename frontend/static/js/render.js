import { CHANGELOG_ITEMS, COLORS } from './constants.js';
import { getLastName, getSavedParticipantName, getSessionAccess, loadHistory } from './history.js';
import { state } from './state.js';
import { $, describeTimeWindow, esc, fmtRange, pad } from './helpers.js';

export function renderHistoryCard() {
  const history = loadHistory();
  renderHomeChangelog();
  $('historyCard')?.classList.remove('hidden');
  if (history.length > 0) {
    $('historyList').innerHTML = history.slice(0, 3).map(item => {
      const sid = encodeURIComponent(item.id);
      return `
      <div class="history-mini-item">
        <button class="history-mini-open" type="button" onclick="goToSession(decodeURIComponent('${sid}'))">
          <span class="history-mini-title">${esc(item.name)}</span>
          <span>${esc(item.dateS)}</span>
        </button>
        <button class="history-mini-remove" type="button" title="从最近表格移除" onclick="removeSessionFromHistory(decodeURIComponent('${sid}'))">删除</button>
      </div>
    `;
    }).join('');
    $('historyDesc').textContent = `${history.length} 个最近的表格；也可粘贴旧链接打开。`;
    return;
  }
  $('historyDesc').textContent = '暂无本机历史；粘贴旧链接或表格 ID 也能打开。';
  $('historyList').innerHTML = '<div class="history-mini-empty">还没有最近表格。创建新表后会自动出现在这里。</div>';
}

export function renderHistoryScreen() {
  const history = loadHistory();
  $('historyListFull').innerHTML = history.length > 0
    ? history.map(item => {
      const access = getSessionAccess(item.id);
      const sid = encodeURIComponent(item.id);
      const actions = [
        `<button class="history-action-btn" type="button" onclick="event.stopPropagation(); goToSession(decodeURIComponent('${sid}'))">打开</button>`,
        `<button class="history-action-btn" type="button" onclick="event.stopPropagation(); removeSessionFromHistory(decodeURIComponent('${sid}'))">移除记录</button>`,
      ];

      if (access.creatorToken) {
        actions.push(`<button class="history-action-btn danger" type="button" onclick="event.stopPropagation(); deleteSessionFromHistory(decodeURIComponent('${sid}'))">删除整表</button>`);
      } else if (access.participantToken && access.participantId) {
        actions.push(`<button class="history-action-btn" type="button" onclick="event.stopPropagation(); leaveSessionFromHistory(decodeURIComponent('${sid}'))">退出参与</button>`);
      }

      const role = access.creatorToken ? '创建者' : (access.participantToken ? '参与者' : '访客');
      return `<div class="history-entry">
        <span class="history-entry-copy">
          <span class="history-entry-title">${esc(item.name)}</span>
          <span class="history-entry-meta">${item.dateS} — ${item.dateE} · ${role}</span>
        </span>
        <span class="history-entry-actions">${actions.join('')}</span>
      </div>`;
    }).join('')
    : '<div class="history-entry-empty">还没有历史记录。创建或打开表格后会自动出现在这里。</div>';
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
  $('jEvMeta').textContent = fmtRange(state.S) + (state.S.participants.length ? ` · 已有 ${state.S.participants.length} 人参与` : ' · 快来第一个填！');
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
  const creatorName = state.S.creatorName ? ' · 创建者 ' + esc(state.S.creatorName) : '';
  const modeHint = state.quickDemo ? ' · 示例预览' : state.ME ? ' · 可填写' : ' · 查看模式';
  $('mSub').innerHTML = '<span class="live-dot"></span>' + fmtRange(state.S) + ' · ' + describeTimeWindow(state.S) + modeHint + creatorName;
  $('btnAISummary')?.classList.toggle('hidden', Boolean(state.quickDemo));
  renderBadges();
  renderCreatorPrompt('main');
  renderRemarkCard();
  renderPublicRemarks();
  updateCollapseButton();
}
export function renderRemarkCard() {
  const card = $('remarkCard');
  const input = $('myRemark');
  if (!state.ME || state.quickDemo) {
    card.classList.add('hidden');
    return;
  }
  card.classList.remove('hidden');
  if (!state.remarkDirty) input.value = state.remarkDraft || state.myRemark || '';
  updateRemarkCounter();
  const saveButton = $('saveRemarkBtn');
  if (saveButton) {
    saveButton.textContent = state.myRemark ? '更新并公开' : '保存并公开';
    saveButton.disabled = Boolean(state.remarkSaving);
  }
  if (!state.remarkDirty && !state.remarkSaving) {
    updateRemarkHint(state.myRemark ? '已提交，组员可见' : '尚未填写');
  }
}

export function updateRemarkCounter() {
  const remark = state.remarkDirty ? state.remarkDraft : state.myRemark;
  $('remarkCount').textContent = `${(remark || '').length}/200`;
}

export function updateRemarkHint(text) {
  $('remarkSaveHint').textContent = text;
}

export function renderPublicRemarks() {
  const card = $('publicRemarksCard');
  const list = $('publicRemarksList');
  if (!card || !list) return;
  if (state.quickDemo) {
    card.classList.add('hidden');
    list.innerHTML = '';
    return;
  }

  const remarks = (state.S?.participants || []).filter(participant => (participant.remark || '').trim());
  if (!remarks.length) {
    card.classList.add('hidden');
    list.innerHTML = '';
    return;
  }

  card.classList.remove('hidden');
  list.innerHTML = remarks.map(participant => `
    <div class="public-remark">
      <div class="public-remark-name">${esc(participant.name)}</div>
      <div class="public-remark-text">${esc(participant.remark)}</div>
    </div>
  `).join('');
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

export function getNextColor() {
  return COLORS[state.S.participants.length % COLORS.length];
}
