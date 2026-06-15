import re

def clean_leakage_patterns(text: str) -> str:
    text = str(text)

    patterns = [
        r"https?://\S+|www\.\S+",          # URL-ovi
        r"<[^>]+>",                        # HTML tagovi
        r"&[a-zA-Z]+;|&#\d+;",             # HTML entities

        r"\bfoto\s*:\s*[^.!\n]*",          # Foto:
        r"\bizvor\s*:\s*[^.!\n]*",         # Izvor:
        r"\bprenosi\s+[^.!\n]*",           # Prenosi ...
        r"\bprenela\s+[^.!\n]*",           # Prenela ...
        r"\bautor\s*:\s*[^.!\n]*",         # Autor:
        r"\bpiše\s*:\s*[^.!\n]*",          # Piše:
        r"\brubrika\s*:\s*[^.!\n]*",       # Rubrika:
        r"\btagovi\s*:\s*[^.!\n]*",        # Tagovi:
        r"\btag\s*:\s*[^.!\n]*",           # Tag:
    ]

    for pattern in patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()
    return text

def make_fingerprint(text: str, n: int = 200) -> str:
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    return normalized[:n]