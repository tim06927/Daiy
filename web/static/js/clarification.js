/**
 * Clarification UI rendering and interaction
 */

/**
 * Show clarification panel with questions
 * @param {Object} data - Response data containing clarification questions
 */
function showClarification(data) {
  const loadingState = document.getElementById('loading-state');
  const clarificationPanel = document.getElementById('clarification-panel');
  const clarificationContent = document.getElementById('clarification-content');
  const productCategories = document.getElementById('product-categories');
  const categoriesContainer = document.getElementById('categories-container');
  
  loadingState.classList.remove('active');
  
  // Update selected options display
  updateSelectedOptions();
  
  // Show clarification panel
  clarificationContent.innerHTML = '';
  
  // Handle new clarification_questions format
  const questions = data.clarification_questions || [];
  
  // Track what's needed
  AppState.pendingClarifications = [];
  AppState.clarificationAnswers = [];
  
  // Process clarification questions FIRST
  if (questions.length > 0) {
    questions.forEach(q => {
      // Skip if already answered
      if (AppState.selectedValues[q.spec_name]) return;
      
      AppState.pendingClarifications.push(q.spec_name);
      
      const section = document.createElement('div');
      section.className = 'clarification-section';
      section.innerHTML = `
        <div class="clarification-label">${q.question}</div>
        ${q.hint ? `<div class="clarification-hint">💡 ${q.hint}</div>` : ''}
        <div class="option-buttons" id="${q.spec_name}-buttons"></div>
        <div class="other-input-container" id="${q.spec_name}-other-container">
          <input type="text" class="other-input" id="${q.spec_name}-other-input" placeholder="Enter your answer...">
        </div>
      `;
      clarificationContent.appendChild(section);
      
      const btnsContainer = section.querySelector(`#${q.spec_name}-buttons`);
      (q.options || []).forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'option-btn';
        btn.textContent = opt;
        btn.dataset.value = opt;
        btn.onclick = () => selectDimension(q.spec_name, opt, btn);
        btnsContainer.appendChild(btn);
      });
      
      // Add "Other" button
      const otherBtn = document.createElement('button');
      otherBtn.className = 'option-btn';
      otherBtn.textContent = 'Other';
      otherBtn.onclick = () => showOtherInputGeneric(q.spec_name, otherBtn);
      btnsContainer.appendChild(otherBtn);
      
      // Handle other input
      const otherInput = section.querySelector(`#${q.spec_name}-other-input`);
      otherInput.addEventListener('input', () => {
        if (otherInput.value.trim()) {
          AppState.selectedValues[q.spec_name] = otherInput.value.trim();
          updateSubmitButton();
        }
      });
    });
  }
  
  // Add Find Parts button after questions
  const submitBtn = document.createElement('button');
  submitBtn.id = 'clarification-submit';
  submitBtn.className = 'clarification-submit';
  submitBtn.textContent = 'Find Parts →';
  submitBtn.onclick = submitClarifications;
  clarificationContent.appendChild(submitBtn);
  
  // Show instructions preview at the bottom if available
  const instructionsPreview = data.instructions_preview || [];
  if (instructionsPreview.length > 0) {
    const previewSection = document.createElement('div');
    previewSection.className = 'clarification-preview';
    previewSection.innerHTML = `
      <div class="clarification-label">Preliminary Instructions:</div>
      <ul class="preview-instructions">
        ${instructionsPreview.map(step => `<li>${step}</li>`).join('')}
      </ul>
    `;
    clarificationContent.appendChild(previewSection);
  }
  
  clarificationPanel.classList.add('active');
  productCategories.classList.add('active');
  categoriesContainer.innerHTML = '';
  updateSubmitButton();
}

/**
 * Select a dimension value (e.g., speed, use_case)
 */
function selectDimension(dim, value, btn) {
  AppState.setSelectedValue(dim, value);
  
  // Update button states
  const btnsContainer = document.getElementById(`${dim}-buttons`);
  if (btnsContainer) {
    btnsContainer.querySelectorAll('.option-btn').forEach(b => b.classList.remove('selected'));
    if (btn) btn.classList.add('selected');
  }
  
  // Hide other input if showing
  const otherContainer = document.getElementById(`${dim}-other-container`);
  if (otherContainer) {
    otherContainer.classList.remove('active');
    otherContainer.querySelector('.other-input').value = '';
  }
  
  updateSelectedOptions();
  updateSubmitButton();
}

/**
 * Show "Other" input field for custom values
 */
function showOtherInputGeneric(dim, btn) {
  const container = document.getElementById(`${dim}-other-container`);
  const buttonsContainer = document.getElementById(`${dim}-buttons`);
  
  // Deselect all buttons in this section
  buttonsContainer.querySelectorAll('.option-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  
  // Clear the selection
  AppState.clearSelectedValue(dim);
  
  // Show input container
  container.classList.add('active');
  container.querySelector('.other-input').focus();
  
  updateSelectedOptions();
  updateSubmitButton();
}

/**
 * Legacy functions for backward compatibility
 */
function selectSpeed(speed, btn) {
  selectDimension('gearing', speed, btn);
}

function selectUseCase(useCase, btn) {
  selectDimension('use_case', useCase, btn);
}

function showOtherInput(type, btn) {
  const dim = type === 'speed' ? 'gearing' : 'use_case';
  showOtherInputGeneric(dim, btn);
}

/**
 * Update submit button visibility based on answered questions
 */
function updateSubmitButton() {
  const submitBtn = document.getElementById('clarification-submit');
  if (!submitBtn) return;
  
  if (AppState.areAllClarificationsAnswered()) {
    submitBtn.classList.add('visible');
  } else {
    submitBtn.classList.remove('visible');
  }
}

/**
 * Submit clarifications and trigger new search
 */
function submitClarifications() {
  const loadingState = document.getElementById('loading-state');
  const productCategories = document.getElementById('product-categories');
  const submitBtn = document.getElementById('clarification-submit');
  
  loadingState.classList.add('active');
  productCategories.classList.remove('active');
  submitBtn.classList.remove('visible');
  
  handleSearch();
}

/**
 * Update selected options display in left panel
 */
function updateSelectedOptions() {
  const selectedOptionsEl = document.getElementById('selected-options');
  selectedOptionsEl.innerHTML = '';
  
  // Show all selected values from clarifications (new format)
  Object.entries(AppState.selectedValues).forEach(([specName, value]) => {
    const opt = document.createElement('div');
    opt.className = 'selected-option';
    
    // Format label: convert spec_name to readable format
    const label = specName
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
    
    // Format value
    let displayValue = value;
    if (typeof value === 'number' && specName.includes('speed')) {
      displayValue = `${value}-speed`;
    }
    
    opt.innerHTML = `
      <span class="label">${label}:</span>
      <span class="value">${displayValue}</span>
      <span class="check">✓</span>
    `;
    selectedOptionsEl.appendChild(opt);
  });
  
  // Legacy support: show speed/use_case if set but not in selectedValues
  if (AppState.selectedSpeed && !AppState.selectedValues['gearing'] && !AppState.selectedValues['drivetrain_speed']) {
    const opt = document.createElement('div');
    opt.className = 'selected-option';
    opt.innerHTML = `
      <span class="label">Speed:</span>
      <span class="value">${AppState.selectedSpeed}-speed</span>
      <span class="check">✓</span>
    `;
    selectedOptionsEl.appendChild(opt);
  }
  
  if (AppState.selectedUseCase && !AppState.selectedValues['use_case']) {
    const opt = document.createElement('div');
    opt.className = 'selected-option';
    opt.innerHTML = `
      <span class="label">Use:</span>
      <span class="value">${AppState.selectedUseCase}</span>
      <span class="check">✓</span>
    `;
    selectedOptionsEl.appendChild(opt);
  }
}
