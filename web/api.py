"""API endpoints for product recommendations.

This module provides the recommendation flow:
1. Job identification - generate step-by-step instructions and identify unclear specs
2. Clarification - gather user answers for unclear specifications  
3. Recommendation - match products and finalize instructions

The /api/recommend endpoint uses this flow.
"""

import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import Blueprint, Response, jsonify, request

# Handle imports for both direct execution and package import
if __package__ is None or __package__ == "":
    # Running directly - add parent to path for absolute imports
    sys.path.insert(0, str(Path(__file__).parent))
    from candidate_selection import (
        select_candidates_dynamic,
        validate_categories,
    )
    from catalog import get_categories as get_catalog_categories
    from categories import (
        PRODUCT_CATEGORIES,
        SHARED_FIT_DIMENSIONS,
        get_clarification_fields,
        get_fit_dimensions_for_categories,
    )
    from error_logging import (
        log_llm_error,
        log_validation_error,
        log_database_error,
        log_processing_error,
        log_unexpected_error,
        log_interaction as log_interaction_db,
    )
    from job_identification import (
        JobIdentification,
        UnclearSpecification,
        identify_job,
        merge_inferred_with_user_selections,
        extract_categories_from_instructions,
    )
    from logging_utils import log_interaction, log_performance
    from prompts import (
        build_recommendation_context,
        make_recommendation_prompt,
    )
    from timing import timer, get_timings, reset_timings
else:
    # Running as package
    from .candidate_selection import (
        select_candidates_dynamic,
        validate_categories,
    )
    from .catalog import get_categories as get_catalog_categories
    from .categories import (
        PRODUCT_CATEGORIES,
        SHARED_FIT_DIMENSIONS,
        get_clarification_fields,
        get_fit_dimensions_for_categories,
    )
    from .error_logging import (
        log_llm_error,
        log_validation_error,
        log_database_error,
        log_processing_error,
        log_unexpected_error,
        log_interaction as log_interaction_db,
    )
    from .job_identification import (
        JobIdentification,
        UnclearSpecification,
        identify_job,
        merge_inferred_with_user_selections,
        extract_categories_from_instructions,
    )
    from .logging_utils import log_interaction, log_performance
    from .prompts import (
        build_recommendation_context,
        make_recommendation_prompt,
    )
    from .timing import timer, get_timings, reset_timings

__all__ = ["api"]

logger = logging.getLogger(__name__)

# Create blueprint for API
api = Blueprint("api", __name__, url_prefix="/api")


def _log_interaction_both(
    event_type: str,
    request_id: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Log interaction to both JSONL (local) and database (Render)."""
    # Log to JSONL for local development
    log_interaction(event_type, data or {})
    # Log to database for production persistence
    try:
        log_interaction_db(event_type, request_id, data)
    except Exception as e:
        logger.error(f"Failed to log interaction to database: {e}")


def _process_image_for_openai(
    image_base64: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Process and validate image for OpenAI.
    
    Returns (processed_base64, mime_type, error_message).
    """
    if __package__ is None or __package__ == "":
        from image_utils import process_image_for_openai
    else:
        from .image_utils import process_image_for_openai
    return process_image_for_openai(image_base64)


def _call_llm_recommendation(
    prompt: str,
    image_base64: Optional[str] = None,
    image_meta: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    model: Optional[str] = None,
    effort: Optional[str] = None,
) -> Dict[str, Any]:
    """Call LLM for recommendation and parse response.
    
    Args:
        prompt: Recommendation prompt.
        image_base64: Optional base64 image.
        image_meta: Optional image metadata.
        request_id: Request ID for error tracking.
        model: Optional model name to use. Defaults to DEFAULT_MODEL.
        effort: Optional reasoning effort level. Defaults to DEFAULT_EFFORT.
        
    Returns:
        Parsed recommendation dict.
    """
    from openai import OpenAI
    if __package__ is None or __package__ == "":
        from config import DEFAULT_MODEL, DEFAULT_EFFORT, is_valid_model_effort
    else:
        from .config import DEFAULT_MODEL, DEFAULT_EFFORT, is_valid_model_effort
    
    # Use provided model/effort or defaults
    selected_model = model if model else DEFAULT_MODEL
    selected_effort = effort if effort else DEFAULT_EFFORT
    
    # Validate model/effort combination, fall back to defaults if invalid
    if not is_valid_model_effort(selected_model, selected_effort):
        logger.warning(
            f"Invalid model/effort combination: {selected_model}/{selected_effort}. "
            f"Using defaults: {DEFAULT_MODEL}/{DEFAULT_EFFORT}"
        )
        selected_model = DEFAULT_MODEL
        selected_effort = DEFAULT_EFFORT
    
    client = OpenAI()
    
    log_interaction(
        "llm_call_recommendation",
        {
            "request_id": request_id,
            "model": selected_model,
            "reasoning_effort": selected_effort,
            "prompt": prompt,
            "image_attached": bool(image_base64),
            "image_meta": image_meta or {},
        },
    )
    
    input_payload = [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]
    if image_base64:
        input_payload.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_base64}",
                    }
                ],
            }
        )
    
    try:
        # Use new API request structure with reasoning effort
        resp = client.responses.create(
            model=selected_model,
            input=input_payload,
            reasoning={"effort": selected_effort},
        )
        
        for item in resp.output:
            if hasattr(item, "content") and item.content is not None:
                raw = item.content[0].text  # type: ignore[union-attr]
                
                log_interaction(
                    "llm_response_recommendation",
                    {
                        "request_id": request_id,
                        "model": selected_model,
                        "reasoning_effort": selected_effort,
                        "raw_response": raw,
                    },
                )
                
                try:
                    parsed = json.loads(raw)
                    return parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError as e:
                    error_msg = f"Failed to parse LLM response as JSON: {str(e)}"
                    log_interaction(
                        "llm_parse_error",
                        {"request_id": request_id, "error": str(e), "raw": raw[:200], "stage": "recommendation"},
                    )
                    log_llm_error(
                        error_msg,
                        request_id=request_id,
                        phase="recommendation",
                        operation="parse_json",
                        context={"raw_length": len(raw), "error": str(e)},
                        recovery_suggestion="Check LLM response format - should be valid JSON",
                    )
                    return {}
                    
    except Exception as e:
        error_msg = f"LLM API error during recommendation: {str(e)}"
        log_interaction("llm_error", {"request_id": request_id, "error": str(e), "stage": "recommendation"})
        log_llm_error(
            error_msg,
            request_id=request_id,
            phase="recommendation",
            operation="llm_call",
            context={"model": selected_model, "error_type": type(e).__name__},
            recovery_suggestion="Check OpenAI API status and quota",
        )
        logger.exception("Error calling LLM for recommendation")
        
    return {}


def _call_llm_clarification(
    prompt: str,
    image_base64: Optional[str] = None,
    model: Optional[str] = None,
    effort: Optional[str] = None,
) -> Dict[str, Any]:
    """Call LLM for clarification and parse response.
    
    Args:
        prompt: Clarification prompt.
        image_base64: Optional base64 image.
        model: Optional model name to use. Defaults to DEFAULT_MODEL.
        effort: Optional reasoning effort level. Defaults to DEFAULT_EFFORT.
        
    Returns:
        Dict with inferred_values and options.
    """
    from openai import OpenAI
    if __package__ is None or __package__ == "":
        from config import DEFAULT_MODEL, DEFAULT_EFFORT, is_valid_model_effort
    else:
        from .config import DEFAULT_MODEL, DEFAULT_EFFORT, is_valid_model_effort
    
    # Use provided model/effort or defaults
    selected_model = model if model else DEFAULT_MODEL
    selected_effort = effort if effort else DEFAULT_EFFORT
    
    # Validate model/effort combination, fall back to defaults if invalid
    if not is_valid_model_effort(selected_model, selected_effort):
        logger.warning(
            f"Invalid model/effort combination: {selected_model}/{selected_effort}. "
            f"Using defaults: {DEFAULT_MODEL}/{DEFAULT_EFFORT}"
        )
        selected_model = DEFAULT_MODEL
        selected_effort = DEFAULT_EFFORT
    
    client = OpenAI()
    
    log_interaction(
        "llm_call_clarification",
        {
            "model": selected_model,
            "reasoning_effort": selected_effort,
            "prompt": prompt,
            "image_attached": bool(image_base64),
        },
    )
    
    input_payload = [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]
    if image_base64:
        input_payload.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_base64}",
                    }
                ],
            }
        )
    
    try:
        # Use new API request structure with reasoning effort
        resp = client.responses.create(
            model=selected_model,
            input=input_payload,
            reasoning={"effort": selected_effort},
        )
        
        for item in resp.output:
            if hasattr(item, "content") and item.content is not None:
                raw = item.content[0].text  # type: ignore[union-attr]
                
                log_interaction(
                    "llm_response_clarification",
                    {
                        "model": selected_model,
                        "reasoning_effort": selected_effort,
                        "raw_response": raw,
                    },
                )
                
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    log_interaction(
                        "llm_parse_error",
                        {"error": str(e), "raw": raw, "stage": "clarification"},
                    )
                    
    except Exception as e:
        log_interaction("llm_error", {"error": str(e), "stage": "clarification"})
        logger.exception("Error calling LLM for clarification")
    
    return {"inferred_values": {}, "options": {}}


@api.route("/recommend", methods=["POST"])
def recommend() -> Union[Tuple[Response, int], Response]:
    """Product recommendation endpoint with step-by-step instructions.
    
    Request JSON:
        {
            "problem_text": "User's description of needs",
            "image_base64": "optional base64 image",
            "clarification_answers": [{"spec_name": "x", "answer": "y"}, ...],
            "identified_job": {...},  // Cached job identification
            "model": "gpt-5-mini",  // Optional: LLM model to use
            "effort": "low"  // Optional: Reasoning effort level
        }
    
    Response JSON (need_clarification=true):
        {
            "need_clarification": true,
            "job": {...},
            "clarification_questions": [
                {
                    "spec_name": "drivetrain_speed",
                    "question": "How many speeds is your drivetrain?",
                    "hint": "Count the cogs on your rear cassette.",
                    "options": ["8-speed", "9-speed", "10-speed", "11-speed", "12-speed"]
                }
            ]
        }
    
    Response JSON (recommendation):
        {
            "diagnosis": "...",
            "final_instructions": [...],
            "primary_products": [...],
            "tools": [...],
            "optional_extras": [...],
            "job": {...}
        }
    """
    # Initialize timing tracker for this request
    reset_timings()
    request_id = str(uuid.uuid4())[:8]
    
    try:
        data = request.get_json(force=True)
    except Exception as e:
        log_validation_error(
            f"Invalid JSON in request: {str(e)}",
            request_id=request_id,
            operation="parse_json",
            context={"error_type": type(e).__name__},
            recovery_suggestion="Ensure request body is valid JSON",
        )
        return jsonify({"error": "Invalid JSON in request"}), 400
    
    try:
        # Validate problem_text is a string
        problem_text = data.get("problem_text", "")
        if not isinstance(problem_text, str):
            log_validation_error(
                "problem_text must be a string",
                request_id=request_id,
                operation="validate_input",
                context={"type_received": type(problem_text).__name__},
            )
            return jsonify({"error": "problem_text must be a string"}), 400
        
        problem_text = problem_text.strip()
        
        clarification_answers = data.get("clarification_answers", [])
        cached_job = data.get("identified_job")
        # Legacy support
        selected_values = data.get("selected_values", {})
        
        # Extract model settings from request (optional)
        selected_model = data.get("model")
        selected_effort = data.get("effort")
        
        # Process image
        raw_image_b64 = data.get("image_base64")
        try:
            processed_image, image_mime, image_error = _process_image_for_openai(raw_image_b64)
            
            if image_error:
                log_processing_error(
                    image_error,
                    request_id=request_id,
                    operation="process_image",
                    recovery_suggestion="Try uploading a different image or a smaller file",
                )
                return jsonify({"error": image_error}), 400
        except Exception as e:
            log_processing_error(
                f"Image processing failed: {str(e)}",
                request_id=request_id,
                operation="process_image",
                context={"error_type": type(e).__name__},
            )
            return jsonify({"error": "Image processing failed"}), 400
        
        image_meta = {
            "uploaded": bool(raw_image_b64),
            "processed": bool(processed_image),
            "mime_type": image_mime,
        }
        
        if not problem_text:
            log_validation_error(
                "problem_text is required",
                request_id=request_id,
                operation="validate_input",
            )
            return jsonify({"error": "problem_text is required"}), 400
        
        # Log user input with model settings
        if not cached_job:
            _log_interaction_both(
                "user_input",
                request_id,
                {
                    "problem_text": problem_text,
                    "image_meta": image_meta,
                    "has_clarifications": bool(clarification_answers),
                    "clarification_answers": clarification_answers if clarification_answers else [],
                    "model": selected_model,
                    "reasoning_effort": selected_effort,
                },
            )
        
        # Step 1: Job Identification (use cached if available)
        if cached_job:
            job = JobIdentification.from_dict(cached_job)
            _log_interaction_both("job_identification_cached", request_id, job.to_dict())
        else:
            with timer("llm_call_job_identification"):
                job = identify_job(
                    problem_text,
                    processed_image,
                    image_meta,
                    model=selected_model,
                    effort=selected_effort,
                )
        
        # Validate categories against available catalog (memory-efficient SQL query)
        try:
            with timer("app_validate_categories"):
                referenced_categories = job.referenced_categories or job.categories
                valid_categories = validate_categories(referenced_categories)
        except Exception as e:
            log_database_error(
                f"Failed to validate categories: {str(e)}",
                request_id=request_id,
                operation="validate_categories",
                context={"referenced": referenced_categories if 'referenced_categories' in locals() else []},
            )
            return jsonify({"error": "Database error validating categories"}), 500
        
        if not valid_categories:
            return jsonify({
                "error": "No matching product categories found for your request.",
                "identified_categories": referenced_categories,
                "hint": "Try being more specific about what products you need.",
            }), 404
        
        # Update job with validated categories
        job.categories = valid_categories
        
        # Step 2: Check for unclear specifications needing clarification
        unclear_specs = job.unclear_specifications
        
        # Filter out specs that already have answers
        answered_spec_names = {a.get("spec_name") for a in clarification_answers}
        unanswered_specs = [
            spec for spec in unclear_specs 
            if spec.spec_name not in answered_spec_names
        ]
        
        # Merge inferred with user selections
        with timer("app_merge_selections"):
            known_values = merge_inferred_with_user_selections(job, selected_values)
        
        # Add clarification answers to known values
        for answer in clarification_answers:
            spec_name = answer.get("spec_name")
            value = answer.get("answer")
            if spec_name and value:
                known_values[spec_name] = value
        
        # If we have unanswered unclear specs, ask for clarification
        if unanswered_specs:
            # Build clarification questions from unclear specs
            questions = [spec.to_dict() for spec in unanswered_specs]
            
            # Log that we're asking for clarification
            _log_interaction_both(
                "clarification_required",
                request_id,
                {
                    "questions": questions,
                    "instructions_preview": job.instructions,
                    "inferred_values": known_values,
                },
            )
            
            # Log partial performance metrics
            timings = get_timings()
            log_performance(timings, request_id=request_id)
            
            return jsonify({
                "need_clarification": True,
                "job": job.to_dict(),
                "clarification_questions": questions,
                "instructions_preview": job.instructions,
                "inferred_values": known_values,
            }), 200
        
        # Step 3: Select products for all referenced categories
        try:
            with timer("app_candidate_selection"):
                candidates = select_candidates_dynamic(valid_categories, known_values)
        except Exception as e:
            log_database_error(
                f"Failed to select candidates: {str(e)}",
                request_id=request_id,
                operation="select_candidates",
                context={"categories": valid_categories, "error_type": type(e).__name__},
            )
            return jsonify({"error": "Failed to find matching products"}), 500
        
        # Log what we found
        _log_interaction_both("candidate_selection", request_id, {
            "categories": valid_categories,
            "known_values": known_values,
            "candidates_count": {cat: len(prods) for cat, prods in candidates.items()},
        })
        
        # Check for empty categories (categories in the instructions but with no products)
        empty_categories = [cat for cat in valid_categories if not candidates.get(cat)]
        if empty_categories:
            logger.warning(f"Empty product categories needed: {empty_categories}")
            return jsonify({
                "need_clarification": False,
                "error": "empty_categories",
                "message": "Some of the product categories needed for your project have no products available.",
                "empty_categories": empty_categories,
                "job": job.to_dict(),
                "instructions": job.instructions,
                "available_categories": [cat for cat in valid_categories if candidates.get(cat)],
                "hint": "This typically means the product database needs to be refreshed or expanded.",
            }), 422
        
        # Step 4: Build recommendation context and prompt
        try:
            with timer("app_build_context"):
                context = build_recommendation_context(
                    problem_text=problem_text,
                    instructions=job.instructions,
                    clarifications=clarification_answers,
                    category_products=candidates,
                    image_base64=processed_image,
                )
            
            with timer("app_build_prompt"):
                prompt = make_recommendation_prompt(context, bool(processed_image))
        except Exception as e:
            log_processing_error(
                f"Failed to build recommendation context: {str(e)}",
                request_id=request_id,
                operation="build_context",
                context={"error_type": type(e).__name__},
            )
            return jsonify({"error": "Failed to build recommendation"}), 500
        
        # Step 5: Call LLM for final recommendation
        with timer("llm_call_recommendation"):
            llm_payload = _call_llm_recommendation(
                prompt,
                processed_image,
                image_meta,
                request_id=request_id,
                model=selected_model,
                effort=selected_effort,
            )
        
        # Step 6: Parse and format response
        with timer("app_format_response"):
            recipe = None
            final_instructions = job.instructions
            
            if "recipe" in llm_payload:
                recipe = llm_payload.get("recipe", {})
                # Extract steps from recipe for display
                final_instructions = recipe.get("steps", final_instructions)
            
            diagnosis = llm_payload.get("diagnosis", "")
            
            # Build product responses
            def _build_product_response(
                product_ref: Dict[str, Any],
                candidates: Dict[str, List[Dict[str, Any]]],
            ) -> Optional[Dict[str, Any]]:
                """Convert LLM product reference to full product response."""
                category = product_ref.get("category")
                index = product_ref.get("product_index", 0)
                reasoning = product_ref.get("reasoning", "")
                
                if not category or category not in candidates:
                    return None
                
                products = candidates[category]
                if not products or index >= len(products):
                    return None
                
                product = products[index]
                config = PRODUCT_CATEGORIES.get(category, {})
                
                return {
                    "category": category,
                    "category_display": config.get("display_name", category.replace("_", " ").title()),
                    "product": product,
                    "reasoning": reasoning,
                }
            
            # Process primary products
            primary_products = []
            for ref in llm_payload.get("primary_products", []):
                prod = _build_product_response(ref, candidates)
                if prod:
                    primary_products.append(prod)
            
            # Process tools
            tools = []
            for ref in llm_payload.get("tools", []):
                prod = _build_product_response(ref, candidates)
                if prod:
                    tools.append(prod)
            
            # Process optional extras (max 3)
            optional_extras = []
            for ref in llm_payload.get("optional_extras", [])[:3]:
                prod = _build_product_response(ref, candidates)
                if prod:
                    optional_extras.append(prod)
        
        # Log final recommendation result
        _log_interaction_both(
            "recommendation_result",
            request_id,
            {
                "diagnosis": diagnosis,
                "final_instructions": final_instructions,
                "primary_products_count": len(primary_products),
                "tools_count": len(tools),
                "optional_extras_count": len(optional_extras),
                "fit_values": known_values,
            },
        )
        
        # Log full performance metrics at the end of successful recommendation
        timings = get_timings()
        log_performance(timings, request_id=request_id)
        
        return jsonify({
            # New recipe format
            "recipe": recipe if recipe else None,
            # Standard format
            "diagnosis": diagnosis,
            "final_instructions": final_instructions,
            "primary_products": primary_products,
            "tools": tools,
            "optional_extras": optional_extras,
            "job": job.to_dict(),
            "fit_values": known_values,
        })
        
    except Exception as e:
        # Catch any unexpected errors
        log_unexpected_error(
            f"Unexpected error in recommendation flow: {str(e)}",
            request_id=request_id,
            operation="recommend",
            user_input=data.get("problem_text", "")[:200] if 'data' in locals() else None,
            context={
                "error_type": type(e).__name__,
                "endpoint": "/api/recommend",
            }
        )
        logger.exception(f"Unexpected error in /api/recommend for request {request_id}")
        return jsonify({
            "error": "An unexpected error occurred",
            "request_id": request_id,
            "message": "Please report this issue with the request ID above",
        }), 500


@api.route("/categories", methods=["GET"])
def list_categories() -> Response:
    """List available product categories.
    
    Returns:
        JSON list of category configurations.
    """
    # Use lightweight SQL query instead of loading full catalog
    available = set(get_catalog_categories())
    
    categories = []
    for key, config in PRODUCT_CATEGORIES.items():
        if key in available:
            categories.append({
                "key": key,
                "display_name": config["display_name"],
                "description": config["description"],
                "fit_dimensions": config["fit_dimensions"],
            })
    
    return jsonify({"categories": categories})


@api.route("/models", methods=["GET"])
def list_models() -> Response:
    """List available LLM models and their effort levels.
    
    Returns:
        JSON with available models, their effort levels, and defaults.
    """
    if __package__ is None or __package__ == "":
        from config import (
            MODEL_EFFORT_LEVELS,
            AVAILABLE_MODELS,
            DEFAULT_MODEL,
            DEFAULT_EFFORT,
        )
    else:
        from .config import (
            MODEL_EFFORT_LEVELS,
            AVAILABLE_MODELS,
            DEFAULT_MODEL,
            DEFAULT_EFFORT,
        )
    
    return jsonify({
        "models": MODEL_EFFORT_LEVELS,
        "available_models": AVAILABLE_MODELS,
        "default_model": DEFAULT_MODEL,
        "default_effort": DEFAULT_EFFORT,
    })
