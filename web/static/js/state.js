/**
 * Application state management
 */
const AppState = {
  // Clarification state
  selectedSpeed: null,
  selectedUseCase: null,
  selectedValues: {},
  clarificationAnswers: [],
  pendingClarifications: [],
  
  // Image state
  compressedImage: null,
  imageDataUrl: null,
  
  // Query state
  currentQuery: '',
  cachedJob: null,
  
  // Reset state to initial
  reset() {
    this.selectedSpeed = null;
    this.selectedUseCase = null;
    this.selectedValues = {};
    this.clarificationAnswers = [];
    this.pendingClarifications = [];
    this.cachedJob = null;
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
    
    // Map to legacy variables for backward compat
    if (dimension === 'gearing' || dimension === 'drivetrain_speed') {
      this.selectedSpeed = this.selectedValues[dimension];
    } else if (dimension === 'use_case') {
      this.selectedUseCase = this.selectedValues[dimension];
    }
  },
  
  // Clear selected value for a dimension
  clearSelectedValue(dimension) {
    delete this.selectedValues[dimension];
    if (dimension === 'gearing' || dimension === 'drivetrain_speed') {
      this.selectedSpeed = null;
    }
    if (dimension === 'use_case') {
      this.selectedUseCase = null;
    }
  },
  
  // Get all selected values including legacy
  getAllSelectedValues() {
    const allValues = { ...this.selectedValues };
    if (this.selectedSpeed && !allValues.gearing && !allValues.drivetrain_speed) {
      allValues.gearing = this.selectedSpeed;
    }
    if (this.selectedUseCase && !allValues.use_case) {
      allValues.use_case = this.selectedUseCase;
    }
    return allValues;
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
      const hasValue = this.selectedValues[dim] || 
        (dim === 'gearing' && this.selectedSpeed) ||
        (dim === 'drivetrain_speed' && this.selectedSpeed) ||
        (dim === 'use_case' && this.selectedUseCase);
      if (!hasValue) {
        return false;
      }
    }
    return this.pendingClarifications.length > 0;
  }
};
