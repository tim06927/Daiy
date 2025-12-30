"""Job identification for dynamic product recommendations.

This module handles the first step of the generalized flow: analyzing user input
to determine which product categories are relevant, generate step-by-step 
instructions, and identify technical specifications that need clarification.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Handle imports for both direct execution and package import
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent))
    from categories import (
        PRODUCT_CATEGORIES,
        SHARED_FIT_DIMENSIONS,
        get_categories_for_prompt,
        get_all_category_names,
    )
    from config import LLM_MODEL
    from logging_utils import log_interaction
else:
    from .categories import (
        PRODUCT_CATEGORIES,
        SHARED_FIT_DIMENSIONS,
        get_categories_for_prompt,
        get_all_category_names,
    )
    from .config import LLM_MODEL
    from .logging_utils import log_interaction

__all__ = [
    "identify_job",
    "JobIdentification",
    "UnclearSpecification",
    "extract_categories_from_instructions",
]

logger = logging.getLogger(__name__)


def _get_openai_client():
    """Get OpenAI client (lazy initialization)."""
    from openai import OpenAI
    return OpenAI()


class UnclearSpecification:
    """A technical specification that needs user clarification.
    
    Represents a single unclear technical dimension with confidence score,
    question, hint for the user, and possible answer options.
    """
    
    def __init__(
        self,
        spec_name: str,
        confidence: float,
        question: str,
        hint: str,
        options: List[str],
    ):
        """Initialize unclear specification.
        
        Args:
            spec_name: Technical specification identifier (e.g., "gearing", "brake_rotor_size").
            confidence: LLM's confidence score (0-1) for this specification.
            question: Clarifying question to ask the user.
            hint: Simple instruction for how user can find the answer.
            options: 2-5 realistic answer options.
        """
        self.spec_name = spec_name
        self.confidence = confidence
        self.question = question
        self.hint = hint
        self.options = options
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "spec_name": self.spec_name,
            "confidence": self.confidence,
            "question": self.question,
            "hint": self.hint,
            "options": self.options,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnclearSpecification":
        """Create from dictionary."""
        return cls(
            spec_name=data.get("spec_name", ""),
            confidence=data.get("confidence", 0.0),
            question=data.get("question", ""),
            hint=data.get("hint", ""),
            options=data.get("options", []),
        )


def extract_categories_from_instructions(instructions: List[str]) -> List[str]:
    """Extract category keys mentioned in step-by-step instructions.
    
    Parses instructions for [category_key] references and returns unique categories.
    
    Args:
        instructions: List of instruction steps with [category] references.
        
    Returns:
        List of unique category keys found in instructions.
    """
    categories = []
    pattern = r'\[([a-z_]+)\]'
    
    for step in instructions:
        matches = re.findall(pattern, step)
        for match in matches:
            if match not in categories:
                categories.append(match)
    
    return categories


class JobIdentification:
    """Result of job identification step.
    
    Contains:
    - instructions: Step-by-step instructions with category references in [category_key] format
    - unclear_specifications: Technical specs needing clarification (confidence < 0.8)
    - Referenced categories extracted from instructions
    
    Legacy fields maintained for backwards compatibility:
    - primary_categories, optional_categories, required_tools
    """
    
    def __init__(
        self,
        instructions: List[str],
        unclear_specifications: List[UnclearSpecification],
        confidence: float,
        reasoning: str,
        # Legacy fields for backwards compatibility
        primary_categories: Optional[List[str]] = None,
        optional_categories: Optional[List[str]] = None,
        required_tools: Optional[List[str]] = None,
        inferred_values: Optional[Dict[str, Any]] = None,
        missing_dimensions: Optional[List[str]] = None,
        optional_reasons: Optional[Dict[str, str]] = None,
        tool_reasons: Optional[Dict[str, str]] = None,
    ):
        """Initialize job identification result.
        
        Args:
            instructions: Step-by-step instructions with [category_key] references.
            unclear_specifications: List of specs needing user clarification.
            confidence: Confidence score (0-1) for the overall identification.
            reasoning: Brief explanation of the identified job.
            primary_categories: (Legacy) Categories the user explicitly asked for.
            optional_categories: (Legacy) Complementary categories for this job.
            required_tools: (Legacy) Tool categories needed.
            inferred_values: (Legacy) Dict of fit dimension values inferred from input.
            missing_dimensions: (Legacy) List of fit dimensions that need clarification.
            optional_reasons: (Legacy) Dict mapping optional category to reason.
            tool_reasons: (Legacy) Dict mapping tool category to reason.
        """
        self.instructions = instructions
        self.unclear_specifications = unclear_specifications
        self.confidence = confidence
        self.reasoning = reasoning
        
        # Extract categories from instructions
        self._referenced_categories = extract_categories_from_instructions(instructions)
        
        # Legacy fields - populate from instructions if not provided
        self.primary_categories = primary_categories or []
        self.optional_categories = optional_categories or []
        self.required_tools = required_tools or []
        self.inferred_values = inferred_values or {}
        self.missing_dimensions = missing_dimensions or [
            spec.spec_name for spec in unclear_specifications
        ]
        self.optional_reasons = optional_reasons or {}
        self.tool_reasons = tool_reasons or {}
    
    @property
    def referenced_categories(self) -> List[str]:
        """Categories referenced in the step-by-step instructions."""
        return self._referenced_categories
    
    @property
    def categories(self) -> List[str]:
        """All categories (for backwards compatibility)."""
        # Prefer referenced categories from instructions, fall back to legacy
        if self._referenced_categories:
            return self._referenced_categories
        return self.primary_categories + self.optional_categories + self.required_tools
    
    @categories.setter
    def categories(self, value: List[str]) -> None:
        """Set categories (for backwards compatibility during validation)."""
        # When setting categories, update referenced categories
        self._referenced_categories = value
        self.primary_categories = value
    
    def get_clarification_questions(self) -> List[Dict[str, Any]]:
        """Get clarification questions for unclear specifications.
        
        Returns:
            List of question dicts with question, hint, and options.
        """
        return [spec.to_dict() for spec in self.unclear_specifications]
    
    def has_unclear_specifications(self) -> bool:
        """Check if there are any specifications needing clarification."""
        return len(self.unclear_specifications) > 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "instructions": self.instructions,
            "unclear_specifications": [spec.to_dict() for spec in self.unclear_specifications],
            "referenced_categories": self._referenced_categories,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            # Legacy fields for backwards compatibility
            "primary_categories": self.primary_categories,
            "optional_categories": self.optional_categories,
            "required_tools": self.required_tools,
            "optional_reasons": self.optional_reasons,
            "tool_reasons": self.tool_reasons,
            "inferred_values": self.inferred_values,
            "missing_dimensions": self.missing_dimensions,
            "categories": self.categories,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobIdentification":
        """Create from dictionary."""
        # Handle new format with instructions
        if "instructions" in data:
            unclear_specs = [
                UnclearSpecification.from_dict(spec)
                for spec in data.get("unclear_specifications", [])
            ]
            return cls(
                instructions=data.get("instructions", []),
                unclear_specifications=unclear_specs,
                confidence=data.get("confidence", 0.0),
                reasoning=data.get("reasoning", ""),
                primary_categories=data.get("primary_categories", []),
                optional_categories=data.get("optional_categories", []),
                required_tools=data.get("required_tools", []),
                inferred_values=data.get("inferred_values", {}),
                missing_dimensions=data.get("missing_dimensions", []),
                optional_reasons=data.get("optional_reasons", {}),
                tool_reasons=data.get("tool_reasons", {}),
            )
        # Handle legacy format
        elif "primary_categories" in data:
            return cls(
                instructions=[],
                unclear_specifications=[],
                confidence=data.get("confidence", 0.0),
                reasoning=data.get("reasoning", ""),
                primary_categories=data.get("primary_categories", []),
                optional_categories=data.get("optional_categories", []),
                required_tools=data.get("required_tools", []),
                inferred_values=data.get("inferred_values", {}),
                missing_dimensions=data.get("missing_dimensions", []),
                optional_reasons=data.get("optional_reasons", {}),
                tool_reasons=data.get("tool_reasons", {}),
            )
        else:
            # Very old format - treat categories as primary
            return cls(
                instructions=[],
                unclear_specifications=[],
                confidence=data.get("confidence", 0.0),
                reasoning=data.get("reasoning", ""),
                primary_categories=data.get("categories", []),
            )


def _build_job_identification_prompt(
    problem_text: str,
    image_attached: bool = False,
) -> str:
    """Build the prompt for job identification.
    
    Generates a prompt that asks the LLM to provide:
    1. Step-by-step instructions with category references in [category_key] format
    2. Unclear specifications with confidence < 0.8 needing user clarification
    
    Args:
        problem_text: User's description of their needs.
        image_attached: Whether a user image is attached.
        
    Returns:
        Formatted prompt string.
    """
    category_descriptions = get_categories_for_prompt()
    
    # Get list of category keys for the prompt
    category_keys = get_all_category_names()
    category_keys_str = ", ".join(category_keys)
    
    # Image analysis instructions
    image_instruction = ""
    if image_attached:
        image_instruction = """

IMPORTANT - IMAGE ANALYSIS:
The user has uploaded a PHOTO. Carefully analyze the image to:
- Identify components, parts, or issues visible in the image
- Extract technical specifications from visual cues (count parts, read markings, measure proportions)
- Look for brand logos, model numbers, or sizing information
- Use this visual information to increase confidence in technical specifications
"""
    
    return f"""You are an expert bicycle mechanic assistant. Analyze the user's request and provide detailed step-by-step instructions to solve their problem.

{category_descriptions}

VALID CATEGORY KEYS (use ONLY these exact keys in square brackets):
{category_keys_str}

USER REQUEST:
\"\"\"{problem_text}\"\"\"
{image_instruction}
YOUR TASK:
1. Create detailed step-by-step instructions explaining how to solve the user's problem
2. In each step, reference ALL parts, accessories, and tools needed using [category_key] format
3. Identify ALL technical specifications and assess your confidence for each
4. For specs with confidence < 0.6, provide clarification questions

RESPONSE FORMAT (return pure JSON only, no prose):
{{
  "instructions": [
    "Step 1: Description of first step. You will need a [category_key] for this.",
    "Step 2: Description including specific technical details. Use a [category_key] tool.",
    "Step 3: Continue with [another_category_key] as needed."
  ],
  "unclear_specifications": [
    {{
      "spec_name": "technical_specification_identifier",
      "confidence": 0.5,
      "question": "What is the specific value of X?",
      "hint": "Simple instruction for how the user can find this answer (e.g., 'count the number of X on Y' or 'measure the diameter of Z').",
      "options": ["Option A", "Option B", "Option C"]
    }}
  ],
  "confidence": 0.85,
  "reasoning": "Brief explanation of what job was identified"
}}

RULES FOR INSTRUCTIONS:
- Be SPECIFIC with technical details (sizes, counts, specifications)
- Reference categories using EXACT keys in [square_brackets] format
- Only use category keys from the VALID CATEGORY KEYS list above
- Include ALL necessary parts, tools, and accessories for each step
- Order steps logically for someone performing the repair/maintenance
- Each step should be actionable and clear

RULES FOR UNCLEAR SPECIFICATIONS:
- Self-assess confidence (0-1) for EVERY technical specification mentioned
- Include ANY spec with confidence < 0.8 in unclear_specifications, but only if it is clearly distinct
- Do NOT include multiple variations of the same spec (merge overlapping specs into one question)
- Do NOT ask implied specs twice (e.g., drivetrain_speed covers cassette/chain speed; tire_width covers rim width if already specified)
- Questions and hints MUST be understandable by a beginner hobby bike repairer with NO special tools
- The "hint" should use simple, visual instructions (e.g., "Count the cogs on the back wheel" NOT "Count cassette sprockets")
- Avoid technical jargon in questions - use everyday language (e.g., "gears" not "drivetrain_speed")
- Provide 2-5 realistic options that cover common scenarios
- spec_name should be a clear identifier (e.g., "drivetrain_speed", "brake_rotor_diameter", "tire_width")

IMPORTANT:
- Do NOT assume technical specifications - if unsure, add to unclear_specifications
- Do NOT use placeholder values in instructions - be specific or mark as unclear
- Categories MUST be from the valid list - do not invent category names
"""


def _ensure_required_dimensions(job: "JobIdentification") -> None:
    """Ensure all required fit dimensions for identified categories are tracked.
    
    If a required dimension is not in inferred_values AND not in missing_dimensions,
    add it to missing_dimensions. This ensures the clarification flow will ask
    for necessary information.
    
    Args:
        job: JobIdentification result to modify in place.
    """
    # Collect all required fit dimensions from identified categories
    all_categories = job.primary_categories + job.optional_categories
    required_dims = set()
    
    for cat in all_categories:
        cat_config = PRODUCT_CATEGORIES.get(cat, {})
        for dim in cat_config.get("required_fit", []):
            required_dims.add(dim)
    
    # Check which required dimensions are missing
    inferred = job.inferred_values or {}
    missing = set(job.missing_dimensions or [])
    
    for dim in required_dims:
        # If not inferred (or inferred as None) and not already marked as missing
        if inferred.get(dim) is None and dim not in missing:
            missing.add(dim)
            logger.debug(f"Added required dimension '{dim}' to missing_dimensions")
    
    # Update job's missing_dimensions
    job.missing_dimensions = list(missing)


def identify_job(
    problem_text: str,
    image_base64: Optional[str] = None,
    image_meta: Optional[Dict[str, Any]] = None,
) -> JobIdentification:
    """Identify job from user input using LLM.
    
    This is the first step in the generalized recommendation flow. It analyzes
    the user's request to produce:
    - Step-by-step instructions with category references
    - Unclear specifications needing clarification
    
    Args:
        problem_text: User's description of their needs.
        image_base64: Optional base64-encoded image.
        image_meta: Optional metadata about the image.
        
    Returns:
        JobIdentification result with instructions and unclear specs.
    """
    image_attached = bool(image_base64)
    prompt = _build_job_identification_prompt(problem_text, image_attached)
    
    # Log the call
    log_interaction(
        "llm_call_job_identification",
        {
            "model": LLM_MODEL,
            "prompt": prompt,
            "user_text": problem_text,
            "image_attached": image_attached,
            "image_meta": image_meta or {},
        },
    )
    
    # Build input payload
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
        client = _get_openai_client()
        resp = client.responses.create(
            model=LLM_MODEL,
            input=input_payload,
        )
        
        for item in resp.output:
            if hasattr(item, "content") and item.content is not None:
                raw = item.content[0].text  # type: ignore[union-attr]
                
                log_interaction(
                    "llm_response_job_identification",
                    {
                        "model": LLM_MODEL,
                        "raw_response": raw,
                    },
                )
                
                try:
                    parsed = json.loads(raw)
                    valid_categories = get_all_category_names()
                    
                    # Parse new format with instructions
                    instructions = parsed.get("instructions", [])
                    
                    # Parse unclear specifications
                    unclear_specs_raw = parsed.get("unclear_specifications", [])
                    unclear_specs = []
                    for spec_data in unclear_specs_raw:
                        unclear_specs.append(UnclearSpecification(
                            spec_name=spec_data.get("spec_name", "unknown"),
                            confidence=float(spec_data.get("confidence", 0.0)),
                            question=spec_data.get("question", ""),
                            hint=spec_data.get("hint", ""),
                            options=spec_data.get("options", []),
                        ))
                    
                    # Extract categories from instructions
                    referenced_categories = extract_categories_from_instructions(instructions)
                    
                    # Validate categories - filter out invalid ones
                    valid_referenced = [c for c in referenced_categories if c in valid_categories]
                    
                    # If no valid categories found, try legacy format or fallback
                    if not valid_referenced:
                        logger.warning("No valid categories in instructions, checking legacy format")
                        
                        # Try legacy format
                        primary_categories = [
                            c for c in parsed.get("primary_categories", [])
                            if c in valid_categories
                        ]
                        if primary_categories:
                            # Build instructions from legacy data for backwards compat
                            instructions = [
                                f"Use products from categories: {', '.join('[' + c + ']' for c in primary_categories)}"
                            ]
                            valid_referenced = primary_categories
                        else:
                            # Fallback based on keywords
                            text_lower = problem_text.lower()
                            if any(w in text_lower for w in ["chain", "cassette", "drivetrain"]):
                                valid_referenced = ["drivetrain_chains", "drivetrain_cassettes", "drivetrain_tools"]
                            elif "light" in text_lower:
                                valid_referenced = ["lighting_bicycle_lights_battery"]
                            elif "pedal" in text_lower:
                                valid_referenced = ["drivetrain_pedals"]
                            else:
                                valid_referenced = ["drivetrain_chains"]
                            
                            instructions = [
                                f"Identified products from: {', '.join('[' + c + ']' for c in valid_referenced)}"
                            ]
                    
                    result = JobIdentification(
                        instructions=instructions,
                        unclear_specifications=unclear_specs,
                        confidence=float(parsed.get("confidence", 0.5)),
                        reasoning=parsed.get("reasoning", ""),
                        # Populate legacy fields for backwards compatibility
                        primary_categories=valid_referenced,
                        inferred_values=parsed.get("inferred_values", {}),
                    )
                    
                    # Ensure required dimensions are tracked
                    _ensure_required_dimensions(result)
                    
                    log_interaction("job_identification_result", result.to_dict())
                    return result
                    
                except json.JSONDecodeError as e:
                    log_interaction(
                        "llm_parse_error_job_identification",
                        {"error": str(e), "raw": raw},
                    )
                    
    except Exception as e:
        log_interaction(
            "llm_error_job_identification",
            {"error": str(e)},
        )
        logger.exception("Error during job identification")
    
    # Fallback: return basic instructions with unknown values
    logger.warning("Job identification failed, using fallback")
    return JobIdentification(
        instructions=[
            "Unable to fully identify the job. Please provide more details.",
            "You may need products from [drivetrain_chains] or [drivetrain_cassettes]."
        ],
        unclear_specifications=[
            UnclearSpecification(
                spec_name="job_type",
                confidence=0.0,
                question="What type of repair or maintenance do you need?",
                hint="Describe the main issue or what you want to accomplish.",
                options=["Chain replacement", "Drivetrain service", "General maintenance", "Other"],
            )
        ],
        confidence=0.0,
        reasoning="Fallback: could not identify specific job from input",
        primary_categories=["drivetrain_chains"],
    )


def merge_inferred_with_user_selections(
    job: JobIdentification,
    user_selections: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge LLM-inferred values with explicit user selections.
    
    User selections take precedence over inferred values.
    
    Args:
        job: Job identification result.
        user_selections: Dict of user-provided values.
        
    Returns:
        Merged dict of all known fit dimension values.
    """
    result = dict(job.inferred_values)
    for key, value in user_selections.items():
        if value is not None:
            result[key] = value
    return result
