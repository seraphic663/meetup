const PREF_KEY = 'mqa_user_preferences';

export const DEFAULT_USER_PREFERENCES = {
  collapsed: true,
  step: 5,
  orientation: 'horizontal',
  theme: 'light',
};

const VALID_STEPS = [5, 10, 15, 20, 30, 60];

function normalizePreferences(raw) {
  const collapsed = raw?.collapsed !== false;
  const step = VALID_STEPS.includes(Number(raw?.step)) ? Number(raw.step) : DEFAULT_USER_PREFERENCES.step;
  const orientation = raw?.orientation === 'vertical' ? 'vertical' : DEFAULT_USER_PREFERENCES.orientation;
  const theme = raw?.theme === 'dark' ? 'dark' : DEFAULT_USER_PREFERENCES.theme;
  return { collapsed, step, orientation, theme };
}

export function applyUserTheme(theme) {
  const nextTheme = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.dataset.theme = nextTheme;
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.content = nextTheme === 'dark' ? '#11151d' : '#416ba5';
  return nextTheme;
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
