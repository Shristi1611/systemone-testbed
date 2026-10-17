import re
import unicodedata

RULES = {
    "override": re.compile(
        r"\b(forget|ignore|disregard|vergiss\w*|ignorier\w*|missacht\w*|oubli\w+|zaboravi|bhool\w*|anadekha)\b"
        r".{0,60}\b(everything|instructions?|rules?|above|before|previous|earlier|anweisung\w*|regeln|alles|davor|instrukcij\w*|niyam|nirdesh\w*|saare)\b",
        re.I | re.S),
    "persona": re.compile(
        r"\b(you are now|now you are|from now on|pretend|role-?play\w*|act as|you are (a|an|the)|du bist|ab se tum|tum ab)\b",
        re.I),
    "marker": re.compile(
        r"\b(new|updated|additional)\s+instructions?\b|\binstructions?\s*:|\bsystem\s+(prompt|override|message|mode)\b|\b(developer|debug|maintenance) mode\b",
        re.I),
    "forced": re.compile(
        r"\b(say|state|answer|respond|reply)\s+(only\s+)?(yes|no|that)\b|\bmake something up\b|\bblame\b|\bprint\s+(yay|your|the (prompt|instructions))",
        re.I),
}


def normalize(text):
    """Clean up tricks that hide words: odd Unicode forms, invisible characters,
    and escaped newlines like the literal characters \\n glued to a word."""
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", t)  # invisible characters
    return t.replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")


def hits(text):
    t = normalize(text)
    return [name for name, rx in RULES.items() if rx.search(t)]