/**
 * Application configuration constants
 */
const CONFIG = {
  // API endpoints
  API: {
    RECOMMEND: '/api/recommend',
    MODELS: '/api/models'
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
  },
  
  // LLM Model settings
  // These are the available models and effort levels (loaded from backend)
  // Structure: { model: [effort_levels] }
  MODELS: {
    "gpt-5.2": ["none", "low", "medium", "high", "xhigh"],
    "gpt-5-mini": ["minimal", "low", "medium", "high"],
    "gpt-5-nano": ["minimal", "low", "medium", "high"]
  },
  
  // Default model settings
  DEFAULT_MODEL: "gpt-5-mini",
  DEFAULT_EFFORT: "low"
};

// Export for ES6 modules (if needed later)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CONFIG;
}
