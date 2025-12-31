/**
 * Main application logic and initialization
 */

// DOM elements
let elements = {};

/**
 * Initialize DOM element references
 */
function initElements() {
  elements = {
    initialState: document.getElementById('initial-state'),
    resultsState: document.getElementById('results-state'),
    searchInput: document.getElementById('search-input'),
    searchBtn: document.getElementById('search-btn'),
    uploadInput: document.getElementById('upload-input'),
    uploadBtn: document.getElementById('upload-btn'),
    imagePreview: document.getElementById('image-preview'),
    previewThumb: document.getElementById('preview-thumb'),
    previewName: document.getElementById('preview-name'),
    previewSize: document.getElementById('preview-size'),
    previewRemove: document.getElementById('preview-remove'),
    queryImagePlaceholder: document.getElementById('query-image-placeholder'),
    queryImage: document.getElementById('query-image'),
    queryTextDisplay: document.getElementById('query-text-display'),
    selectedOptionsEl: document.getElementById('selected-options'),
    clarificationPanel: document.getElementById('clarification-panel'),
    clarificationContent: document.getElementById('clarification-content'),
    loadingState: document.getElementById('loading-state'),
    errorMessage: document.getElementById('error-message'),
    productCategories: document.getElementById('product-categories'),
    categoriesContainer: document.getElementById('categories-container'),
  };
}

/**
 * Switch to results state
 */
function switchToResultsState() {
  AppState.currentQuery = elements.searchInput.value.trim();
  elements.queryTextDisplay.textContent = AppState.currentQuery;
  
  // Show image if uploaded
  if (AppState.imageDataUrl) {
    elements.queryImage.src = AppState.imageDataUrl;
    elements.queryImage.classList.remove('hidden');
    elements.queryImagePlaceholder.classList.add('hidden');
  } else {
    elements.queryImage.classList.add('hidden');
    elements.queryImagePlaceholder.classList.remove('hidden');
  }
  
  elements.initialState.classList.add('hidden');
  elements.resultsState.classList.add('active');
  
  // Show loading
  elements.loadingState.classList.add('active');
  elements.productCategories.classList.remove('active');
  elements.errorMessage.classList.add('hidden');
  elements.clarificationPanel.classList.remove('active');
}

/**
 * Reset to initial state
 */
function resetToInitial() {
  elements.resultsState.classList.remove('active');
  elements.initialState.classList.remove('hidden');
  AppState.reset();
  elements.selectedOptionsEl.innerHTML = '';
  elements.clarificationPanel.classList.remove('active');
  elements.productCategories.classList.remove('active');
  elements.loadingState.classList.remove('active');
  elements.errorMessage.classList.add('hidden');
  
  // Reset diagnosis from previous run
  const diagnosisContainer = document.getElementById('diagnosis-container');
  const diagnosisText = document.getElementById('diagnosis-text');
  if (diagnosisContainer) diagnosisContainer.classList.add('hidden');
  if (diagnosisText) diagnosisText.textContent = '';
  
  elements.searchInput.focus();
}

/**
 * Show error message
 */
function showError(message) {
  elements.loadingState.classList.remove('active');
  elements.errorMessage.textContent = message;
  elements.errorMessage.classList.remove('hidden');
}

/**
 * Show results
 */
function showResults(data) {
  elements.loadingState.classList.remove('active');
  elements.clarificationPanel.classList.remove('active');
  updateSelectedOptions();
  
  // Use diagnosis from LLM if available
  const diagnosis = data.diagnosis || '';
  const sections = data.sections || {};
  const finalInstructions = data.final_instructions || [];
  
  // Show diagnosis in left panel
  const diagnosisContainer = document.getElementById('diagnosis-container');
  const diagnosisText = document.getElementById('diagnosis-text');
  if (diagnosis) {
    diagnosisText.textContent = diagnosis;
    diagnosisContainer.classList.remove('hidden');
  } else {
    diagnosisContainer.classList.add('hidden');
  }
  
  // Render product categories (using new structured format if available)
  renderProductCategories(
    data.products_by_category || [],
    sections,
    data.primary_products || [],
    data.optional_extras || data.optional_products || [],
    data.tools || data.tool_products || []
  );
  
  // Render instructions (prefer final_instructions over sections)
  renderInstructions(sections, finalInstructions);
  
  // Setup tabs
  setupResultsTabs();
  
  elements.productCategories.classList.add('active');
}

/**
 * Handle search submission
 */
async function handleSearch() {
  const problemText = elements.searchInput.value.trim();
  
  if (!problemText) {
    elements.searchInput.focus();
    return;
  }

  elements.searchBtn.disabled = true;
  elements.searchBtn.classList.add('loading');
  
  // Switch to results state
  switchToResultsState();

  try {
    const data = await fetchRecommendations(problemText);

    if (data.need_clarification) {
      showClarification(data);
      return;
    }

    // Show results - clear cached job for next search
    AppState.cachedJob = null;
    showResults(data);

  } catch (error) {
    showError(error.message);
  } finally {
    elements.searchBtn.disabled = false;
    elements.searchBtn.classList.remove('loading');
  }
}

/**
 * Initialize event listeners
 */
function initEventListeners() {
  // Search button
  elements.searchBtn.addEventListener('click', handleSearch);
  
  // Enter key to search
  elements.searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  });

  // Auto-resize textarea
  elements.searchInput.addEventListener('input', () => {
    elements.searchInput.style.height = 'auto';
    elements.searchInput.style.height = Math.min(
      elements.searchInput.scrollHeight, 
      CONFIG.UI.MAX_TEXTAREA_HEIGHT
    ) + 'px';
  });
}

/**
 * Initialize application
 */
function initApp() {
  initElements();
  initEventListeners();
  initImageHandlers(elements);
  
  // Focus input on load
  elements.searchInput.focus();
}

// Start app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
