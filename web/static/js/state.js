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
  
  // Reset state to initial
  reset() {
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
