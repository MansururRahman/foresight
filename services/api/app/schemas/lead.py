from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import LeadTeamSize


class LeadCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: str = Field(min_length=1, max_length=160)
    role: str = Field(min_length=1, max_length=120)
    team_size: LeadTeamSize
    story: str | None = Field(default=None, max_length=2000)
    source: str | None = Field(default=None, max_length=100)
    # Honeypot: hidden in the form, so only bots fill it in.
    website: str = Field(default="", max_length=500)

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("story", "source")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        return value or None


class LeadAccepted(BaseModel):
    status: Literal["received"] = "received"
