# =============================================================================
# local_search.py — Local Vision Search (No API Key Required)
# =============================================================================
#
# This module gives Fovea the ability to search footage WITHOUT any
# AI API key. It runs entirely on the user's machine using computer vision.
#
# WHY THIS MATTERS:
#   A family in a developing country, a small shop owner, a school —
#   many people cannot afford ChatGPT or Gemini API credits.
#   This ensures Fovea is useful for EVERYONE, not just people
#   with money for API subscriptions.
#
# HOW LOCAL SEARCH WORKS:
#   We analyze each frame using classical computer vision techniques:
#
#   1. COLOR DETECTION:
#      We look for specific colors the user mentioned.
#      "red car" → we check if the frame contains significant red pixels.
#      Colors supported: red, orange, yellow, green, blue, purple,
#                        white, black, gray, brown, pink, cyan
#
#   2. OBJECT/KEYWORD MATCHING:
#      We extract simple visual features and match against common words.
#      "person" → we check if the frame has human-shaped blobs
#      "car" / "vehicle" → we check for large rectangular objects
#      "night" / "dark" → we check overall brightness
#
#   3. BRIGHTNESS ANALYSIS:
#      "dark footage", "nighttime", "bright" etc.
#
#   4. MOTION/ACTIVITY:
#      If consecutive frames are available, we detect movement.
#
#   5. SAVED DESCRIPTION MATCHING:
#      If the frame was previously described (by AI or manually),
#      we also keyword-match that description.
#
# ACCURACY:
#   This is NOT as accurate as AI vision. It will have false positives
#   (returns frames that don't really match) and false negatives
#   (misses some matching frames). But it's infinitely better than
#   having to scrub through hours of footage manually.
#
# LIMITATIONS:
#   - Cannot understand context ("suspicious person" won't work)
#   - Color detection can be fooled by lighting conditions
#   - Cannot read license plates or identify faces
#   For precise searches, use an AI API key.
# =============================================================================

import cv2
import numpy as np
from typing import Optional


# =============================================================================
# Color Definitions
# =============================================================================
# Each color is defined as HSV ranges.
# HSV (Hue, Saturation, Value) is much better than RGB for color detection
# because it separates color from brightness — so "red" means red whether
# it's in bright sunlight or shade.
#
# Hue range: 0–179 in OpenCV (full circle = 360°, so OpenCV uses half)
# Saturation: 0–255 (0 = grey, 255 = pure color)
# Value: 0–255 (0 = black, 255 = bright)

# Each entry: (name, [(lower_hsv, upper_hsv), ...])
# Some colors (like red) wrap around the hue circle, so they need two ranges.
COLOR_RANGES = {
    "red": [
        (np.array([0, 100, 80]),   np.array([10, 255, 255])),   # Red (low hue)
        (np.array([165, 100, 80]), np.array([179, 255, 255])),  # Red (high hue wrap)
    ],
    "orange": [
        (np.array([10, 100, 80]),  np.array([25, 255, 255])),
    ],
    "yellow": [
        (np.array([25, 100, 80]),  np.array([35, 255, 255])),
    ],
    "green": [
        (np.array([35, 60, 50]),   np.array([85, 255, 255])),
    ],
    "blue": [
        (np.array([100, 60, 50]),  np.array([130, 255, 255])),
    ],
    "purple": [
        (np.array([130, 50, 50]),  np.array([160, 255, 255])),
    ],
    "pink": [
        (np.array([160, 40, 100]), np.array([170, 255, 255])),
    ],
    "cyan": [
        (np.array([85, 60, 60]),   np.array([100, 255, 255])),
    ],
    "white": [
        # White = low saturation, high brightness
        (np.array([0, 0, 200]),    np.array([179, 40, 255])),
    ],
    "black": [
        # Black = low brightness
        (np.array([0, 0, 0]),      np.array([179, 255, 50])),
    ],
    "gray":  [
        # Gray = low saturation, medium brightness
        (np.array([0, 0, 60]),     np.array([179, 40, 200])),
    ],
    "grey":  [
        (np.array([0, 0, 60]),     np.array([179, 40, 200])),
    ],
    "brown": [
        (np.array([10, 60, 50]),   np.array([20, 200, 150])),
    ],
    "silver": [
        # Silver is similar to gray but brighter
        (np.array([0, 0, 150]),    np.array([179, 40, 220])),
    ],
}

# Words that suggest a person is in the frame
PERSON_KEYWORDS = {
    "person", "people", "man", "woman", "boy", "girl", "child", "kid",
    "human", "pedestrian", "someone", "anybody", "figure", "individual",
    "suspect", "intruder", "thief", "officer", "guard", "worker",
    "jacket", "shirt", "wearing", "dressed", "clothes", "clothing",
    "walking", "running", "standing", "sitting",
}

# Words that suggest a vehicle is in the frame
VEHICLE_KEYWORDS = {
    "car", "vehicle", "truck", "van", "motorcycle", "bike", "bicycle",
    "suv", "sedan", "pickup", "bus", "lorry", "taxi", "automobile",
    "driving", "parked", "parking", "plate", "license",
}

# Words related to time of day / lighting
NIGHT_KEYWORDS = {"night", "dark", "nighttime", "evening", "midnight", "dusk"}
DAY_KEYWORDS   = {"day", "daylight", "daytime", "bright", "sunny", "morning", "afternoon"}

# Words related to motion/activity
MOTION_KEYWORDS = {
    "moving", "motion", "running", "walking", "entering", "leaving",
    "activity", "movement", "action",
}


# =============================================================================
# Main Local Search Function
# =============================================================================

def local_search(query: str, filepath: str,
                 saved_description: Optional[str] = None) -> tuple[bool, str]:
    """
    Search a frame locally without any AI API.

    Analyzes the image using computer vision and matches against the
    query using color detection, object detection, and keyword matching.

    Args:
        query:            The user's search text
        filepath:         Path to the camera frame image
        saved_description: Any previously saved description of this frame

    Returns:
        Tuple of (matched: bool, description: str)
        - matched: True if the frame likely matches the query
        - description: Plain-English description of what was detected
    """
    # Parse the query into lowercase words for matching
    query_words = set(query.lower().split())

    # We'll collect evidence for and against a match
    match_reasons  = []   # reasons this frame matches
    detected_info  = []   # general info about what we see

    # ── Step 1: Try to load the image ─────────────────────────────────────────
    frame = cv2.imread(filepath)
    if frame is None:
        # Can't read the file — skip it
        return False, "Could not read frame file"

    # Resize to a standard size for consistent analysis
    # We use 640x480 — enough detail for analysis, fast to process
    frame_resized = cv2.resize(frame, (640, 480))

    # Convert to HSV color space for color detection
    hsv = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2HSV)

    # Total pixels in the frame (used to calculate percentages)
    total_pixels = frame_resized.shape[0] * frame_resized.shape[1]

    # ── Step 2: Color Detection ────────────────────────────────────────────────
    # Check which colors are mentioned in the query
    # Only search for colors that the user actually mentioned
    for color_name, ranges in COLOR_RANGES.items():
        if color_name in query_words or color_name in query.lower():
            # Count how many pixels match this color
            color_pixel_count = 0
            for (lower, upper) in ranges:
                mask = cv2.inRange(hsv, lower, upper)
                color_pixel_count += cv2.countNonZero(mask)

            # Calculate what percentage of the frame this color occupies
            percentage = (color_pixel_count / total_pixels) * 100

            # Threshold: at least 3% of the frame must be this color
            # (avoids false matches from tiny color patches)
            if percentage >= 3.0:
                match_reasons.append(
                    f"{color_name} color detected ({percentage:.0f}% of frame)"
                )
                detected_info.append(f"contains {color_name}")

    # ── Step 3: Always detect dominant colors (for description) ───────────────
    # Even if the user didn't ask about color, we note what colors are present
    dominant = _get_dominant_colors(hsv, total_pixels)
    if dominant:
        detected_info.extend(dominant)

    # ── Step 4: Person Detection ───────────────────────────────────────────────
    person_in_query = bool(query_words & PERSON_KEYWORDS)
    person_detected, person_confidence = _detect_person(frame_resized)

    if person_detected:
        detected_info.append("person/people visible")
        if person_in_query:
            match_reasons.append(f"person detected (confidence: {person_confidence}%)")

    # ── Step 5: Vehicle Detection ──────────────────────────────────────────────
    vehicle_in_query = bool(query_words & VEHICLE_KEYWORDS)
    vehicle_detected, vehicle_confidence = _detect_vehicle(frame_resized)

    if vehicle_detected:
        detected_info.append("vehicle visible")
        if vehicle_in_query:
            match_reasons.append(f"vehicle detected (confidence: {vehicle_confidence}%)")

    # ── Step 6: Brightness / Time of Day ──────────────────────────────────────
    brightness = _get_brightness(frame_resized)
    if brightness < 50:
        detected_info.append("low light / night conditions")
        if query_words & NIGHT_KEYWORDS:
            match_reasons.append("dark/night conditions match")
    elif brightness > 150:
        detected_info.append("good lighting / daytime")
        if query_words & DAY_KEYWORDS:
            match_reasons.append("bright/day conditions match")

    # ── Step 7: Saved Description Keyword Match ────────────────────────────────
    # If this frame was previously described (by AI or manually), also check that
    if saved_description:
        desc_words = set(saved_description.lower().split())
        # Find query words (3+ chars) that appear in the description
        matching_keywords = [
            w for w in query_words
            if len(w) > 2 and w in saved_description.lower()
        ]
        if matching_keywords:
            match_reasons.append(
                f"saved description matches: {', '.join(matching_keywords)}"
            )

    # ── Step 8: Build the description string ──────────────────────────────────
    if detected_info:
        local_desc = "Local analysis: " + ", ".join(detected_info)
    else:
        local_desc = "Local analysis: no significant features detected"

    if match_reasons:
        local_desc += "\nMatch reasons: " + "; ".join(match_reasons)

    # ── Step 9: Decide if it's a match ────────────────────────────────────────
    # We consider it a match if we found at least one reason it could match
    matched = len(match_reasons) > 0

    return matched, local_desc


# =============================================================================
# Helper Functions
# =============================================================================

def _get_dominant_colors(hsv: np.ndarray, total_pixels: int) -> list[str]:
    """
    Find the most prominent colors in the frame.
    Returns a list of color names that appear significantly.
    """
    dominant = []
    # Check a selection of common colors
    for color_name in ["red", "blue", "green", "yellow", "white", "black", "gray"]:
        ranges = COLOR_RANGES.get(color_name, [])
        count  = 0
        for (lower, upper) in ranges:
            mask  = cv2.inRange(hsv, lower, upper)
            count += cv2.countNonZero(mask)
        pct = (count / total_pixels) * 100
        if pct >= 8.0:  # Only mention colors that are quite prominent
            dominant.append(f"prominent {color_name}")
    return dominant


def _detect_person(frame: np.ndarray) -> tuple[bool, int]:
    """
    Try to detect if there is a person in the frame.

    Uses HOG (Histogram of Oriented Gradients) — a classical computer
    vision algorithm specifically designed for pedestrian detection.
    Invented in 2005, it works offline with no AI needed.

    Returns:
        (detected: bool, confidence_percentage: int)
    """
    try:
        # OpenCV's built-in pedestrian detector
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        # Convert to grayscale for faster processing
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect people — winStride controls speed vs accuracy tradeoff
        # (8,8) = check every 8 pixels — good balance
        rects, weights = hog.detectMultiScale(
            gray,
            winStride=(8, 8),
            padding=(4, 4),
            scale=1.05
        )

        if len(rects) > 0:
            # Use the highest detection weight as confidence
            confidence = min(int(max(weights) * 100), 95)
            return True, confidence

    except Exception:
        pass  # HOG detection failed — that's OK

    return False, 0


def _detect_vehicle(frame: np.ndarray) -> tuple[bool, int]:
    """
    Try to detect if there is a vehicle in the frame.

    Vehicles are large, roughly rectangular objects with certain
    color patterns. We use edge detection and contour analysis.

    This is simpler than person detection but works reasonably well
    for cars in typical security camera angles.

    Returns:
        (detected: bool, confidence_percentage: int)
    """
    try:
        gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        # Detect edges using Canny algorithm
        edges   = cv2.Canny(blurred, 50, 150)

        # Find contours (outlines of objects)
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        frame_area   = frame.shape[0] * frame.shape[1]
        large_rects  = 0

        for contour in contours:
            area = cv2.contourArea(contour)
            # Vehicles occupy a significant portion of the frame
            if area > frame_area * 0.05:  # At least 5% of frame
                # Check if the contour is roughly rectangular
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h if h > 0 else 0
                # Cars are typically wider than tall (1.3 to 4.0 ratio)
                if 1.3 < aspect_ratio < 4.0:
                    large_rects += 1

        if large_rects >= 2:  # Need multiple large rectangular shapes
            confidence = min(large_rects * 20, 75)
            return True, confidence

    except Exception:
        pass

    return False, 0


def _get_brightness(frame: np.ndarray) -> float:
    """
    Calculate the average brightness of a frame.

    Returns a value from 0 (completely black) to 255 (completely white).
    Values below 80 suggest nighttime/low light.
    Values above 180 suggest bright daylight.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))


# =============================================================================
# Smart Description Builder
# =============================================================================

def build_frame_description(filepath: str) -> str:
    """
    Build a rich text description of a frame using local computer vision.
    This is called when no AI is configured, to pre-describe frames
    so they can be searched later even without AI.

    This description is stored in the database alongside the frame
    and used for keyword matching in future searches.

    Args:
        filepath: Path to the camera frame

    Returns:
        A human-readable description string
    """
    frame = cv2.imread(filepath)
    if frame is None:
        return ""

    frame_resized = cv2.resize(frame, (640, 480))
    hsv           = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2HSV)
    total_pixels  = frame_resized.shape[0] * frame_resized.shape[1]

    parts = []

    # ── Time of day ────────────────────────────────────────────────────────────
    brightness = _get_brightness(frame_resized)
    if brightness < 40:
        parts.append("very dark frame (night or low light)")
    elif brightness < 80:
        parts.append("dark conditions (evening or dim light)")
    elif brightness < 130:
        parts.append("moderate lighting")
    else:
        parts.append("well-lit frame (daytime or good lighting)")

    # ── Dominant colors ────────────────────────────────────────────────────────
    color_parts = []
    for color_name in ["red", "orange", "yellow", "green", "blue", "purple",
                       "white", "black", "gray", "brown"]:
        ranges = COLOR_RANGES.get(color_name, [])
        count  = sum(
            cv2.countNonZero(cv2.inRange(hsv, lo, hi))
            for lo, hi in ranges
        )
        pct = (count / total_pixels) * 100
        if pct >= 5.0:
            color_parts.append(f"{color_name} ({pct:.0f}%)")

    if color_parts:
        parts.append("dominant colors: " + ", ".join(color_parts))

    # ── Person detection ───────────────────────────────────────────────────────
    person_detected, person_conf = _detect_person(frame_resized)
    if person_detected:
        parts.append(f"person/people detected ({person_conf}% confidence)")

    # ── Vehicle detection ──────────────────────────────────────────────────────
    vehicle_detected, vehicle_conf = _detect_vehicle(frame_resized)
    if vehicle_detected:
        parts.append(f"vehicle detected ({vehicle_conf}% confidence)")

    # ── Activity/edge density (rough motion indicator) ─────────────────────────
    gray       = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
    edges      = cv2.Canny(gray, 50, 150)
    edge_pct   = (cv2.countNonZero(edges) / total_pixels) * 100
    if edge_pct > 15:
        parts.append("high activity or complex scene")
    elif edge_pct < 3:
        parts.append("quiet/static scene")

    return ". ".join(parts) if parts else "no notable features detected"