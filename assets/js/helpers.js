import { ST_AVAIL, ST_BUSY, ST_EMPTY } from './constants.js';

let toastTimer = null;

export function $(id) {
  return document.getElementById(id);
}

export function pad(num) {
  return String(num).padStart(2, '0');
}

export function dfmt(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function fmtRange(session) {
  return `${session.dateS.slice(5).replace('-', '月')}日 — ${session.dateE.slice(5).replace('-', '月')}日`;
}

export function dayDiff(start, end) {
  return (new Date(end) - new Date(start)) / 86400000;
}

export function esc(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function lerp(hexA, hexB, ratio) {
  const parse = hex => [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16));
  const [r1, g1, b1] = parse(hexA);
  const [r2, g2, b2] = parse(hexB);
  return `rgb(${~~(r1 + (r2 - r1) * ratio)},${~~(g1 + (g2 - g1) * ratio)},${~~(b1 + (b2 - b1) * ratio)})`;
}

export function normalizeAvail(raw) {
  if (!raw) return {};
  const output = {};
  Object.entries(raw).forEach(([date, value]) => {
    output[date] = {};
    if (Array.isArray(value)) {
      value.forEach(hour => {
        output[date][String(hour)] = ST_AVAIL;
      });
      return;
    }
    if (typeof value === 'object') {
      Object.entries(value).forEach(([hour, status]) => {
        output[date][String(hour)] = Number(status) || ST_EMPTY;
      });
    }
  });
  return output;
}

export function getState(dayAvail, hour) {
  if (!dayAvail) return ST_EMPTY;
  const value = dayAvail[String(hour)];
  return value === ST_AVAIL || value === ST_BUSY ? Number(value) : ST_EMPTY;
}

export function getDates(session) {
  const dates = [];
  const current = new Date(`${session.dateS}T00:00:00`);
  const end = new Date(`${session.dateE}T00:00:00`);
  while (current <= end) {
    dates.push(dfmt(current));
    current.setDate(current.getDate() + 1);
  }
  return dates;
}

export function getHours(session) {
  const hours = [];
  for (let hour = session.hourS; hour < session.hourE; hour += 1) {
    hours.push(hour);
  }
  return hours;
}

export function showScreen(id) {
  ['homeScreen', 'historyScreen', 'setupScreen', 'joinScreen', 'mainScreen']
    .forEach(screenId => $(screenId).classList.toggle('hidden', screenId !== id));
}

export function toast(message) {
  const node = $('toast');
  node.textContent = message;
  node.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove('show'), 2800);
}

export function clone(value) {
  return JSON.parse(JSON.stringify(value));
}
