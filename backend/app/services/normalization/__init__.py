"""Exact, bounded numeric parsing. Never evaluate OCR as Python or symbolic code."""

import re
import unicodedata
from fractions import Fraction
from typing import Literal

AnswerType = Literal["integer", "decimal", "fraction"]
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
FRACTION = r"[+-]?\d+/[+-]?\d+"


def parse_answer(raw: str, answer_type: AnswerType) -> Fraction:
    if answer_type not in {"integer", "decimal", "fraction"}:
        raise ValueError("Unsupported answer type")
    if not raw or len(raw) > 100:
        raise ValueError("Empty or oversized answer")
    # Expand single-glyph vulgar fractions before compatibility normalization.
    vulgar = {
        "½": "1/2",
        "⅓": "1/3",
        "⅔": "2/3",
        "¼": "1/4",
        "¾": "3/4",
        "⅕": "1/5",
        "⅖": "2/5",
        "⅗": "3/5",
        "⅘": "4/5",
        "⅙": "1/6",
        "⅚": "5/6",
        "⅛": "1/8",
        "⅜": "3/8",
        "⅝": "5/8",
        "⅞": "7/8",
    }
    stripped = raw.strip()
    sign = ""
    if stripped.startswith(("-", "−", "+")):
        sign, stripped = stripped[0], stripped[1:].strip()
    if stripped in vulgar:
        stripped = sign + vulgar[stripped]
    else:
        if any(glyph in raw for glyph in vulgar):
            raise ValueError("Mixed or ambiguous fractions are unsupported")
        stripped = raw.strip()
    if any(unicodedata.category(char) == "No" for char in stripped):
        raise ValueError("Ambiguous numeric glyph")
    text = unicodedata.normalize("NFKC", stripped).replace("−", "-").replace("–", "-").replace("⁄", "/")
    # Only remove harmless spacing around a sign/slash; '1 2' must not become '12'.
    text = re.sub(r"^([+-])\s+", r"\1", text)
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\\(?:d?frac)\{([+-]?\d+)\}\{([+-]?\d+)\}", r"\1/\2", text)
    text = text.removeprefix("$").removesuffix("$").strip()
    if not re.fullmatch(NUMBER, text) and not (answer_type == "fraction" and re.fullmatch(FRACTION, text)):
        raise ValueError("Not a supported numeric answer")
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError):
        raise ValueError("Invalid numeric answer") from None
    if answer_type == "integer" and value.denominator != 1:
        raise ValueError("Expected an integer")
    return value


def normalize_answer(raw: str, answer_type: AnswerType) -> str:
    value = parse_answer(raw, answer_type)
    if value.denominator == 1:
        return str(value.numerator)
    if answer_type == "fraction":
        return f"{value.numerator}/{value.denominator}"
    # Decimal input is finite; retain exact decimal digits, without float rounding.
    from decimal import Decimal, localcontext

    with localcontext() as context:
        context.prec = 220
        return format(Decimal(value.numerator) / Decimal(value.denominator), "f").rstrip("0").rstrip(".")


def answers_equivalent(student_answer: str, expected_answer: str, answer_type: AnswerType) -> bool:
    try:
        return parse_answer(student_answer, answer_type) == parse_answer(expected_answer, answer_type)
    except ValueError:
        return False
