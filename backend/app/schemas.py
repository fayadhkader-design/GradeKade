from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.normalization import AnswerType, normalize_answer


class StudentCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    external_id: str | None = Field(default=None, max_length=80)

    @field_validator("first_name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Enter a name or demo identifier")
        return value.strip()


class QuestionCreate(BaseModel):
    question_number: int = Field(ge=1, le=200)
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    expected_answer: str = Field(min_length=1, max_length=100)
    answer_type: AnswerType
    auto_grade_enabled: bool = True

    @model_validator(mode="after")
    def valid_question(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("Answer box must be inside the page")
        normalize_answer(self.expected_answer, self.answer_type)
        return self


class QuestionsSave(BaseModel):
    questions: list[QuestionCreate] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_questions(self):
        numbers = [q.question_number for q in self.questions]
        if len(set(numbers)) != len(numbers):
            raise ValueError("Question numbers must be unique")
        return self


class ReviewCreate(BaseModel):
    grade: Literal["correct", "incorrect"]
    recognized_answer: str | None = Field(default=None, max_length=100)
