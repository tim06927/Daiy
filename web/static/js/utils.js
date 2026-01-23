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
 * Generate unique ID for ARIA relationships
 */
let tooltipIdCounter = 0;
function generateTooltipId() {
  return `tooltip-${++tooltipIdCounter}`;
}

/**
 * Create a help tooltip (? bubble) element with accessibility support
 * @param {string} text - Tooltip text content
 * @param {string} label - Optional label before the ? icon (e.g., "Why")
 * @returns {string} HTML string for tooltip
 */
function createHelpTooltip(text, label = '') {
  if (!text) return '';
  const tooltipId = generateTooltipId();
  const labelHtml = label ? `<span class="tooltip-label">${escapeHtml(label)}</span>` : '';
  return `${labelHtml}<button type="button" class="help-tooltip" onclick="toggleTooltip(event, this)" onkeydown="handleTooltipKeydown(event, this)" aria-expanded="false" aria-describedby="${tooltipId}">?<span class="tooltip-text" id="${tooltipId}" role="tooltip">${escapeHtml(text)}</span></button>`;
}

/**
 * Toggle tooltip visibility (for click/tap support)
 * @param {Event} event - The click event
 * @param {HTMLElement} element - The tooltip element
 */
function toggleTooltip(event, element) {
  // Prevent event from bubbling (important inside <a> elements)
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  
  // Close other open tooltips
  document.querySelectorAll('.help-tooltip.active').forEach(el => {
    if (el !== element) {
      el.classList.remove('active');
      el.setAttribute('aria-expanded', 'false');
    }
  });
  
  const isActive = element.classList.toggle('active');
  element.setAttribute('aria-expanded', isActive ? 'true' : 'false');
}

/**
 * Handle keyboard interactions for tooltips
 * @param {KeyboardEvent} event - The keyboard event
 * @param {HTMLElement} element - The tooltip element
 */
function handleTooltipKeydown(event, element) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    event.stopPropagation();
    toggleTooltip(event, element);
  } else if (event.key === 'Escape') {
    event.preventDefault();
    element.classList.remove('active');
    element.setAttribute('aria-expanded', 'false');
  }
}

// Close tooltips when clicking outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('.help-tooltip')) {
    document.querySelectorAll('.help-tooltip.active').forEach(el => {
      el.classList.remove('active');
      el.setAttribute('aria-expanded', 'false');
    });
  }
});

// Close tooltips on Escape key globally
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.help-tooltip.active').forEach(el => {
      el.classList.remove('active');
      el.setAttribute('aria-expanded', 'false');
    });
  }
});
