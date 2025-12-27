"""Generalized API endpoints for product recommendations.

This module provides the new category-agnostic recommendation flow:
1. Job identification - determine categories and fit dimensions needed
2. Clarification - gather missing fit information
3. Recommendation - generate grounded product suggestions

The /api/v2/recommend endpoint uses this flow.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import Blueprint, Response, jsonify, request

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
    identify_job,
    merge_inferred_with_user_selections,
)
from .logging_utils import log_interaction
from .prompts import (
    build_grounding_context_dynamic,
    make_clarification_prompt_dynamic,
    make_recommendation_prompt,
)

__all__ = ["api_v2"]

logger = logging.getLogger(__name__)

# Create blueprint for v2 API
api_v2 = Blueprint("api_v2", __name__, url_prefix="/api/v2")


def _process_image_for_openai(
    image_base64: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Process and validate image for OpenAI.
    
    Returns (processed_base64, mime_type, error_message).
    """
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
    from .config import LLM_MODEL
    
    client = OpenAI()
    
    log_interaction(
        "llm_call_recommendation_v2",
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
                    "llm_response_recommendation_v2",
                    {"model": LLM_MODEL, "raw_response": raw},
                )
                
                try:
                    parsed = json.loads(raw)
                    return parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError as e:
                    log_interaction(
                        "llm_parse_error_recommendation_v2",
                        {"error": str(e), "raw": raw},
                    )
                    return {}
                    
    except Exception as e:
        log_interaction("llm_error_recommendation_v2", {"error": str(e)})
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
    from .config import LLM_MODEL
    
    client = OpenAI()
    
    log_interaction(
        "llm_call_clarification_v2",
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
                    "llm_response_clarification_v2",
                    {"model": LLM_MODEL, "raw_response": raw},
                )
                
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    log_interaction(
                        "llm_parse_error_clarification_v2",
                        {"error": str(e), "raw": raw},
                    )
                    
    except Exception as e:
        log_interaction("llm_error_clarification_v2", {"error": str(e)})
        logger.exception("Error calling LLM for clarification")
    
    return {"inferred_values": {}, "options": {}}


@api_v2.route("/recommend", methods=["POST"])
def recommend() -> Union[Tuple[Response, int], Response]:
    """Generalized product recommendation endpoint.
    
    Request JSON:
        {
            "problem_text": "User's description of needs",
            "image_base64": "optional base64 image",
            "selected_values": {"gearing": 11, ...},  // Optional user selections
            "identified_job": {...}  // Optional cached job identification
        }
    
    Response JSON (need_clarification=true):
        {
            "need_clarification": true,
            "job": {...},  // Job identification result
            "missing_dimensions": ["gearing"],
            "clarification_fields": {...},  // Field configs for UI
            "inferred_values": {...}  // Values already inferred
        }
    
    Response JSON (recommendation):
        {
            "diagnosis": "...",
            "sections": {...},
            "products_by_category": [...],
            "job": {...},
            "fit_values": {...}
        }
    """
    data = request.get_json(force=True)
    problem_text = data.get("problem_text", "").strip()
    selected_values = data.get("selected_values", {})
    cached_job = data.get("identified_job")
    
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
    
    # Log user input if this is a fresh request
    if not selected_values and not cached_job:
        log_interaction(
            "user_input_v2",
            {"problem_text": problem_text, "image_meta": image_meta},
        )
    
    # Step 1: Job Identification (use cached if available)
    if cached_job:
        job = JobIdentification.from_dict(cached_job)
        log_interaction("job_identification_cached", job.to_dict())
    else:
        job = identify_job(problem_text, processed_image, image_meta)
    
    # Validate categories against available catalog
    df = _get_catalog_df()
    valid_categories = validate_categories_against_catalog(job.categories, df)
    
    if not valid_categories:
        return jsonify({
            "error": "No matching product categories found for your request.",
            "identified_categories": job.categories,
            "hint": "Try being more specific about what products you need.",
        }), 404
    
    job.categories = valid_categories
    
    # Step 2: Merge inferred values with user selections
    known_values = merge_inferred_with_user_selections(job, selected_values)
    
    # Step 3: Check if clarification is needed
    clarification_fields = get_clarification_fields(job.categories, known_values)
    
    # Only require clarification for required dimensions
    required_missing = []
    for dim, config in clarification_fields.items():
        if config.get("is_required", False):
            required_missing.append(dim)
    
    if required_missing:
        # Need clarification - try LLM inference first
        prompt = make_clarification_prompt_dynamic(
            problem_text,
            job.categories,
            required_missing,
            bool(processed_image),
        )
        
        llm_result = _call_llm_clarification(prompt, processed_image)
        
        # Update known values with LLM inferences
        for dim, value in llm_result.get("inferred_values", {}).items():
            if value is not None and dim not in known_values:
                known_values[dim] = value
                if dim in required_missing:
                    required_missing.remove(dim)
        
        # If still missing required values, ask user
        if required_missing:
            # Build options for missing dimensions
            options = llm_result.get("options", {})
            
            # Ensure we have options for all missing dimensions
            for dim in required_missing:
                options_key = f"{dim}_options"
                if options_key not in options or not options[options_key]:
                    dim_config = SHARED_FIT_DIMENSIONS.get(dim, {})
                    options[options_key] = dim_config.get("options", [])
            
            # Build hints
            hints = {}
            for dim in required_missing:
                dim_config = SHARED_FIT_DIMENSIONS.get(dim, {})
                hints[dim] = dim_config.get("hint", "")
            
            return jsonify({
                "need_clarification": True,
                "job": job.to_dict(),
                "missing_dimensions": required_missing,
                "options": options,
                "hints": hints,
                "inferred_values": known_values,
            }), 200
    
    # Step 4: Select candidates
    candidates = select_candidates_dynamic(df, job.categories, known_values)
    
    # Check if we have any candidates
    total_candidates = sum(len(prods) for prods in candidates.values())
    if total_candidates == 0:
        return jsonify({
            "error": "No matching products found for your requirements.",
            "job": job.to_dict(),
            "fit_values": known_values,
            "hint": "Try adjusting your requirements or selecting different options.",
        }), 404
    
    # Step 5: Build context and prompt
    context = build_grounding_context_dynamic(
        problem_text,
        job.categories,
        known_values,
        candidates,
        processed_image,
    )
    
    prompt = make_recommendation_prompt(context, bool(processed_image))
    
    # Step 6: Call LLM for recommendation
    llm_payload = _call_llm_recommendation(prompt, processed_image, image_meta)
    
    # Step 7: Parse and format response
    sections = llm_payload.get("sections", {})
    ranking = llm_payload.get("product_ranking", {})
    diagnosis = llm_payload.get("diagnosis", "")
    
    # Build products_by_category response
    products_by_category = []
    
    for cat in job.categories:
        cat_candidates = candidates.get(cat, [])
        if not cat_candidates:
            continue
        
        config = PRODUCT_CATEGORIES.get(cat, {})
        display_name = config.get("display_name", cat.replace("_", " ").title())
        
        rank_info = ranking.get(cat, {})
        best_idx = rank_info.get("best_index", 0)
        
        # Validate index
        if not isinstance(best_idx, int) or best_idx < 0 or best_idx >= len(cat_candidates):
            best_idx = 0
        
        # Get alternatives
        alt_indices = rank_info.get("alternatives", [])
        if not isinstance(alt_indices, list):
            alt_indices = []
        alt_indices = [
            i for i in alt_indices
            if isinstance(i, int) and 0 <= i < len(cat_candidates) and i != best_idx
        ]
        
        # Fill remaining
        remaining = [
            i for i in range(len(cat_candidates))
            if i not in alt_indices and i != best_idx
        ]
        alt_indices = alt_indices + remaining
        
        # Get why_fits
        why_fits = rank_info.get("why_fits", {})
        if not isinstance(why_fits, dict):
            why_fits = {}
        
        def _add_why_fits(prod: Dict[str, Any], idx: int) -> Dict[str, Any]:
            prod_copy = dict(prod)
            prod_copy["type"] = cat
            why_text = why_fits.get(str(idx)) or why_fits.get(idx) or ""
            prod_copy["why_it_fits"] = why_text if isinstance(why_text, str) else ""
            return prod_copy
        
        best_prod = _add_why_fits(cat_candidates[best_idx], best_idx)
        alt_prods = [_add_why_fits(cat_candidates[i], i) for i in alt_indices]
        
        products_by_category.append({
            "category": display_name,
            "category_key": cat,
            "best": best_prod,
            "alternatives": alt_prods,
        })
    
    if not products_by_category:
        return jsonify({
            "error": "Could not generate recommendations.",
            "job": job.to_dict(),
            "fit_values": known_values,
        }), 500
    
    return jsonify({
        "diagnosis": diagnosis,
        "sections": sections,
        "products_by_category": products_by_category,
        "job": job.to_dict(),
        "fit_values": known_values,
    })


@api_v2.route("/categories", methods=["GET"])
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
