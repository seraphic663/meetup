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

export function fmtHour(hour) {
  return `${pad(hour)}:00`;
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

export function getDayTimeWindow(session, date) {
  const baseStart = Number(session?.hourS ?? 9);
  const baseEnd = Number(session?.hourE ?? 21);
  const firstHourS = Number(session?.firstHourS ?? baseStart);
  const lastHourE = Number(session?.lastHourE ?? baseEnd);

  if (session?.dateS === date && session?.dateE === date) {
    return { start: firstHourS, end: lastHourE };
  }
  if (session?.dateS === date) {
    return { start: firstHourS, end: baseEnd };
  }
  if (session?.dateE === date) {
    return { start: baseStart, end: lastHourE };
  }
  return { start: baseStart, end: baseEnd };
}

export function describeTimeWindow(session) {
  if (!session) return '';
  const baseStart = Number(session.hourS ?? 9);
  const baseEnd = Number(session.hourE ?? 21);
  const firstHourS = Number(session.firstHourS ?? baseStart);
  const lastHourE = Number(session.lastHourE ?? baseEnd);
  const parts = [`每日 ${fmtHour(baseStart)}-${fmtHour(baseEnd)}`];

  if (session.dateS === session.dateE) {
    if (firstHourS !== baseStart || lastHourE !== baseEnd) {
      parts.push(`当天实际 ${fmtHour(firstHourS)}-${fmtHour(lastHourE)}`);
    }
    return parts.join(' · ');
  }

  if (firstHourS !== baseStart) parts.push(`首日 ${fmtHour(firstHourS)} 起`);
  if (lastHourE !== baseEnd) parts.push(`末日到 ${fmtHour(lastHourE)}`);
  return parts.join(' · ');
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
