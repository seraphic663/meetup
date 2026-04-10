const PREF_KEY = 'mqa_user_preferences';

export const DEFAULT_USER_PREFERENCES = {
  layout: 'pr',
  collapsed: true,
};

function normalizePreferences(raw) {
  const layout = raw?.layout === 'tr' ? 'tr' : 'pr';
  const collapsed = raw?.collapsed !== false;
  return { layout, collapsed };
}

export function getUserPreferences() {
  try {
    return normalizePreferences(JSON.parse(localStorage.getItem(PREF_KEY) || '{}'));
  } catch (_) {
    return { ...DEFAULT_USER_PREFERENCES };
  }
}

export function saveUserPreferences(preferences) {
  const next = normalizePreferences(preferences);
  localStorage.setItem(PREF_KEY, JSON.stringify(next));
  return next;
}
