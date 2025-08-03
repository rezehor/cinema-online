from datetime import date
from typing import Optional, Any, Union
from typing_extensions import Annotated

from fastapi import UploadFile, Form, File
from pydantic import BaseModel, field_validator, HttpUrl, PrivateAttr

from Cinema.models import GenderEnum
from Cinema.validation.profile import (
    validate_name,
    validate_gender,
    validate_birth_date,
)


class ProfileCreateSchema(BaseModel):
    first_name: Annotated[str, Form(...)]
    last_name: Annotated[str, Form(...)]
    gender: Annotated[Optional[GenderEnum], Form(None)] = None
    date_of_birth: Annotated[Optional[date], Form(None)] = None
    info: Annotated[Optional[str], Form(None)] = None
    avatar: Annotated[Optional[UploadFile], File(None)] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_fields(cls, value: str) -> str:
        validate_name(value)
        return value.strip().lower()

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value: Optional[GenderEnum]) -> Optional[GenderEnum]:
        if value is not None:
            validate_gender(str(value))
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth_field(cls, value: Optional[date]) -> Optional[date]:
        if value:
            validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info_field(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("Info field cannot be empty or contain only spaces.")
            return cleaned
        return value


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None
    avatar: Optional[HttpUrl] = None


class ProfileUpdateSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            validate_name(value)
            return value.strip().lower()
        return value

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value: Optional[GenderEnum]) -> Optional[GenderEnum]:
        if value is not None:
            validate_gender(str(value))
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth_field(cls, value: Optional[date]) -> Optional[date]:
        if value:
            validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info_field(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("Info field cannot be empty or contain only spaces.")
            return cleaned
        return value
