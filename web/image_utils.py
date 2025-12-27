"""Image processing utilities for the Daiy web app.

Handles image validation, conversion, and preparation for OpenAI API.
"""

import base64
import sys
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

# Handle imports for both direct execution and package import
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent))
    from logging_utils import log_interaction
else:
    from .logging_utils import log_interaction

__all__ = ["process_image_for_openai", "MAX_IMAGE_SIZE"]

# Maximum image size in bytes (5MB)
MAX_IMAGE_SIZE = 5 * 1024 * 1024

# Register HEIF/HEIC support for Pillow (for iPad images)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # pillow-heif not installed, HEIC support disabled


def process_image_for_openai(
    image_base64: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Process and convert image to a format OpenAI accepts.

    Accepts any image format (including HEIC from iPad) and converts to PNG.
    Rejects images larger than 5MB.

    Args:
        image_base64: Raw base64 string (may include data URL prefix or not).

    Returns:
        Tuple of (processed_base64, mime_type, error_message).
        - If successful: (base64_string, "image/png", None)
        - If image too large: (None, None, "error message for user")
        - If invalid/no image: (None, None, None)
    """
    if not image_base64 or not isinstance(image_base64, str):
        return None, None, None

    # Strip whitespace
    clean = image_base64.strip()
    if not clean:
        return None, None, None

    # If it's a data URL, extract the base64 part
    if clean.startswith("data:"):
        # Format: data:image/jpeg;base64,/9j/4AAQ...
        try:
            _, b64_data = clean.split(",", 1)
            clean = b64_data
        except ValueError:
            return None, None, None

    # Try to decode base64
    try:
        decoded = base64.b64decode(clean, validate=True)
    except Exception:
        return None, None, None

    # Check size limit (5MB)
    if len(decoded) > MAX_IMAGE_SIZE:
        size_mb = len(decoded) / (1024 * 1024)
        return None, None, f"Image too large ({size_mb:.1f}MB). Please use an image smaller than 5MB."

    # Try to open and convert the image using Pillow
    try:
        from PIL import Image

        img = Image.open(BytesIO(decoded))

        # Convert to RGB if necessary (handles RGBA, P mode, etc.)
        if img.mode in ("RGBA", "LA", "P"):
            # For images with transparency, convert to RGB with white background
            if img.mode == "P":
                img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode in ("RGBA", "LA"):
                background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
            else:
                background.paste(img)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Save as PNG to preserve quality (no compression artifacts)
        output = BytesIO()
        img.save(output, format="PNG")
        output.seek(0)

        # Check if converted image is too large
        png_data = output.read()
        if len(png_data) > MAX_IMAGE_SIZE:
            size_mb = len(png_data) / (1024 * 1024)
            return None, None, f"Image too large after processing ({size_mb:.1f}MB). Please use a smaller image."

        # Encode back to base64
        processed_b64 = base64.b64encode(png_data).decode("utf-8")
        return processed_b64, "image/png", None

    except Exception as e:
        log_interaction("image_processing_error", {"error": str(e)})
        return None, None, None
