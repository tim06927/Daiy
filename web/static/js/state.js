/**
 * Application state management
 */
const AppState = {
  // Clarification state
  selectedValues: {},
  clarificationAnswers: [],
  pendingClarifications: [],
  
  // Image state
  compressedImage: null,
  imageDataUrl: null,
  
  // Query state
  currentQuery: '',
  cachedJob: null,
  
  // Model settings state (sticky - persisted to localStorage)
  selectedModel: null,
  selectedEffort: null,
  
  // Initialize model settings from localStorage or defaults
  initModelSettings() {
    const savedModel = localStorage.getItem('daiy_model');
    const savedEffort = localStorage.getItem('daiy_effort');
    
    this.selectedModel = savedModel || CONFIG.DEFAULT_MODEL;
    this.selectedEffort = savedEffort || CONFIG.DEFAULT_EFFORT;
    
    // Validate the model/effort combination
    if (!this.isValidModelEffort(this.selectedModel, this.selectedEffort)) {
      this.selectedModel = CONFIG.DEFAULT_MODEL;
      this.selectedEffort = CONFIG.DEFAULT_EFFORT;
    }
  },
  
  // Check if model/effort combination is valid
  isValidModelEffort(model, effort) {
    const efforts = CONFIG.MODELS[model];
    return efforts && efforts.includes(effort);
  },
  
  // Set model (and reset effort if incompatible)
  setModel(model) {
    this.selectedModel = model;
    localStorage.setItem('daiy_model', model);
    
    // Reset effort if not compatible with new model
    if (!this.isValidModelEffort(model, this.selectedEffort)) {
      const defaultEfforts = CONFIG.MODELS[model];
      this.selectedEffort = defaultEfforts ? defaultEfforts[0] : CONFIG.DEFAULT_EFFORT;
      localStorage.setItem('daiy_effort', this.selectedEffort);
    }
  },
  
  // Set effort level
  setEffort(effort) {
    if (this.isValidModelEffort(this.selectedModel, effort)) {
      this.selectedEffort = effort;
      localStorage.setItem('daiy_effort', effort);
    }
  },
  
  // Get current model settings
  getModelSettings() {
    return {
      model: this.selectedModel,
      effort: this.selectedEffort
    };
  },
  
  // Reset state to initial
  reset() {
    this.selectedValues = {};
    this.clarificationAnswers = [];
    this.pendingClarifications = [];
    this.cachedJob = null;
    // Note: model settings are NOT reset - they are sticky
  },
  
  // Reset image state
  resetImage() {
    this.compressedImage = null;
    this.imageDataUrl = null;
  },
  
  // Update selected value for a dimension
  setSelectedValue(dimension, value) {
    // Parse as int if it looks like a number or speed
    if (/^\d+(-speed)?$/.test(value)) {
      this.selectedValues[dimension] = parseInt(value);
    } else {
      this.selectedValues[dimension] = value;
    }
  },
  
  // Clear selected value for a dimension
  clearSelectedValue(dimension) {
    delete this.selectedValues[dimension];
  },
  
  // Get all selected values
  getAllSelectedValues() {
    return { ...this.selectedValues };
  },
  
  // Build clarification answers in new format
  getClarificationAnswers() {
    return Object.entries(this.selectedValues).map(([key, value]) => ({
      spec_name: key,
      answer: value
    }));
  },
  
  // Check if all pending clarifications are answered
  areAllClarificationsAnswered() {
    for (const dim of this.pendingClarifications) {
      if (!this.selectedValues[dim]) {
        return false;
      }
    }
    return this.pendingClarifications.length > 0;
  }
};
