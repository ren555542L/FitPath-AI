import re
from typing import TypedDict

class SafetyResult(TypedDict):
    safety_status: str
    message: str
    medical_review_required: bool

# Medical risk terms to scan (as regex parts, word boundary is added dynamically)
MEDICAL_TERMS = [
    r"chest\s+pain",
    r"fainting",
    r"heart\s+attack",
    r"severe\s+palpitations",
    r"recent\s+surgery",
    r"post-op",
    r"fracture",
    r"torn\s+ligament",
    r"herniated\s+disc",
    r"severe\s+shortness\s+of\s+breath"
]

# General fitness redirect terms (bodybuilding / gym bro)
FITNESS_TERMS = [
    r"bodybuilding",
    r"bulk(?:ing)?",
    r"shred(?:ding)?",
    r"hypertrophy",
    r"steroids?",
    r"extreme\s+transformation"
]

# Extreme timelines/expectations
TIMELINE_TERMS = [
    r"lose\s+\d+\s*(?:kg|lbs|kilos|kilograms|pounds)?\s+in\s+\d+\s*days",
    r"lose\s+weight\s+instantly",
    r"extreme\s+fat\s+loss",
    r"rapid\s+transformation"
]

# Negation patterns to check before the matched terms
NEGATION_PATTERN = r"\b(?:no|don'?t\s+want(?:\s+to)?|do\s+not\s+want(?:\s+to)?|avoid|without)\s+"

def has_unnegated_match(text: str, term_pattern: str) -> bool:
    """Helper to detect if a specific term matches and is NOT negated."""
    # Pattern captures negation prefix (group 1) and the target term (group 2)
    pattern = re.compile(rf"(?:({NEGATION_PATTERN}))?(\b{term_pattern}\b)", re.IGNORECASE)
    for match in pattern.finditer(text):
        negation, term = match.groups()
        if not negation:
            return True
    return False

def screen_notes(notes: str | None) -> SafetyResult:
    """
    Screens onboarding notes for safety triggers in memory.
    Returns safety_status, medical_review_required, and a supportive message.
    """
    if not notes or not notes.strip():
        return {
            "safety_status": "safe",
            "message": "",
            "medical_review_required": False
        }

    # Normalize whitespace for cleaner matching
    normalized_notes = " ".join(notes.split())

    # 1. Check Medical Risk Terms first
    for term in MEDICAL_TERMS:
        if has_unnegated_match(normalized_notes, term):
            return {
                "safety_status": "medical_review_required",
                "message": (
                    "For your safety, FitPath requires a medical review before starting. "
                    "We recommend consulting a qualified healthcare professional regarding any "
                    "chest pain, fainting, heart conditions, recent surgeries, fractures, or joint issues."
                ),
                "medical_review_required": True
            }

    # 2. Check General Fitness terms
    for term in FITNESS_TERMS:
        if has_unnegated_match(normalized_notes, term):
            return {
                "safety_status": "general_fitness_redirect",
                "message": (
                    "FitPath focuses on stamina, mobility, posture, balance, functional strength, "
                    "and sustainable habits. We do not support bodybuilding, bulking, shredding, "
                    "hypertrophy, steroids, or extreme transformations."
                ),
                "medical_review_required": False
            }

    # 3. Check Extreme Timeline terms (unnegated checks or direct checks)
    for term in TIMELINE_TERMS:
        if re.search(rf"\b{term}\b", normalized_notes, re.IGNORECASE):
            return {
                "safety_status": "general_fitness_redirect",
                "message": (
                    "FitPath focuses on safe, gradual, and sustainable wellness habits rather than "
                    "rapid or extreme weight loss. We recommend a target of 0.5 to 1 kg of weight loss "
                    "per week for long-term health."
                ),
                "medical_review_required": False
            }

    return {
        "safety_status": "safe",
        "message": "",
        "medical_review_required": False
    }
