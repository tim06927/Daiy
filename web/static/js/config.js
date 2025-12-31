/**
 * Application configuration constants
 */
const CONFIG = {
  // API endpoints
  API: {
    RECOMMEND: '/api/recommend'
  },
  
  // Image compression settings
  IMAGE: {
    MAX_SIZE: 960,
    JPEG_QUALITY: 0.8,
    BLOB_QUALITY: 0.7
  },
  
  // UI constants
  UI: {
    MAX_TEXTAREA_HEIGHT: 150,
    MIN_TEXTAREA_HEIGHT: 56
  }
};

// Export for ES6 modules (if needed later)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CONFIG;
}
