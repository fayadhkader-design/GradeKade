"""Exact, bounded numeric parsing. Never evaluate OCR as Python or symbolic code."""

import re
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
    text = raw.strip().replace("−", "-").replace("–", "-")
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
