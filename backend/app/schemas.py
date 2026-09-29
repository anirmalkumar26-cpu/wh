from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


Role = Literal["student", "teacher", "administrator"]
Depth = Literal["beginner", "intermediate", "advanced", "research"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def password_has_variety(cls, value: str) -> str:
        if not any(char.islower() for char in value) or not any(char.isupper() for char in value) or not any(
            char.isdigit() for char in value
        ):
            raise ValueError("Password must include lowercase, uppercase, and numeric characters")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    role: Role
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class LessonRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=300)
    text: str | None = Field(default=None, max_length=12000)
    depth: Depth = "intermediate"

    @field_validator("topic", "text")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def require_input(self):
        if not self.topic and not self.text:
            raise ValueError("Provide a topic or text")
        if self.topic and self.text:
            raise ValueError("Provide a topic or text, not both")
        return self


class LessonContent(BaseModel):
    overview: str = Field(min_length=1, max_length=8000)
    objectives: list[str] = Field(min_length=1, max_length=12)
    prerequisites: list[str] = Field(default_factory=list, max_length=30)
    sections: list["LessonSection"] = Field(min_length=1, max_length=20)
    key_terms: list[str] = Field(default_factory=list, max_length=40)
    common_mistakes: list[str] = Field(default_factory=list, max_length=20)
    review_questions: list[str] = Field(default_factory=list, max_length=20)
    recap: str = Field(min_length=1, max_length=8000)

    @field_validator("objectives", "prerequisites", "key_terms", "common_mistakes", "review_questions")
    @classmethod
    def validate_lesson_text_lists(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 1000 for value in values):
            raise ValueError("Lesson text items must be non-empty and no longer than 1000 characters")
        return values


class LessonSection(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=8000)
    examples: list[str] = Field(default_factory=list, max_length=10)


class LessonResponse(BaseModel):
    id: str
    topic: str
    depth: Depth
    content: LessonContent


class ConceptRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)
    subject: str = Field(default="General", max_length=200)
    difficulty: Depth = "intermediate"


class RelationshipRequest(BaseModel):
    source_id: str
    target_id: str
    relation_type: Literal["prerequisite", "part_of", "related_to", "applied_in", "extends", "contrasts_with"]


class AssessmentRequest(BaseModel):
    lesson_id: str
    question_count: int = Field(default=3, ge=1, le=3)


class AnswerSubmission(BaseModel):
    answers: dict[str, str] = Field(min_length=1)

    @field_validator("answers")
    @classmethod
    def validate_answer_lengths(cls, answers: dict[str, str]) -> dict[str, str]:
        if any(len(answer) > 2000 for answer in answers.values()):
            raise ValueError("Answers must be no longer than 2000 characters")
        return answers


class VideoRequest(BaseModel):
    lesson_id: str


class AdminUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Literal["teacher", "administrator"]

    @field_validator("password")
    @classmethod
    def password_has_variety(cls, value: str) -> str:
        if not any(char.islower() for char in value) or not any(char.isupper() for char in value) or not any(
            char.isdigit() for char in value
        ):
            raise ValueError("Password must include lowercase, uppercase, and numeric characters")
        return value
