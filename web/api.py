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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import Blueprint, Response, jsonify, request

# Handle imports for both direct execution and package import
if __package__ is None or __package__ == "":
    # Running directly - add parent to path for absolute imports
    sys.path.insert(0, str(Path(__file__).parent))
    from candidate_selection import (
        select_candidates_dynamic,
        validate_categories_against_catalog,
    )
    from catalog import get_catalog
    from categories import (
        PRODUCT_CATEGORIES,
        SHARED_FIT_DIMENSIONS,
        get_clarification_fields,
        get_fit_dimensions_for_categories,
    )
    from job_identification import (
        JobIdentification,
        UnclearSpecification,
        identify_job,
        merge_inferred_with_user_selections,
        extract_categories_from_instructions,
    )
    from logging_utils import log_interaction
    from prompts import (
        build_grounding_context_dynamic,
        build_recommendation_context,
        make_clarification_prompt_dynamic,
        make_recommendation_prompt,
    )
else:
    # Running as package
    from .candidate_selection import (
        select_candidates_dynamic,
        validate_categories_against_catalog,
    )
    from .catalog import get_catalog
    from .categories import (
        PRODUCT_CATEGORIES,
        SHARED_FIT_DIMENSIONS,
        get_clarification_fields,
        get_fit_dimensions_for_categories,
    )
    from .job_identification import (
        JobIdentification,
        UnclearSpecification,
        identify_job,
        merge_inferred_with_user_selections,
        extract_categories_from_instructions,
    )
    from .logging_utils import log_interaction
    from .prompts import (
        build_grounding_context_dynamic,
        build_recommendation_context,
        make_clarification_prompt_dynamic,
        make_recommendation_prompt,
    )

__all__ = ["api"]

logger = logging.getLogger(__name__)

# Create blueprint for API
api = Blueprint("api", __name__, url_prefix="/api")


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


def _get_catalog_df():
    """Get the catalog DataFrame from the shared catalog module."""
    return get_catalog()


def _call_llm_recommendation(
    prompt: str,
    image_base64: Optional[str] = None,
    image_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call LLM for recommendation and parse response.
    
    Args:
        prompt: Recommendation prompt.
        image_base64: Optional base64 image.
        image_meta: Optional image metadata.
        
    Returns:
        Parsed recommendation dict.
    """
    from openai import OpenAI
    if __package__ is None or __package__ == "":
        from config import LLM_MODEL
    else:
        from .config import LLM_MODEL
    
    client = OpenAI()
    
    log_interaction(
        "llm_call_recommendation",
        {
            "model": LLM_MODEL,
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
        resp = client.responses.create(
            model=LLM_MODEL,
            input=input_payload,
        )
        
        for item in resp.output:
            if hasattr(item, "content") and item.content is not None:
                raw = item.content[0].text  # type: ignore[union-attr]
                
                log_interaction(
                    "llm_response_recommendation",
                    {"model": LLM_MODEL, "raw_response": raw},
                )
                
                try:
                    parsed = json.loads(raw)
                    return parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError as e:
                    log_interaction(
                        "llm_parse_error",
                        {"error": str(e), "raw": raw, "stage": "recommendation"},
                    )
                    return {}
                    
    except Exception as e:
        log_interaction("llm_error", {"error": str(e), "stage": "recommendation"})
        logger.exception("Error calling LLM for recommendation")
        
    return {}


def _call_llm_clarification(
    prompt: str,
    image_base64: Optional[str] = None,
) -> Dict[str, Any]:
    """Call LLM for clarification and parse response.
    
    Args:
        prompt: Clarification prompt.
        image_base64: Optional base64 image.
        
    Returns:
        Dict with inferred_values and options.
    """
    from openai import OpenAI
    if __package__ is None or __package__ == "":
        from config import LLM_MODEL
    else:
        from .config import LLM_MODEL
    
    client = OpenAI()
    
    log_interaction(
        "llm_call_clarification",
        {"model": LLM_MODEL, "prompt": prompt, "image_attached": bool(image_base64)},
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
        resp = client.responses.create(
            model=LLM_MODEL,
            input=input_payload,
        )
        
        for item in resp.output:
            if hasattr(item, "content") and item.content is not None:
                raw = item.content[0].text  # type: ignore[union-attr]
                
                log_interaction(
                    "llm_response_clarification",
                    {"model": LLM_MODEL, "raw_response": raw},
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
            "identified_job": {...}  // Cached job identification
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
    data = request.get_json(force=True)
    
    # Validate problem_text is a string
    problem_text = data.get("problem_text", "")
    if not isinstance(problem_text, str):
        return jsonify({"error": "problem_text must be a string"}), 400
    
    problem_text = problem_text.strip()
    
    clarification_answers = data.get("clarification_answers", [])
    cached_job = data.get("identified_job")
    # Legacy support
    selected_values = data.get("selected_values", {})
    
    # Process image
    raw_image_b64 = data.get("image_base64")
    processed_image, image_mime, image_error = _process_image_for_openai(raw_image_b64)
    
    if image_error:
        return jsonify({"error": image_error}), 400
    
    image_meta = {
        "uploaded": bool(raw_image_b64),
        "processed": bool(processed_image),
        "mime_type": image_mime,
    }
    
    if not problem_text:
        return jsonify({"error": "problem_text is required"}), 400
    
    # Log user input
    if not cached_job:
        log_interaction(
            "user_input",
            {
                "problem_text": problem_text,
                "image_meta": image_meta,
                "has_clarifications": bool(clarification_answers),
                "clarification_answers": clarification_answers if clarification_answers else [],
            },
        )
    
    # Step 1: Job Identification (use cached if available)
    if cached_job:
        job = JobIdentification.from_dict(cached_job)
        log_interaction("job_identification_cached", job.to_dict())
    else:
        job = identify_job(problem_text, processed_image, image_meta)
    
    # Validate categories against available catalog
    df = _get_catalog_df()
    referenced_categories = job.referenced_categories or job.categories
    valid_categories = validate_categories_against_catalog(referenced_categories, df)
    
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
        log_interaction(
            "clarification_required",
            {
                "questions": questions,
                "instructions_preview": job.instructions,
                "inferred_values": known_values,
            },
        )
        
        return jsonify({
            "need_clarification": True,
            "job": job.to_dict(),
            "clarification_questions": questions,
            "instructions_preview": job.instructions,
            "inferred_values": known_values,
        }), 200
    
    # Step 3: Select products for all referenced categories
    candidates = select_candidates_dynamic(df, valid_categories, known_values)
    
    # Log what we found
    log_interaction("candidate_selection", {
        "categories": valid_categories,
        "known_values": known_values,
        "candidates_count": {cat: len(prods) for cat, prods in candidates.items()},
    })
    
    # Step 4: Build recommendation context and prompt
    context = build_recommendation_context(
        problem_text=problem_text,
        instructions=job.instructions,
        clarifications=clarification_answers,
        category_products=candidates,
        image_base64=processed_image,
    )
    
    prompt = make_recommendation_prompt(context, bool(processed_image))
    
    # Step 5: Call LLM for final recommendation
    llm_payload = _call_llm_recommendation(prompt, processed_image, image_meta)
    
    # Step 6: Parse and format response
    final_instructions = llm_payload.get("final_instructions", job.instructions)
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
    
    # Build legacy format for backwards compatibility
    legacy_sections = {
        "why_it_fits": [diagnosis] if diagnosis else [],
        "suggested_workflow": final_instructions,
        "checklist": [],
    }
    
    # Build legacy products_by_category
    products_by_category = []
    for cat in valid_categories:
        cat_candidates = candidates.get(cat, [])
        if not cat_candidates:
            continue
        
        config = PRODUCT_CATEGORIES.get(cat, {})
        products_by_category.append({
            "category": config.get("display_name", cat.replace("_", " ").title()),
            "category_key": cat,
            "best": cat_candidates[0] if cat_candidates else None,
            "alternatives": cat_candidates[1:] if len(cat_candidates) > 1 else [],
        })
    
    # Log final recommendation result
    log_interaction(
        "recommendation_result",
        {
            "diagnosis": diagnosis,
            "final_instructions": final_instructions,
            "primary_products_count": len(primary_products),
            "tools_count": len(tools),
            "optional_extras_count": len(optional_extras),
            "fit_values": known_values,
        },
    )
    
    return jsonify({
        # New format
        "diagnosis": diagnosis,
        "final_instructions": final_instructions,
        "primary_products": primary_products,
        "tools": tools,
        "optional_extras": optional_extras,
        "job": job.to_dict(),
        "fit_values": known_values,
        # Legacy format for backwards compatibility
        "sections": legacy_sections,
        "products_by_category": products_by_category,
    })


@api.route("/categories", methods=["GET"])
def list_categories() -> Response:
    """List available product categories.
    
    Returns:
        JSON list of category configurations.
    """
    df = _get_catalog_df()
    available = set(df["category"].dropna().unique())
    
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
