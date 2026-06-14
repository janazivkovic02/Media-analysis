from cyrtranslit import to_latin

def convert_to_latin(text):
    if text is None:
        return ""

    return to_latin(str(text))