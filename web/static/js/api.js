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
  
  // Build selected_values for legacy support
  const allSelectedValues = AppState.getAllSelectedValues();
  
  const resp = await fetch(CONFIG.API.RECOMMEND, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      problem_text: problemText,
      clarification_answers: clarificationAnswersToSend,
      selected_values: allSelectedValues,
      image_base64: AppState.compressedImage,
      identified_job: AppState.cachedJob,
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

  // Persist any inferred values from the new API format
  if (data.inferred_values) {
    if (!AppState.selectedSpeed && data.inferred_values.gearing) {
      AppState.selectedSpeed = data.inferred_values.gearing;
    }
    if (!AppState.selectedUseCase && data.inferred_values.use_case) {
      AppState.selectedUseCase = data.inferred_values.use_case;
    }
  }
  // Legacy format support
  if (!AppState.selectedSpeed && data.inferred_speed) {
    AppState.selectedSpeed = data.inferred_speed;
  }
  if (!AppState.selectedUseCase && data.inferred_use_case) {
    AppState.selectedUseCase = data.inferred_use_case;
  }

  return data;
}
