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

function getAccessKey(sessionId) {
  return `mqa_auth_${sessionId}`;
}

export function getSessionAccess(sessionId) {
  try {
    return JSON.parse(localStorage.getItem(getAccessKey(sessionId)) || '{}');
  } catch (_) {
    return {};
  }
}

function saveSessionAccess(sessionId, updater) {
  const current = getSessionAccess(sessionId);
  const next = updater(current);
  localStorage.setItem(getAccessKey(sessionId), JSON.stringify(next));
  return next;
}

export function saveCreatorToken(sessionId, token) {
  if (!token) return;
  saveSessionAccess(sessionId, current => ({ ...current, creatorToken: token }));
}

export function saveParticipantAccess(sessionId, { participantId, participantName, participantToken }) {
  saveSessionAccess(sessionId, current => ({
    ...current,
    participantId: participantId || current.participantId || '',
    participantName: participantName || current.participantName || '',
    participantToken: participantToken || current.participantToken || '',
  }));
  if (participantName) localStorage.setItem(`mqa_${sessionId}`, participantName);
  if (participantName) rememberLastName(participantName);
}

export function clearParticipantAccess(sessionId) {
  saveSessionAccess(sessionId, current => {
    const next = { ...current };
    delete next.participantId;
    delete next.participantName;
    delete next.participantToken;
    return next;
  });
}

export function clearSessionAccess(sessionId) {
  localStorage.removeItem(getAccessKey(sessionId));
}

export function getSessionAuthHeaders(sessionId) {
  const access = getSessionAccess(sessionId);
  const headers = {};
  if (access.creatorToken) headers['X-Creator-Token'] = access.creatorToken;
  if (access.participantToken) headers['X-Participant-Token'] = access.participantToken;
  return headers;
}

export function removeHistoryItem(sessionId) {
  const history = loadHistory().filter(item => item.id !== sessionId);
  localStorage.setItem('mqa_history', JSON.stringify(history));
}

export function getSavedParticipantName(sessionId) {
  const access = getSessionAccess(sessionId);
  return access.participantName || localStorage.getItem(`mqa_${sessionId}`);
}

export function saveParticipantName(sessionId, name) {
  saveParticipantAccess(sessionId, { participantName: name });
}
