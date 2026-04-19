"""Shared text normalization helpers."""
import re
import unicodedata


def strip_accents(s: str) -> str:
    """Remove Vietnamese diacritics via NFD normalization."""
    nfd = unicodedata.normalize("NFD", s)
    # Remove combining marks
    no_marks = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    # Special case: Vietnamese 'đ'/'Đ' does not decompose
    return no_marks.replace("đ", "d").replace("Đ", "D")


def norm(s: str) -> str:
    """Lowercase, strip accents, collapse whitespace, drop 'nganh'/'chuyen nganh' prefix."""
    s = strip_accents(s).lower()
    s = re.sub(r"[\s]+", " ", s).strip()
    # Drop prefixes
    s = re.sub(r"^(nganh|chuyen nganh)\s+", "", s)
    # Remove common filler words that don't matter for matching
    return s


def norm_uni(s: str) -> str:
    """Normalize university name for matching - aggressive."""
    s = norm(s)
    # Strip common affixes
    s = re.sub(r"\btruong\b", "", s)
    s = re.sub(r"\bhoc vien\b", "hv", s)
    s = re.sub(r"\bdai hoc\b", "dh", s)
    s = re.sub(r"\bco so\b.*", "", s)  # drop campus suffix
    s = re.sub(r"\bphia bac\b", "", s)
    s = re.sub(r"\bphia nam\b", "", s)
    s = re.sub(r"[-–—]", " ", s)
    s = re.sub(r"[\s]+", " ", s).strip()
    return s
