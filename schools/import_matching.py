import re
from difflib import SequenceMatcher


FUZZY_AUTO_THRESHOLD = 0.86
FUZZY_REVIEW_THRESHOLD = 0.72


def normalize_name(text):
    """Normalize names enough to compare imports without changing stored values."""
    text = (text or '').strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return re.sub(r'[^a-z0-9\s\-()]', '', text)


def find_name_match(model, name, threshold=FUZZY_AUTO_THRESHOLD):
    """
    Find an existing object by a user-entered name.

    Returns (obj, was_corrected, matched_name, ratio). If no match is confident
    enough, obj is None and matched_name/ratio describe the closest candidate.
    """
    exact = model.objects.filter(name__iexact=name).first()
    if exact:
        return exact, False, exact.name, 1.0

    normalized_input = normalize_name(name)
    if not normalized_input:
        return None, False, None, 0.0

    best_obj = None
    best_ratio = 0.0

    for obj in model.objects.all():
        normalized_existing = normalize_name(obj.name)
        if normalized_existing == normalized_input:
            return obj, True, obj.name, 1.0

        ratio = SequenceMatcher(None, normalized_input, normalized_existing).ratio()
        if ratio > best_ratio:
            best_obj = obj
            best_ratio = ratio

    if best_obj and best_ratio >= threshold:
        return best_obj, True, best_obj.name, best_ratio

    return None, False, best_obj.name if best_obj else None, best_ratio

