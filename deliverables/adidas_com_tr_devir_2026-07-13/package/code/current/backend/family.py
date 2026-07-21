from product_identity import identity_from_title


def make_family_key(text):
    """Build a color-independent key without merging gender, width or generations."""
    if not text:
        return None
    return identity_from_title(text).family_key or None
