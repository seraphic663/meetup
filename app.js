'use strict';

const COLORS = ['#FF6B35','#4ECDC4','#45B7D1','#9B59B6','#E67E22','#27AE60','#E91E63','#3498DB','#F39C12','#1ABC9C','#E74C3C','#16A085'];
const WD = ['周日','周一','周二','周三','周四','周五','周六'];

// ─── 三态常量 ───
const ST_EMPTY = 0;  // 未填（灰色）
const ST_AVAIL = 1;  // 有空（彩色）
const ST_BUSY  = 2;  // 没空（浅红 + ✕）

let SID     = null;
let S       = null;
let ME      = null;
// myAvail 格式：{ "2025-03-06": { 9: 1, 10: 2, ... } }
let myAvail = {};
let myRemark = '';

let layout    = 'tr';   // 'tr'=时间为行 / 'pr'=人员为行
let collapsed = true;   // 默认折叠他人

let drag  = { on: false, fillTo: ST_AVAIL, col: -1, lastKey: '' };
let pollT = null;
let saveT = null;
let remarkSaveT = null;

// ─── Tutorial ───
let tutorialStep = 0;
const tutorialSteps = [
  { emoji: '1️⃣', title: '点击格子循环切换状态', desc: '绿色 = 有空，红✕ = 没空，灰色 = 未填。每点一次循环切换。' },
  { emoji: '2️⃣', title: '拖拽批量填写', desc: '按住并上下拖动，快速填充多个相同的时段。' },
  { emoji: '3️⃣', title: '切换布局查看', desc: '时间为行 vs 人员为行，两种视角全面了解情况。' },
  { emoji: '4️⃣', title: '分享链接邀请', desc: '复制链接，发微信群，朋友点链接选名字就能填。' }
];

/* ─── API ─── */
async function api(url, method = 'GET', body = null) {
  const opts = { method, headers: {} };
  if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  try {
    const r = await fetch(url, opts);
    if (!r.ok) return null;
    return await r.json();
  } catch(e) { return null; }
}

/* ─── 格式兼容（旧 avail:[h,...] → 新 avail:{date:{h:state}}）─── */
function normalizeAvail(raw) {
  if (!raw) return {};
  const out = {};
  for (const [date, val] of Object.entries(raw)) {
    out[date] = {};
    if (Array.isArray(val)) {
      // 旧格式：有空数组
      val.forEach(h => { out[date][String(h)] = ST_AVAIL; });
    } else if (typeof val === 'object') {
      for (const [h, st] of Object.entries(val)) {
        out[date][String(h)] = Number(st) || ST_EMPTY;
      }
    }
  }
  return out;
}

// dayAvail: 单天字典 { "9": 1, "12": 2, ... }
function getState(dayAvail, hour) {
  if (!dayAvail) return ST_EMPTY;
  const v = dayAvail[String(hour)];
  return (v === ST_AVAIL || v === ST_BUSY) ? Number(v) : ST_EMPTY;
}

/* ─── History 管理 ─── */
function saveToHistory(sid, name, dateS, dateE) {
  let history = JSON.parse(localStorage.getItem('mqa_history') || '[]');
  history = history.filter(h => h.id !== sid);  // 去重
  history.unshift({ id: sid, name, dateS, dateE, visited: Date.now() });
  history = history.slice(0, 5);  // 仅保留最近 5 个
  localStorage.setItem('mqa_history', JSON.stringify(history));
  renderHistoryCard();
}

function loadHistory() {
  return JSON.parse(localStorage.getItem('mqa_history') || '[]');
}

function renderHistoryCard() {
  const hist = loadHistory();
  if (hist.length > 0) {
    $('historyCard').classList.remove('hidden');
    const items = hist.slice(0, 3).map(h => `<div class="hc-item" onclick="goToSession('${h.id}')" style="cursor:pointer">${h.name} (${h.dateS})</div>`).join('');
    $('historyList').innerHTML = items;
    $('historyDesc').textContent = `${hist.length} 个最近的表格`;
  } else {
    $('historyCard').classList.add('hidden');
  }
}

function goToSession(sid) {
  location.href = `/?s=${sid}`;
}

/* ─── Boot ─── */
document.addEventListener('mouseup',  endDrag);
document.addEventListener('touchend', endDrag);

(async function init() {
  SID = new URLSearchParams(location.search).get('s');
  if (SID) {
    S = await api(`/api/session/${SID}`);
    if (!S) { toast('❌ 会话不存在或已过期'); setTimeout(() => location.href = '/', 2000); return; }
    S.participants.forEach(p => { p.avail = normalizeAvail(p.avail); });
    renderJoin();
  } else {
    initForm(); showHome();
  }
})();

/* ─── 屏幕导航 ─── */
function showHome() {
  renderHistoryCard();
  showScr('homeScreen');
}

function goToHome() {
  stopPoll();
  if (ME) {
    const meP = S.participants.find(p => p.name === ME);
    if (meP) {
      meP.avail = JSON.parse(JSON.stringify(myAvail));
      meP.remark = myRemark;
    }
    saveAvail();
  }
  showHome();
}

function goToSetup() {
  showScr('setupScreen');
}

function goToHistory() {
  const hist = loadHistory();
  $('historyListFull').innerHTML = hist.length > 0
    ? hist.map(h => `<div class="fg">
        <button class="btn-p" style="margin-top:0" onclick="goToSession('${h.id}')">${h.name}</button>
        <div style="font-size:12px;color:var(--t3);margin-top:6px">${h.dateS} — ${h.dateE}</div>
      </div>`).join('')
    : '<div style="text-align:center;color:var(--t3);padding:20px">还没有历史记录呢</div>';
  showScr('historyScreen');
}

/* ─── Setup form ─── */
function initForm() {
  const selS = $('sHourS'), selE = $('sHourE');
  for (let h = 0; h <= 23; h++) {
    [selS, selE].forEach(sel => {
      const o = document.createElement('option');
      o.value = h; o.textContent = pad(h) + ':00'; sel.appendChild(o);
    });
  }
  selS.value = 9; selE.value = 21;
  const now = new Date(), later = new Date(now);
  later.setDate(now.getDate() + 3);
  $('sDateS').value = dfmt(now); $('sDateE').value = dfmt(later);
  const inp = $('tagInp');
  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(); }
    if (e.key === 'Backspace' && !e.target.value) removeLastTag();
  });
  inp.addEventListener('focus', () => $('tagWrap').classList.add('focused'));
  inp.addEventListener('blur',  () => $('tagWrap').classList.remove('focused'));
}

async function createSession() {
  const name = $('sName').value.trim(), dateS = $('sDateS').value, dateE = $('sDateE').value;
  const hourS = +$('sHourS').value, hourE = +$('sHourE').value, myName = $('sMyName').value.trim();
  if (!name)            return toast('请输入活动名称');
  if (!dateS || !dateE) return toast('请选择日期');
  if (dateS > dateE)    return toast('开始日期不能晚于结束日期');
  if (hourS >= hourE)   return toast('截止时间须晚于起始时间');
  if (!myName)          return toast('请输入你的昵称（发起人）');
  if (dayDiff(dateS, dateE) > 14) return toast('日期范围最多14天');
  $('setupScreen').querySelector('.btn-p').textContent = '创建中…';
  const r = await api('/api/session', 'POST', { name, dateS, dateE, hourS, hourE, expectedNames: [...tags] });
  if (!r?.id) { $('setupScreen').querySelector('.btn-p').textContent = '创建调查 →'; return toast('创建失败，请重试'); }
  location.href = `/?s=${r.id}`;
}

/* ─── Tag input ─── */
let tags = [];
function focusTagInput(e) { if (!e.target.classList.contains('tag-x')) $('tagInp').focus(); }
function addTag() {
  const v = $('tagInp').value.trim();
  if (!v || tags.includes(v)) return;
  if (tags.length >= 12) return toast('最多12人');
  tags.push(v); $('tagInp').value = ''; renderTags();
}
function removeTag(name) { tags = tags.filter(t => t !== name); renderTags(); }
function removeLastTag()  { if (tags.length) { tags.pop(); renderTags(); } }
function renderTags() {
  $('tagWrap').querySelectorAll('.tag').forEach(t => t.remove());
  [...tags].reverse().forEach(t => {
    const div = document.createElement('div'); div.className = 'tag';
    div.innerHTML = `${esc(t)}<button class="tag-x" onclick="removeTag('${esc(t)}')" type="button">×</button>`;
    $('tagWrap').insertBefore(div, $('tagWrap').firstChild);
  });
}

/* ─── Join ─── */
let jPick = null;
function renderJoin() {
  $('jEvName').textContent = S.name;
  $('jEvMeta').textContent = fmtRange() + (S.participants.length ? ` · 已有 ${S.participants.length} 人填写` : ' · 快来第一个填！');
  const saved = localStorage.getItem('mqa_' + SID);
  const savedP = saved && S.participants.find(p => p.name === saved);
  if (savedP) { $('jResumeName').textContent = saved; $('jResumeArea').classList.remove('hidden'); }
  else        { $('jResumeArea').classList.add('hidden'); }
  const exp = S.expectedNames || [];
  if (exp.length) {
    $('jChipsArea').classList.remove('hidden');
    $('jChips').innerHTML = exp.map(n => {
      const filled = S.participants.find(p => p.name === n);
      return `<div class="nchip${filled ? ' done' : ''}" onclick="${filled ? '' : `pickChip(this,'${esc(n)}')`}">${esc(n)}${filled ? ' ✓' : ''}</div>`;
    }).join('');
  } else { $('jChipsArea').classList.add('hidden'); }
  jPick = null; $('jName').value = '';
  showScr('joinScreen');
}
function pickChip(el, name) {
  document.querySelectorAll('.nchip').forEach(c => c.classList.remove('active'));
  el.classList.add('active'); jPick = name; $('jName').value = name;
}
async function joinSession() {
  const name = ($('jName').value.trim() || jPick || '').trim();
  if (!name) return toast('请选择或输入你的昵称');
  const existingP = S.participants.find(p => p.name === name);
  const color = existingP ? existingP.color : COLORS[S.participants.length % COLORS.length];
  const newS = await api(`/api/session/${SID}/join`, 'POST', { name, color });
  if (!newS) return toast('加入失败，请重试');
  S = newS; S.participants.forEach(p => { p.avail = normalizeAvail(p.avail); });
  ME = name;
  const meP = S.participants.find(p => p.name === ME);
  myAvail = meP?.avail ? JSON.parse(JSON.stringify(meP.avail)) : {};
  myRemark = (meP?.remark || '').slice(0, 200);
  localStorage.setItem('mqa_' + SID, ME);
  saveToHistory(SID, S.name, S.dateS, S.dateE);
  renderMain(); showScr('mainScreen'); startPoll();
  toast(existingP ? `欢迎回来，${ME} 👋` : `点格子循环：有空（彩色）→ 没空（红✕）→ 未填 ✌️`);
}
async function resumeSession() {
  const saved = localStorage.getItem('mqa_' + SID);
  if (!saved) return; $('jName').value = saved; await joinSession();
}
function viewOnly() { ME = null; myAvail = {}; myRemark = ''; saveToHistory(SID, S.name, S.dateS, S.dateE); renderMain(); showScr('mainScreen'); startPoll(); }
function switchUser() { stopPoll(); ME = null; myAvail = {}; myRemark = ''; renderJoin(); }

/* ─── 布局 & 折叠控制 ─── */
function setLayout(mode) {
  layout = mode;
  $('btnTR').classList.toggle('active', mode === 'tr');
  $('btnPR').classList.toggle('active', mode === 'pr');
  renderGrid();
}

function toggleCollapse() {
  collapsed = !collapsed;
  updateCollapseBtn();
  // 直接切换 DOM，不重渲
  document.querySelectorAll('tr.other-row').forEach(r => r.classList.toggle('collapsed', collapsed));
  // m-tr 模式：折叠 th/td 列
  document.querySelectorAll('.other-col').forEach(el => {
    el.style.display = collapsed ? 'none' : '';
  });
  document.querySelectorAll('.toggle-btn-row td').forEach(td => {
    td.textContent = collapsed ? '▼ 展开其他人' : '▲ 收起其他人';
  });
}

function updateCollapseBtn() {
  $('btnCollapse').textContent = collapsed ? '👁 展开他人' : '🙈 折叠他人';
  $('btnCollapse').classList.toggle('active', !collapsed);
}

/* ─── Main ─── */
function renderMain() {
  $('mTitle').textContent = S.name;
  $('mSub').innerHTML = `<span class="live-dot"></span>${fmtRange()}${ME ? ' · 点击切换状态' : ' · 查看模式'}`;
  renderBadges();
  if (ME) {
    $('tipBox').textContent = '💡 点格子循环切换：有空（彩色）→ 没空（红✕）→ 未填（灰）。上下拖可批量填。';
    $('tipBox').classList.remove('hidden');
  } else { $('tipBox').classList.add('hidden'); }
  renderRemarkCard();
  updateCollapseBtn();
  renderGrid();
}

function renderRemarkCard() {
  const card = $('remarkCard');
  const input = $('myRemark');
  if (!card || !input) return;
  if (!ME) {
    card.classList.add('hidden');
    return;
  }
  card.classList.remove('hidden');
  input.value = myRemark || '';
  input.oninput = onRemarkInput;
  updateRemarkCounter();
  updateRemarkHint('自动保存');
}

function onRemarkInput(e) {
  const val = (e?.target?.value || '').slice(0, 200);
  myRemark = val;
  const meP = S.participants.find(p => p.name === ME);
  if (meP) meP.remark = myRemark;
  updateRemarkCounter();
  updateRemarkHint('保存中…');
  clearTimeout(remarkSaveT);
  remarkSaveT = setTimeout(async () => {
    await saveAvail();
    updateRemarkHint('已保存');
  }, 350);
}

function updateRemarkCounter() {
  const countEl = $('remarkCount');
  if (countEl) countEl.textContent = `${(myRemark || '').length}/200`;
}

function updateRemarkHint(text) {
  const hintEl = $('remarkSaveHint');
  if (hintEl) hintEl.textContent = text;
}

function renderBadges() {
  $('statsStrip').innerHTML =
    `<span class="s-lbl">参与者（${S.participants.length}人）：</span><div class="pbadges">` +
    S.participants.map(p => {
      const isMe = p.name === ME;
      return `<span class="pbadge${isMe ? ' me' : ''}"><span class="pdot" style="background:${p.color}"></span>${esc(p.name)}${isMe ? '（我）' : ''}</span>`;
    }).join('') + `</div>`;
}

/* ─── Grid ─── */
function renderGrid() {
  const sc = window.scrollY;
  $('gridContent').innerHTML = getDates().map(d => renderDay(d)).join('');
  attachEvents();
  window.scrollTo(0, sc);
}

function renderDay(date) {
  const d = new Date(date + 'T00:00:00');
  const wd = WD[d.getDay()], isWe = d.getDay() === 0 || d.getDay() === 6;
  const mm = d.getMonth() + 1, dd = d.getDate();
  const inner = layout === 'tr' ? renderDayTR(date) : renderDayPR(date);
  return `<div class="day-sec">
    <div class="day-hdr">
      <span class="day-date">${mm}月${dd}日</span>
      <span class="day-wd${isWe ? ' we' : ''}">${wd}${isWe ? ' 🎉' : ''}</span>
    </div>
    <div class="g-card"><div class="g-scroll">${inner}</div></div>
  </div>`;
}

/* ══ 时间=行 ══ */
function renderDayTR(date) {
  const ppl = S.participants, myI = ME ? ppl.findIndex(p => p.name === ME) : -1;
  const hours = getHours(), maxP = ppl.length;

  const thCols = ppl.map((p, i) => {
    const isMe = i === myI, isOther = !isMe;
    return `<th class="th-p${isMe ? ' is-me' : ''}${isOther ? ' other-col' : ''}" ${isOther && collapsed ? 'style="display:none"' : ''}>
      <span class="pname">${esc(p.name)}${isMe ? ' ✏' : ''}</span>
      <span class="pmark" style="background:${p.color}"></span>
    </th>`;
  }).join('');
  const thead = `<thead><tr><th class="th-lbl">时段</th>${thCols}<th class="th-sum">汇总</th></tr></thead>`;

  const myDA = ME ? (myAvail[date] || {}) : {};

  const rows = hours.map(h => {
    const avails = ppl.map((p, i) => getState(i === myI ? myDA : (p.avail[date] || {}), h));
    const cntAvail = avails.filter(s => s === ST_AVAIL).length;
    const cntBusy  = avails.filter(s => s === ST_BUSY).length;

    const tdCols = ppl.map((p, i) => {
      const isMe = i === myI, isOther = !isMe;
      const st = avails[i];
      const cls = 'ci' + (isMe ? ' ed' : ' ro') + (isOther && ME ? ' dim' : '');
      const da  = isMe
        ? ` data-date="${date}" data-hour="${h}" data-col="${i}"`
        : ` data-pi="${i}" data-date="${date}" data-hour="${h}"`;
      return `<td class="td-c${isOther ? ' other-col' : ''}" ${isOther && collapsed ? 'style="display:none"' : ''}>
        <div class="${cls}" style="${cellStyle(st, p.color)}"${da}>${st === ST_BUSY ? '✕' : ''}</div>
      </td>`;
    }).join('');

    return `<tr data-date="${date}" data-h="${h}">
      <td class="td-lbl">${pad(h)}:00<small>— ${pad(h+1)}:00</small></td>
      ${tdCols}
      <td class="td-sum">${buildSI(cntAvail, cntBusy, maxP)}</td>
    </tr>`;
  }).join('');

  const otherCnt = ppl.filter((_, i) => i !== myI).length;
  const toggleRow = otherCnt > 0
    ? `<tr class="toggle-btn-row" onclick="toggleCollapse()"><td colspan="${ppl.length + 2}">${collapsed ? '▼ 展开其他人' : '▲ 收起其他人'}</td></tr>` : '';

  return `<table class="sg m-tr" data-date="${date}">
    ${thead}<tbody>${rows}${toggleRow}</tbody>
  </table>`;
}

/* ══ 人员=行 ══ */
function renderDayPR(date) {
  const ppl = S.participants, myI = ME ? ppl.findIndex(p => p.name === ME) : -1;
  const hours = getHours(), maxP = ppl.length;

  const thHours = hours.map(h => `<th class="th-h">${pad(h)}<br><span style="font-size:9px;color:#bbb">—${pad(h+1)}</span></th>`).join('');
  const thead = `<thead><tr><th class="th-lbl2">人员</th>${thHours}<th class="th-sum2">小计</th></tr></thead>`;

  const myDA = ME ? (myAvail[date] || {}) : {};

  const personRows = ppl.map((p, i) => {
    const isMe = i === myI, isOther = !isMe;
    const av = isMe ? myDA : (p.avail[date] || {});
    const cntA = hours.filter(h => getState(av, h) === ST_AVAIL).length;

    const tdHours = hours.map(h => {
      const st = getState(av, h);
      const cls = 'ci' + (isMe ? ' ed' : ' ro') + (isOther && ME ? ' dim' : '');
      const da  = isMe
        ? ` data-date="${date}" data-hour="${h}" data-col="${i}"`
        : ` data-pi="${i}" data-date="${date}" data-hour="${h}"`;
      return `<td class="td-h${isOther ? ' other-col' : ''}" ${isOther && collapsed ? 'style="display:none"' : ''}>
        <div class="${cls}" style="${cellStyle(st, p.color)}"${da}>${st === ST_BUSY ? '✕' : ''}</div>
      </td>`;
    }).join('');

    const sumStyle = cntA > 0 ? `background:#E8F8F0;color:#05A050` : `background:#F5F5F5;color:#CCC`;
    const pSumTd = `<td class="td-psum${isOther ? ' other-col' : ''}" ${isOther && collapsed ? 'style="display:none"' : ''}>
      <div class="si" style="${sumStyle}">${cntA > 0 ? cntA : ''}</div>
    </td>`;

    return `<tr data-date="${date}" data-pi="${i}"${isOther ? ` class="other-row${collapsed ? ' collapsed' : ''}"` : ''}>
      <td class="td-plbl">
        <span class="pn${isMe ? ' is-me' : ''}">${esc(p.name)}${isMe ? ' ✏' : ''}</span>
        <span class="pm" style="background:${p.color}"></span>
      </td>
      ${tdHours}${pSumTd}
    </tr>`;
  }).join('');

  // 汇总行（逐列统计）
  const sumTds = hours.map(h => {
    const avails = ppl.map((p, i) => getState(i === myI ? myDA : (p.avail[date] || {}), h));
    const cntAvail = avails.filter(s => s === ST_AVAIL).length;
    const cntBusy  = avails.filter(s => s === ST_BUSY).length;
    return `<td class="td-h">${buildSI(cntAvail, cntBusy, maxP)}</td>`;
  }).join('');

  const otherCnt = ppl.filter((_, i) => i !== myI).length;
  const toggleRow = otherCnt > 0
    ? `<tr class="toggle-btn-row" onclick="toggleCollapse()"><td colspan="${hours.length + 2}">${collapsed ? '▼ 展开其他人' : '▲ 收起其他人'}</td></tr>` : '';

  return `<table class="sg m-pr" data-date="${date}">
    ${thead}<tbody>
      ${personRows}
      ${toggleRow}
      <tr class="sum-row" data-date="${date}">
        <td class="td-plbl"><span class="pn" style="color:var(--t3)">汇总</span></td>
        ${sumTds}
        <td class="td-psum"></td>
      </tr>
    </tbody>
  </table>`;
}

/* ─── 视觉辅助 ─── */
function cellStyle(state, color) {
  if (state === ST_AVAIL) return `background:${color};color:transparent;`;
  if (state === ST_BUSY)  return `background:#FFF0F0;color:#FF4D4F;`;
  return `background:#EFF0F2;color:transparent;`;
}

function buildSI(cntAvail, cntBusy, maxP) {
  if (maxP === 0 || (cntAvail === 0 && cntBusy === 0)) return `<div class="si"></div>`;
  const r = cntAvail / maxP;
  const bg  = cntAvail > 0 ? lerp('#C2EFD4', '#07C160', r) : '#F5F5F5';
  const col = r > 0.55 ? '#fff' : (cntAvail > 0 ? '#065C30' : '#CCC');
  const txt = cntAvail > 0 ? `${cntAvail}/${maxP}` : '';
  const dot = cntBusy  > 0 ? `<span class="si-busy" title="${cntBusy}人没空"></span>` : '';
  return `<div class="si" style="background:${bg};color:${col}">${txt}${dot}</div>`;
}

/* ─── 拖拽（三态循环）─── */
function attachEvents() {
  if (!ME) return;
  document.querySelectorAll('.ci.ed').forEach(el => {
    el.addEventListener('mousedown',  onDown,  { passive: false });
    el.addEventListener('mouseenter', onEnter);
    el.addEventListener('touchstart', onTStart, { passive: false });
    el.addEventListener('touchmove',  onTMove,  { passive: false });
  });
}

function onDown(e)   { e.preventDefault(); startDrag(e.currentTarget); }
function onTStart(e) { e.preventDefault(); startDrag(e.currentTarget); }
function onEnter(e) {
  if (!drag.on) return;
  const el = e.currentTarget;
  if (+el.dataset.col !== drag.col) return;
  const key = `${el.dataset.date}-${el.dataset.hour}`;
  if (key === drag.lastKey) return;
  drag.lastKey = key;
  applyCell(el.dataset.date, +el.dataset.hour, drag.fillTo, el);
}
function onTMove(e) {
  if (!drag.on) return; e.preventDefault();
  const el = document.elementFromPoint(e.touches[0].clientX, e.touches[0].clientY)?.closest('.ci.ed');
  if (!el || +el.dataset.col !== drag.col) return;
  const key = `${el.dataset.date}-${el.dataset.hour}`;
  if (key === drag.lastKey) return;
  drag.lastKey = key;
  applyCell(el.dataset.date, +el.dataset.hour, drag.fillTo, el);
}

function startDrag(el) {
  const date = el.dataset.date, h = +el.dataset.hour, col = +el.dataset.col;
  const cur  = getState(myAvail[date] || {}, h);
  const next = (cur + 1) % 3;  // 0→1→2→0（未填→有空→没空→未填）
  drag = { on: true, fillTo: next, col, lastKey: `${date}-${h}` };
  applyCell(date, h, next, el);
}

function applyCell(date, hour, state, el) {
  if (!myAvail[date]) myAvail[date] = {};
  myAvail[date][String(hour)] = state;
  if (el) {
    const me = S.participants.find(p => p.name === ME);
    el.setAttribute('style', cellStyle(state, me?.color || '#07C160'));
    el.textContent = state === ST_BUSY ? '✕' : '';
  }
}

function endDrag() {
  if (!drag.on) return;
  drag.on = false;
  const meP = S.participants.find(p => p.name === ME);
  if (meP) {
    meP.avail = JSON.parse(JSON.stringify(myAvail));
    meP.remark = myRemark;
  }
  refreshSummary();
  clearTimeout(saveT);
  saveT = setTimeout(saveAvail, 400);
}

async function saveAvail() {
  if (!ME || !SID) return;
  await api(`/api/session/${SID}/avail`, 'PUT', { name: ME, avail: myAvail, remark: myRemark });
}

function refreshSummary() {
  const ppl = S.participants, myI = ppl.findIndex(p => p.name === ME), maxP = ppl.length;
  getDates().forEach(date => {
    const myDA = ME ? (myAvail[date] || {}) : {};
    getHours().forEach(h => {
      const avails = ppl.map((p, i) => getState(i === myI ? myDA : (p.avail[date] || {}), h));
      const cntAvail = avails.filter(s => s === ST_AVAIL).length;
      const cntBusy  = avails.filter(s => s === ST_BUSY).length;
      // m-tr 模式：更新 .si
      const row = document.querySelector(`table.sg.m-tr[data-date="${date}"] tr[data-h="${h}"] .si`);
      if (row) row.outerHTML = buildSI(cntAvail, cntBusy, maxP);
    });
    // m-pr 模式：更新汇总行
    if (layout === 'pr') {
      const sumRow = document.querySelector(`tr.sum-row[data-date="${date}"]`);
      if (sumRow) {
        const tds = sumRow.querySelectorAll('td.td-h');
        getHours().forEach((h, idx) => {
          const avails = ppl.map((p, i) => getState(i === myI ? (myAvail[date] || {}) : (p.avail[date] || {}), h));
          const cntA = avails.filter(s => s === ST_AVAIL).length;
          const cntB = avails.filter(s => s === ST_BUSY).length;
          if (tds[idx]) tds[idx].innerHTML = buildSI(cntA, cntB, maxP);
        });
      }
    }
  });
}

/* ─── Polling ─── */
function startPoll() { stopPoll(); pollT = setInterval(doPoll, 3000); }
function stopPoll()  { clearInterval(pollT); pollT = null; }

async function doPoll() {
  if (drag.on) return;
  const newS = await api(`/api/session/${SID}`);
  if (!newS) return;
  const prevCount = S.participants.length;

  newS.participants.forEach(np => {
    np.avail = normalizeAvail(np.avail);
    if (np.name === ME) return;
    const ex = S.participants.find(p => p.name === np.name);
    if (ex) {
      ex.avail = np.avail;
      ex.remark = np.remark || '';
    }
    else    { S.participants.push({ ...np }); }
  });

  if (S.participants.length > prevCount) {
    toast(`${S.participants[S.participants.length - 1].name} 加入了 🎉`);
    renderBadges(); renderGrid(); return;
  }

  // 局部更新他人格子
  S.participants.forEach((p, idx) => {
    if (p.name === ME) return;
    getDates().forEach(date => {
      getHours().forEach(h => {
        const st = getState(p.avail[date] || {}, h);
        // m-tr 模式格子
        const elTR = document.querySelector(`.ci[data-pi="${idx}"][data-date="${date}"][data-hour="${h}"]`);
        if (elTR) { elTR.setAttribute('style', cellStyle(st, p.color)); elTR.textContent = st === ST_BUSY ? '✕' : ''; }
      });
    });
  });
  refreshSummary();
}

/* ─── Tutorial ─── */
function showTutorial() {
  tutorialStep = 0;
  showTutorialStep();
  $('tutorialOverlay').classList.add('show');
}

function showTutorialStep() {
  const step = tutorialSteps[tutorialStep];
  $('tutStep').textContent = step.emoji;
  $('tutTitle').textContent = step.title;
  $('tutDesc').textContent = step.desc;
  const btn = $('tutBtn');
  btn.textContent = tutorialStep < tutorialSteps.length - 1 ? '下一步 →' : '开始使用';
  btn.onclick = () => {
    if (tutorialStep < tutorialSteps.length - 1) {
      tutorialStep++;
      showTutorialStep();
    } else {
      skipTutorial();
    }
  };
}

function skipTutorial() {
  $('tutorialOverlay').classList.remove('show');
  localStorage.setItem('mqa_tutorial_done', 'true');
}

/* ─── AI Summary ─── */
async function openAISummary() {
  if (!SID) return toast('无法获取会话信息');
  $('aiSummaryOverlay').classList.add('open');
  // 调用后端 API
  const summary = await api(`/api/session/${SID}/summary`);
  if (summary?.summary) {
    renderAISummary(summary.summary);
  } else {
    $('aiContent').innerHTML = `<div style="color:var(--t3);text-align:center;padding:20px">🚫 生成失败，请稍后重试</div>`;
  }
}

function renderAISummary(text) {
  // 简单的 markdown-like 渲染
  const lines = text.split('\n');
  let html = '';
  lines.forEach(line => {
    if (line.startsWith('## ')) {
      html += `<div class="ai-section"><div class="ai-section-title">${esc(line.slice(3))}</div>`;
    } else if (line.startsWith('- ')) {
      html += `<div class="ai-item"><div class="ai-item-emoji">•</div><div class="ai-item-text">${esc(line.slice(2))}</div></div>`;
    } else if (line.trim()) {
      html += `<div class="ai-item-text">${esc(line)}</div>`;
    }
  });
  html += '</div>';
  $('aiContent').innerHTML = html;
}

function closeAISummary() {
  $('aiSummaryOverlay').classList.remove('open');
}

function overlayBgAI(e) {
  if (e.target === $('aiSummaryOverlay')) closeAISummary();
}

/* ─── Share ─── */
function openShare() {
  $('shUrl').textContent = location.href;
  $('shPeopleStat').textContent = `当前已有 ${S.participants.length} 人填写数据。`;
  $('shareOverlay').classList.add('open');
}
function closeShare() { $('shareOverlay').classList.remove('open'); }
function overlayBg(e) { if (e.target === $('shareOverlay')) closeShare(); }
function copyUrl() {
  const url = location.href, done = () => { toast('已复制 🎉  发到群里吧！'); closeShare(); };
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(url).then(done).catch(() => fbCopy(url, done));
  else fbCopy(url, done);
}
function fbCopy(url, cb) {
  const ta = Object.assign(document.createElement('textarea'), { value: url });
  ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0;width:1px;height:1px';
  document.body.appendChild(ta); ta.focus(); ta.select();
  try { document.execCommand('copy'); cb(); } catch(_) { toast('请长按链接手动复制'); }
  ta.remove();
}

/* ─── Helpers ─── */
function getDates() {
  const out = [], d = new Date(S.dateS + 'T00:00:00'), e = new Date(S.dateE + 'T00:00:00');
  while (d <= e) { out.push(dfmt(d)); d.setDate(d.getDate() + 1); }
  return out;
}
function getHours() { const h = []; for (let i = S.hourS; i < S.hourE; i++) h.push(i); return h; }
function dfmt(d)    { return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`; }
function fmtRange() { return S.dateS.slice(5).replace('-','月') + '日 — ' + S.dateE.slice(5).replace('-','月') + '日'; }
function dayDiff(a, b) { return (new Date(b) - new Date(a)) / 86400000; }
function pad(n) { return String(n).padStart(2, '0'); }
function $(id)  { return document.getElementById(id); }
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
function lerp(h1, h2, t) {
  const p = h => [1,3,5].map(i => parseInt(h.slice(i,i+2),16));
  const [r1,g1,b1] = p(h1), [r2,g2,b2] = p(h2);
  return `rgb(${~~(r1+(r2-r1)*t)},${~~(g1+(g2-g1)*t)},${~~(b1+(b2-b1)*t)})`;
}
function showScr(id) {
  ['homeScreen','historyScreen','setupScreen','joinScreen','mainScreen'].forEach(s => $(s).classList.toggle('hidden', s !== id));
}
let _tt;
function toast(msg) {
  const el = $('toast'); el.textContent = msg; el.classList.add('show');
  clearTimeout(_tt); _tt = setTimeout(() => el.classList.remove('show'), 2800);
}
