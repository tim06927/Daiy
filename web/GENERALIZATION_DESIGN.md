# Web App Generalization Design

## Overview

Transform the app from hardcoded drivetrain-only (cassettes + chains + tools) to a 
category-agnostic system that can handle any combination of scraped product categories.

## Current Flow (Hardcoded)

```
User Input → Regex Extraction → LLM Clarification → Candidate Selection → Recommendation
              (speed, use_case)   (speed_options,     (cassettes, chains,   (hardcoded 3 
                                   use_case_options)   drivetrain_tools)     categories)
```

## Proposed Generalized Flow

```
User Input → Job Identification → Dynamic Clarification → Candidate Selection → Recommendation
              (categories +        (category-specific      (per-category        (N categories)
               fit dimensions)      questions)              filtering)
```

## Key Components

### 1. Product Category Registry (`web/categories.py`)

Define available categories with their fit dimensions:

```python
PRODUCT_CATEGORIES = {
    "cassettes": {
        "display_name": "Cassettes",
        "fit_dimensions": ["gearing", "freehub_compatibility"],
        "clarification_fields": {
            "gearing": {
                "prompt": "What speed drivetrain do you have?",
                "hint": "Count the cogs on your rear cassette",
                "options_template": ["8-speed", "9-speed", "10-speed", "11-speed", "12-speed"]
            }
        }
    },
    "chains": {
        "display_name": "Chains",
        "fit_dimensions": ["gearing"],
        "clarification_fields": {
            "gearing": {
                "prompt": "What speed drivetrain do you have?",
                "hint": "Count the cogs on your rear cassette",
                "options_template": ["8-speed", "9-speed", "10-speed", "11-speed", "12-speed"]
            }
        }
    },
    "mtb_gloves": {
        "display_name": "MTB Gloves",
        "fit_dimensions": ["size", "season"],
        "clarification_fields": {
            "size": {
                "prompt": "What size gloves do you need?",
                "hint": "Measure hand circumference",
                "options_template": ["XS", "S", "M", "L", "XL", "XXL"]
            },
            "season": {
                "prompt": "What season will you use these?",
                "hint": "Summer gloves are lighter, winter have insulation",
                "options_template": ["Summer", "All-Season", "Winter"]
            }
        }
    },
    "drivetrain_tools": {
        "display_name": "Drivetrain Tools",
        "fit_dimensions": [],  # Tools are more general
        "clarification_fields": {}
    }
}
```

### 2. Job Identification Step

New LLM call after user input that returns:

```json
{
  "identified_categories": ["cassettes", "chains"],
  "inferred_values": {
    "gearing": 11,
    "use_case": "road"
  },
  "missing_clarifications": ["use_case"],
  "confidence": 0.85,
  "reasoning": "User mentions worn chain and cassette, 11-speed visible in image"
}
```

### 3. Dynamic Clarification

Instead of hardcoded `speed_options` and `use_case_options`, generate clarification 
questions based on:
- Identified categories
- Missing fit dimensions for those categories
- What the LLM couldn't infer

### 4. Dynamic Candidate Selection

Replace `select_candidates()` with a category-agnostic version:

```python
def select_candidates_for_categories(
    df: pd.DataFrame,
    categories: List[str],
    fit_values: Dict[str, Any]
) -> Dict[str, List[Dict]]:
    """
    Dynamically filter products for each requested category
    based on the category's fit dimensions.
    """
    results = {}
    for cat in categories:
        cat_config = PRODUCT_CATEGORIES[cat]
        filtered = df[df["category"] == cat]
        
        for dim in cat_config["fit_dimensions"]:
            if dim in fit_values and fit_values[dim]:
                # Apply filter based on dimension type
                filtered = apply_fit_filter(filtered, dim, fit_values[dim])
        
        results[cat] = filtered.head(MAX_PRODUCTS_PER_CATEGORY).to_dict('records')
    return results
```

### 5. Dynamic Prompt Construction

Replace `make_prompt()` with version that:
- Lists only the identified categories
- Instructs LLM to recommend one per category
- Doesn't assume cassettes/chains/tools structure

## Migration Strategy

### Phase 1: Create Infrastructure (non-breaking)
1. Create `web/categories.py` with category registry
2. Add `identify_job()` function (new LLM call)
3. Keep existing flow working

### Phase 2: Refactor Internals
4. Generalize `select_candidates()` 
5. Generalize `make_prompt()`
6. Update response parsing

### Phase 3: Update API
7. Change `/api/recommend` to use new flow
8. Update frontend to handle dynamic categories

## Benefits

1. **Extensibility**: Add new categories by updating config, not code
2. **Flexibility**: Users can get recommendations for any combination
3. **Smarter**: Job identification can understand complex requests
4. **Cleaner**: Remove 20+ hardcoded drivetrain references

## Example User Flows

### Current (Hardcoded)
> "My chain is worn out on my 11-speed road bike"
→ Always returns: cassette + chain + tool suggestions

### Generalized
> "My chain is worn out"
→ Job ID detects: categories=[chains], needs clarification for gearing
→ Clarifies: "What speed drivetrain?"
→ Returns: just chain suggestions

> "Need new winter gloves for MTB"
→ Job ID detects: categories=[mtb_gloves], needs clarification for size
→ Clarifies: "What size?"
→ Returns: winter MTB glove suggestions

> "Want to upgrade my whole drivetrain and need tools"
→ Job ID detects: categories=[cassettes, chains, drivetrain_tools]
→ Clarifies: "What speed?"
→ Returns: cassette + chain + tool suggestions (like today, but not assumed)
