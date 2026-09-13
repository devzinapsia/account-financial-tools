"""Best-effort extraction of Argentine CUIT/DNI numbers from free-text bank
statement legends (e.g. the "Contacto"/"Detalle"/"Concepto" column of a bank
export), used to auto-assign a partner during statement import.
"""

import re

# AFIP's modulo-11 check digit algorithm for the first 10 digits of a CUIT.
_CUIT_MULTIPLIERS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)

# 11 digits, optionally split as XX-XXXXXXXX-X with '-' or whitespace as
# separator. The negative lookaround ensures we never match a substring of a
# longer digit run (e.g. an 18-digit CBU account number), since any digit
# immediately before/after the candidate would fail the lookaround.
_CUIT_RE = re.compile(r'(?<!\d)(\d{2})[-\s]?(\d{8})[-\s]?(\d)(?!\d)')

# A DNI has no check digit and no fixed separator convention, so it's
# recognized only by shape: 7 or 8 bare digits, or the same digits grouped in
# thousands with '.' (e.g. "12.345.678").
_DNI_RE = re.compile(r'(?<!\d)(\d{1,2}\.\d{3}\.\d{3}|\d{7,8})(?!\d)')
_DNI_HINT_RE = re.compile(r'\bDNI\b\s*[:.\-]?\s*(\d{1,2}\.?\d{3}\.?\d{3}|\d{7,8})', re.IGNORECASE)


def _cuit_check_digit(digits10):
    """Return the expected AFIP check digit for the first 10 digits of a
    CUIT, or None if the modulo-11 remainder is 10 (conventionally treated
    as an invalid CUIT, since it can't be represented as a single digit)."""
    total = sum(int(digit) * multiplier for digit, multiplier in zip(digits10, _CUIT_MULTIPLIERS))
    remainder = 11 - (total % 11)
    if remainder == 11:
        return 0
    if remainder == 10:
        return None
    return remainder


def is_valid_cuit(cuit):
    """Whether ``cuit`` (11 digits, no separators) has a valid AFIP check digit."""
    if not cuit or not re.fullmatch(r'\d{11}', cuit):
        return False
    expected = _cuit_check_digit(cuit[:10])
    return expected is not None and expected == int(cuit[10])


def _find_cuit_candidates(text):
    """Yield (span, digits) for every CUIT-shaped substring in ``text``,
    regardless of check-digit validity (used both to find valid CUITs and to
    exclude those spans from DNI detection)."""
    for match in _CUIT_RE.finditer(text or ''):
        yield match.span(), ''.join(match.groups())


def extract_cuit(text):
    """Return the single valid CUIT (11 digits, no separators) found in
    ``text``, or None if zero or more than one distinct valid CUIT is found."""
    valid_cuits = {digits for _, digits in _find_cuit_candidates(text) if is_valid_cuit(digits)}
    if len(valid_cuits) == 1:
        return next(iter(valid_cuits))
    return None


def extract_dni(text):
    """Best-effort extraction of a single Argentine DNI from ``text``.

    A DNI has no check digit, so this is inherently more ambiguous than CUIT
    extraction: it never overlaps a CUIT-shaped span (valid or not), prefers
    a number explicitly preceded by the word "DNI", and otherwise falls back
    to a single unambiguous 7-8 digit candidate. Returns None on any
    ambiguity (zero or several distinct candidates) rather than guessing.
    """
    if not text:
        return None

    hint_match = _DNI_HINT_RE.search(text)
    if hint_match:
        digits = hint_match.group(1).replace('.', '')
        if 7 <= len(digits) <= 8:
            return digits

    cuit_spans = [span for span, _ in _find_cuit_candidates(text)]

    def _overlaps_cuit(span):
        return any(span[0] < end and span[1] > start for start, end in cuit_spans)

    candidates = {
        match.group(1).replace('.', '')
        for match in _DNI_RE.finditer(text)
        if not _overlaps_cuit(match.span())
    }
    candidates = {digits for digits in candidates if 7 <= len(digits) <= 8}
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def normalize_vat(vat):
    """Strip everything but digits, for comparing a CUIT extracted from free
    text against ``res.partner.vat`` regardless of how the latter is
    formatted (with/without dashes, with/without an "AR" country prefix)."""
    return re.sub(r'\D', '', vat or '')
