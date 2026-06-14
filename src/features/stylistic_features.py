import re
import pandas as pd


def count_uppercase_letters(text):
    """
    Broji velika slova u tekstu.
    """
    text = str(text)
    return sum(1 for char in text if char.isupper())


def uppercase_ratio(text):
    """
    Računa udeo velikih slova među svim slovima.
    """
    text = str(text)

    letters = [char for char in text if char.isalpha()]

    if len(letters) == 0:
        return 0.0

    uppercase_letters = [char for char in letters if char.isupper()]

    return len(uppercase_letters) / len(letters)


def count_caps_words(text):
    """
    Broji reči napisane potpuno velikim slovima.
    """
    text = str(text)

    words = re.findall(r"\b\w+\b", text)

    return sum(
        1
        for word in words
        if len(word) > 1 and word.isupper()
    )


def count_exclamations(text):
    """
    Broji uzvičnike u tekstu.
    """
    return str(text).count("!")


def count_questions(text):
    """
    Broji upitnike u tekstu.
    """
    return str(text).count("?")

def average_sentence_length(text):
    """
    Prosečan broj reči po rečenici.
    """
    text = str(text)

    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) == 0:
        return 0.0

    word_counts = [
        len(re.findall(r"\b\w+\b", sentence))
        for sentence in sentences
    ]

    return sum(word_counts) / len(word_counts)


def add_stylistic_features(df):
    """
    Dodaje stilističke feature-e u DataFrame.
    Očekuje da postoje kolone: title, text, full_text.
    """
    df = df.copy()

    df["title_uppercase_ratio"] = df["title"].apply(uppercase_ratio)
    df["text_uppercase_ratio"] = df["text"].apply(uppercase_ratio)

    df["title_caps_words"] = df["title"].apply(count_caps_words)
    df["text_caps_words"] = df["text"].apply(count_caps_words)

    df["title_exclamations"] = df["title"].apply(count_exclamations)
    df["text_exclamations"] = df["text"].apply(count_exclamations)

    df["title_questions"] = df["title"].apply(count_questions)
    df["text_questions"] = df["text"].apply(count_questions)

    df["text_avg_sentence_length"] = df["text"].apply(average_sentence_length)

    return df