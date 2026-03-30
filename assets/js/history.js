export function loadHistory() {
  return JSON.parse(localStorage.getItem('mqa_history') || '[]');
}

export function saveToHistory(sid, name, dateS, dateE) {
  let history = loadHistory();
  history = history.filter(item => item.id !== sid);
  history.unshift({ id: sid, name, dateS, dateE, visited: Date.now() });
  history = history.slice(0, 5);
  localStorage.setItem('mqa_history', JSON.stringify(history));
}

export function rememberLastName(name) {
  if (name) localStorage.setItem('mqa_last_name', name);
}

export function getLastName() {
  return localStorage.getItem('mqa_last_name') || '';
}

export function getSavedParticipantName(sessionId) {
  return localStorage.getItem(`mqa_${sessionId}`);
}

export function saveParticipantName(sessionId, name) {
  localStorage.setItem(`mqa_${sessionId}`, name);
  rememberLastName(name);
}
