import { esc } from './helpers.js';

export function renderAISummary(text) {
  const lines = String(text || '').split('\n');
  const sections = [];
  let current = { title: '总结', items: [] };

  lines.forEach(rawLine => {
    const line = rawLine.trim();
    if (!line) return;
    if (line.startsWith('## ')) {
      if (current.items.length || current.title !== '总结') sections.push(current);
      current = { title: line.slice(3), items: [] };
      return;
    }
    if (line.startsWith('- ')) {
      current.items.push({ type: 'bullet', value: line.slice(2) });
      return;
    }
    current.items.push({ type: 'text', value: line.replace(/^\d+\.\s*/, '') });
  });

  if (current.items.length || !sections.length) sections.push(current);

  return sections.map(section => `
    <div class="ai-section">
      <div class="ai-section-title">${esc(section.title)}</div>
      <div class="ai-section-body">
        ${section.items.map(item => item.type === 'bullet'
          ? `<div class="ai-item"><div class="ai-item-emoji">•</div><div class="ai-item-text">${esc(item.value)}</div></div>`
          : `<div class="ai-item-text">${esc(item.value)}</div>`
        ).join('')}
      </div>
    </div>
  `).join('');
}
