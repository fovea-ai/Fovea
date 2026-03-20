# =============================================================================
# ai_handler.py — Fovea AI Provider Integration
# =============================================================================
#
# This file handles all communication with AI providers (ChatGPT, Gemini,
# Claude, Grok, DeepSeek). It sends camera frames to the AI and asks whether
# the frame matches what the user is searching for.
#
# HOW IT WORKS (for beginners):
#   1. A frame (single photo from a camera) is converted to base64 (text format)
#   2. That base64 image is sent to the AI API along with a question
#   3. The AI replies "YES | description" or "NO | description"
#   4. We parse that reply and return (True/False, description) to the search
#
# IMPORTANT: DeepSeek cannot see images — it is TEXT ONLY.
#   For DeepSeek, we skip sending images and instead match keywords in
#   saved text descriptions.
#
# Photo Enhancement (ChatGPT and Gemini only):
#   Instead of just asking "does this match?", we first ask the AI to
#   describe the frame in maximum detail, then use that rich description
#   to do the match. More accurate but uses more API credits.
# =============================================================================

import base64
import requests
import os
from core.storage import get_secure_setting, get_setting

# Providers that CANNOT analyze images — text/keyword search only
TEXT_ONLY_PROVIDERS = {"deepseek"}

# Providers that support Photo Enhancement (rich description before matching)
ENHANCE_PROVIDERS = {"openai", "gemini"}


# =============================================================================
# Image Encoding
# =============================================================================

def encode_image(filepath: str) -> str:
    """
    Convert an image file to base64 string.

    Why base64? AI APIs don't accept raw files — they need the image
    encoded as text so it can be sent inside a JSON request body.

    Args:
        filepath: Path to the image file on disk

    Returns:
        Base64-encoded string of the image
    """
    with open(filepath, "rb") as f:
        # "rb" = read binary — read raw bytes, not text
        return base64.b64encode(f.read()).decode("utf-8")


# =============================================================================
# Helper Utilities
# =============================================================================

def provider_supports_vision() -> bool:
    """
    Check if the currently configured AI provider can analyze images.
    DeepSeek cannot — it only understands text.
    """
    provider = get_setting("ai_provider", "")
    return provider not in TEXT_ONLY_PROVIDERS and provider != ""


# =============================================================================
# Photo Enhancement
# =============================================================================

def enhance_image(filepath: str) -> str | None:
    """
    Ask the AI to describe a camera frame in MAXIMUM detail.

    This is used for Photo Enhancement mode. Instead of asking "does this
    match the query?", we first get a rich detailed description of everything
    in the frame, then use that to make the match decision.

    Example output:
        "A red sedan car (possibly Honda Civic) parked facing left. The car
        has a white horizontal stripe along the lower door panel. License plate
        partially visible: XY-1... Two people walking in background, one wearing
        a blue jacket and carrying a backpack. Daytime, clear weather."

    Only works for ChatGPT and Gemini. Returns None for other providers.

    Args:
        filepath: Path to the camera frame image

    Returns:
        Detailed description string, or None if enhancement failed
    """
    provider = get_setting("ai_provider", "")
    api_key  = get_secure_setting("ai_api_key", "")

    # Only GPT and Gemini support enhancement
    if provider not in ENHANCE_PROVIDERS or not api_key:
        return None

    # This prompt instructs the AI to be as specific as possible
    # because vague descriptions ("a car", "a person") won't match well
    prompt = (
        "You are analyzing a security camera frame. "
        "Describe EVERYTHING you see in exhaustive detail: "
        "people (clothing colors, hair, build, age estimate, gender), "
        "vehicles (make, model if visible, color, markings, license plate if visible), "
        "objects, locations, lighting, weather, actions happening. "
        "Be specific about colors — don't say 'dark', say 'navy blue' or 'charcoal'. "
        "This description will be used to match search queries."
    )

    try:
        if provider == "openai":
            return _openai_query(filepath, api_key, prompt)
        elif provider == "gemini":
            return _gemini_query(filepath, api_key, prompt)
    except Exception:
        # Enhancement failed — that's OK, we'll fall through to standard search
        return None


# =============================================================================
# Frame Description (used for training data labeling)
# =============================================================================

def describe_image(filepath: str) -> str | None:
    """
    Get a plain description of a frame for saving to the database.
    Used when labeling frames for the AI training system.

    Args:
        filepath: Path to the camera frame image

    Returns:
        Description string, or None if no AI configured or AI failed
    """
    provider = get_setting("ai_provider", "")
    api_key  = get_secure_setting("ai_api_key", "")

    # Can't describe without an API key
    if not provider or not api_key:
        return None

    # DeepSeek cannot see images
    if provider in TEXT_ONLY_PROVIDERS:
        return None

    prompt = (
        "Describe this security camera image in detail. "
        "Include all objects, people, vehicles, colors, and notable features."
    )

    try:
        if provider == "openai":
            return _openai_query(filepath, api_key, prompt)
        elif provider == "gemini":
            return _gemini_query(filepath, api_key, prompt)
        elif provider == "claude":
            return _claude_query(filepath, api_key, prompt)
        elif provider == "grok":
            return _grok_query(filepath, api_key, prompt)
    except Exception as e:
        return f"[AI Error: {e}]"

    return None


# =============================================================================
# Main Search Function
# =============================================================================

def search_with_ai(query: str, filepath: str,
                   saved_description: str | None = None,
                   use_enhancement: bool = False) -> tuple[bool, str | None]:
    """
    Ask the AI: does this camera frame match the user's search query?

    This is the CORE function of Fovea's search system.
    It is called once per frame during a search operation.

    There are three search modes:
    ─────────────────────────────────────────────────────────────────────────
    1. DEEPSEEK MODE (text only):
       DeepSeek cannot see images. Instead, we keyword-match the search
       query against any saved text description of the frame.
       Fast and free, but only works if frames have been described before.

    2. ENHANCEMENT MODE (GPT/Gemini only):
       First, ask AI to describe the frame in rich detail (enhance_image).
       Then, ask AI if that detailed description matches the query.
       Most accurate, but costs 2× the API credits per frame.

    3. STANDARD VISION MODE (GPT, Gemini, Claude, Grok):
       Send the image directly to the AI with the question:
       "Does this frame match: [query]? YES/NO | description"
       Good balance of speed and accuracy.
    ─────────────────────────────────────────────────────────────────────────

    Args:
        query:            What the user typed in the search box
        filepath:         Path to the camera frame image on disk
        saved_description: Any previously saved AI description of this frame
        use_enhancement:  If True, use Photo Enhancement mode (slower, more accurate)

    Returns:
        Tuple of (matched: bool, description: str | None)
        - matched: True if the AI thinks this frame matches the query
        - description: What the AI says it sees in the frame
    """
    provider = get_setting("ai_provider", "")
    api_key  = get_secure_setting("ai_api_key", "")

    # No provider configured — can't search with AI
    if not provider or not api_key:
        return False, None

    # ── Mode 1: DeepSeek — text/keyword search only ───────────────────────────
    if provider in TEXT_ONLY_PROVIDERS:
        if not saved_description:
            # No description to match against — skip this frame
            return False, None

        # Split the query into individual keywords and check each one
        # We ignore very short words (less than 3 chars) like "a", "in", "the"
        keywords = [word.lower() for word in query.split() if len(word) > 2]
        matched  = any(keyword in saved_description.lower() for keyword in keywords)
        return matched, saved_description

    # ── Mode 2: Photo Enhancement ─────────────────────────────────────────────
    if use_enhancement and provider in ENHANCE_PROVIDERS:
        enhanced_desc = enhance_image(filepath)

        if enhanced_desc:
            # Use the detailed description to ask the AI a focused question
            enhanced_prompt = (
                f"You are analyzing a security camera frame. "
                f"The detailed description of this frame is:\n{enhanced_desc}\n\n"
                f"The user searches for: '{query}'.\n"
                f"Does this frame match the search? Answer YES or NO first, then briefly explain.\n"
                f"Format: YES/NO | explanation"
            )
            try:
                # Ask the AI using the enhanced description as context
                if provider == "openai":
                    response = _openai_query(filepath, api_key, enhanced_prompt)
                elif provider == "gemini":
                    response = _gemini_query(filepath, api_key, enhanced_prompt)
                else:
                    response = None

                if response:
                    parts   = response.split("|", 1)
                    matched = parts[0].strip().upper().startswith("YES")
                    desc    = f"[Enhanced] {parts[1].strip() if len(parts) > 1 else enhanced_desc}"
                    return matched, desc
            except Exception:
                pass  # Enhancement failed — fall through to standard search

    # ── Mode 3: Standard vision search ───────────────────────────────────────
    # Build the prompt that asks the AI to check if the frame matches
    prompt = (
        f"You are analyzing a security camera frame. "
        f"The user searches for: '{query}'. "
        f"Does this image match? Answer YES or NO first, then describe what you see. "
        f"Format: YES/NO | description"
    )

    try:
        # Send to the appropriate AI provider
        if provider == "openai":
            response = _openai_query(filepath, api_key, prompt)
        elif provider == "gemini":
            response = _gemini_query(filepath, api_key, prompt)
        elif provider == "claude":
            response = _claude_query(filepath, api_key, prompt)
        elif provider == "grok":
            response = _grok_query(filepath, api_key, prompt)
        else:
            return False, None

        # Parse the "YES/NO | description" response format
        if response:
            parts   = response.split("|", 1)
            matched = parts[0].strip().upper().startswith("YES")
            desc    = parts[1].strip() if len(parts) > 1 else response
            return matched, desc

    # ── Error Handling ────────────────────────────────────────────────────────
    # We raise RuntimeError with friendly messages so the search worker
    # can display them to the user and decide whether to keep trying.

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot reach the AI service. Check your internet connection."
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            "AI request timed out (took too long). Try again."
        )
    except requests.exceptions.HTTPError as e:
        # HTTP error codes tell us exactly what went wrong
        code = e.response.status_code if e.response else "?"
        if code == 401:
            raise RuntimeError(
                "Invalid API key. Go to Settings and check your API key."
            )
        elif code == 429:
            raise RuntimeError(
                "AI rate limit reached — you sent too many requests. "
                "Wait a moment and try again, or search a shorter time range."
            )
        elif code == 402:
            raise RuntimeError(
                "AI API quota exceeded. Your account has run out of credits. "
                "Check your billing at the provider's website."
            )
        else:
            raise RuntimeError(f"AI API returned error {code}. Try again.")
    except Exception as e:
        raise RuntimeError(f"Unexpected AI error: {e}")

    return False, None


# =============================================================================
# Provider-Specific API Functions
# =============================================================================
# Each function below handles ONE specific AI provider.
# They all do the same thing:
#   1. Encode the image as base64
#   2. Build the request body (JSON format required by that provider)
#   3. Send the HTTP POST request to the provider's API
#   4. Extract and return the text response
#
# If you want to add a new AI provider, add a new function here and
# add a case for it in search_with_ai() and describe_image() above.
# =============================================================================


def _openai_query(filepath: str, api_key: str, prompt: str) -> str:
    """
    Send a frame to OpenAI's GPT-4o and get a response.

    Model: gpt-5.4-mini — fast, affordable, excellent vision.
    Docs:  https://platform.openai.com/docs/guides/vision

    The image is embedded directly in the message as a base64 data URL,
    which means we don't need to upload it anywhere first.
    """
    img_b64 = encode_image(filepath)

    headers = {
        "Authorization": f"Bearer {api_key}",  # API key authentication
        "Content-Type": "application/json"
    }

    body = {
        "model": "gpt-5.4-mini",           # Best vision model from OpenAI
        "messages": [{
            "role": "user",
            "content": [
                # The image, embedded as a base64 data URL
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                },
                # The question/prompt
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }],
        "max_tokens": 400  # Max length of the AI's reply
    }

    # Send the request and raise an error if HTTP status is not 200
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers, json=body, timeout=30
    )
    r.raise_for_status()

    # Extract the text from the response JSON
    return r.json()["choices"][0]["message"]["content"]


def _gemini_query(filepath: str, api_key: str, prompt: str) -> str:
    """
    Send a frame to Google's Gemini 2.5 Flash and get a response.

    Model: gemini-3.1-pro-preview — Google's latest vision model (March 2026).
    Docs:  https://ai.google.dev/gemini-api/docs

    Note: Gemini's API format is different from OpenAI's —
    the image and text go in "parts" inside "contents".
    The API key is passed as a URL parameter, not a header.
    """
    img_b64 = encode_image(filepath)

    # API key is appended to the URL for Gemini
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-2.5-flash:generateContent?key={api_key}"
    )

    body = {
        "contents": [{
            "parts": [
                # Image part — Gemini calls it "inline_data"
                {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                # Text prompt part
                {"text": prompt}
            ]
        }]
    }

    r = requests.post(url, json=body, timeout=30)
    r.raise_for_status()

    # Gemini's response structure is nested differently from OpenAI
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _claude_query(filepath: str, api_key: str, prompt: str) -> str:
    """
    Send a frame to Anthropic's Claude and get a response.

    Model: claude-opus-4-5 — Anthropic's most capable vision model.
    Docs:  https://docs.anthropic.com/en/api/messages

    Claude uses a different authentication header ("x-api-key" instead
    of "Authorization: Bearer") and a different JSON structure.
    """
    img_b64 = encode_image(filepath)

    headers = {
        "x-api-key": api_key,                  # Claude uses this header for auth
        "anthropic-version": "2023-06-01",      # Required API version header
        "content-type": "application/json"
    }

    body = {
        "model": "claude-opus-4-5",
        "max_tokens": 400,
        "messages": [{
            "role": "user",
            "content": [
                # Claude's image format uses "source" with base64 data
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_b64
                    }
                },
                # The text prompt comes after the image
                {"type": "text", "text": prompt}
            ]
        }]
    }

    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers, json=body, timeout=30
    )
    r.raise_for_status()

    # Claude's response structure
    return r.json()["content"][0]["text"]


def _grok_query(filepath: str, api_key: str, prompt: str) -> str:
    """
    Send a frame to xAI's Grok and get a response.

    Model: grok-2-vision-latest — xAI's vision model.
    Docs:  https://docs.x.ai/api

    Grok uses the same API format as OpenAI (they're compatible),
    just with a different base URL and model name.
    """
    img_b64 = encode_image(filepath)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    body = {
        "model": "grok-2-vision-latest",
        "messages": [{
            "role": "user",
            "content": [
                # Same format as OpenAI
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                },
                {"type": "text", "text": prompt}
            ]
        }],
        "max_tokens": 400
    }

    r = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers=headers, json=body, timeout=30
    )
    r.raise_for_status()

    return r.json()["choices"][0]["message"]["content"]

# =============================================================================
# Note for contributors:
# To add a new AI provider:
# 1. Add a new function _yourprovider_query(filepath, api_key, prompt) above
# 2. Add the provider key to TEXT_ONLY_PROVIDERS if it can't see images
# 3. Add the provider key to ENHANCE_PROVIDERS if it supports enhancement
# 4. Add elif branches in search_with_ai() and describe_image()
# 5. Add the provider to PROVIDERS dict in ui/settings_page.py
# =============================================================================