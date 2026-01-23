/**
 * Shared utility functions
 */

/**
 * Escape HTML to prevent XSS
 * @param {*} value - Value to escape
 * @returns {string} Escaped HTML string
 */
function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Create a help tooltip (? bubble) element
 * @param {string} text - Tooltip text content
 * @param {string} label - Optional label before the ? icon (e.g., "Why")
 * @returns {string} HTML string for tooltip
 */
function createHelpTooltip(text, label = '') {
  if (!text) return '';
  const labelHtml = label ? `<span class="tooltip-label">${escapeHtml(label)}</span>` : '';
  return `${labelHtml}<span class="help-tooltip" onclick="toggleTooltip(this)" tabindex="0">?<span class="tooltip-text">${escapeHtml(text)}</span></span>`;
}

/**
 * Toggle tooltip visibility (for mobile click support)
 * @param {HTMLElement} element - The tooltip element
 */
function toggleTooltip(element) {
  // Close other open tooltips
  document.querySelectorAll('.help-tooltip.active').forEach(el => {
    if (el !== element) el.classList.remove('active');
  });
  element.classList.toggle('active');
}

// Close tooltips when clicking outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('.help-tooltip')) {
    document.querySelectorAll('.help-tooltip.active').forEach(el => {
      el.classList.remove('active');
    });
  }
});
