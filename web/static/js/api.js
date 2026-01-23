/**
 * API communication with backend
 */

/**
 * Send recommendation request to backend
 * @param {string} problemText - User's problem description
 * @returns {Promise<Object>} API response data
 */
async function fetchRecommendations(problemText) {
  // Build clarification_answers from selected values (new format)
  const clarificationAnswersToSend = AppState.getClarificationAnswers();
  
  // Get current model settings
  const modelSettings = AppState.getModelSettings();
  
  const resp = await fetch(CONFIG.API.RECOMMEND, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      problem_text: problemText,
      clarification_answers: clarificationAnswersToSend,
      image_base64: AppState.compressedImage,
      identified_job: AppState.cachedJob,
      model: modelSettings.model,
      effort: modelSettings.effort,
    }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `Server error (${resp.status})`);
  }

  const data = await resp.json();

  // Cache job identification for subsequent requests
  if (data.job) {
    AppState.cachedJob = data.job;
  }

  return data;
}

/**
 * Fetch available models and their effort levels from backend
 * @returns {Promise<Object>} Models configuration
 */
async function fetchModels() {
  try {
    const resp = await fetch(CONFIG.API.MODELS);
    if (resp.ok) {
      const data = await resp.json();
      // Update CONFIG with server-side values
      if (data.models) {
        CONFIG.MODELS = data.models;
      }
      if (data.default_model) {
        CONFIG.DEFAULT_MODEL = data.default_model;
      }
      if (data.default_effort) {
        CONFIG.DEFAULT_EFFORT = data.default_effort;
      }
      return data;
    }
  } catch (e) {
    console.warn('Failed to fetch models from server, using defaults:', e);
  }
  return null;
}
