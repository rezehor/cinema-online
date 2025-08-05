from datetime import date, datetime
from typing import Optional
from typing_extensions import Annotated

from fastapi import UploadFile, Form, File
from pydantic import BaseModel, field_validator, HttpUrl, model_validator

from models import GenderEnum
from validation.profile import (
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

    @model_validator(mode="before")
    @classmethod
    def clean_form_fields(cls, values):
        for key in ("info", "first_name", "last_name"):
            if key in values and isinstance(values[key], str):
                values[key] = values[key].strip()

        gender = values.get("gender")
        if gender:
            try:
                values["gender"] = GenderEnum(gender.strip().lower())
            except ValueError:
                raise ValueError("Gender must be 'man' or 'woman'.")

        dob = values.get("date_of_birth")
        if dob and isinstance(dob, str):
            try:
                values["date_of_birth"] = datetime.strptime(dob, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Invalid date format for date_of_birth. Use YYYY-MM-DD.")

        return values


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

    @model_validator(mode="before")
    @classmethod
    def preprocess_fields(cls, data: dict) -> dict:
        if gender := data.get("gender"):
            gender = gender.strip().lower()
            if gender:
                try:
                    data["gender"] = GenderEnum(gender)
                except ValueError:
                    raise ValueError("Gender must be 'man' or 'woman'.")
            else:
                data["gender"] = None

        if dob := data.get("date_of_birth"):
            dob = dob.strip()
            if dob:
                try:
                    data["date_of_birth"] = datetime.strptime(dob, "%Y-%m-%d").date()
                except ValueError:
                    raise ValueError("Invalid date format. Use YYYY-MM-DD.")
            else:
                data["date_of_birth"] = None

        if info := data.get("info"):
            cleaned = info.strip()
            if not cleaned:
                raise ValueError("Info field cannot be empty or contain only spaces.")
            data["info"] = cleaned

        if fn := data.get("first_name"):
            data["first_name"] = fn.strip().lower()

        if ln := data.get("last_name"):
            data["last_name"] = ln.strip().lower()

        return data

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_fields(cls, value: Optional[str]) -> Optional[str]:
        if value:
            validate_name(value)
        return value

    @field_validator("gender")
    @classmethod
    def validate_gender_field(cls, value: Optional[GenderEnum]) -> Optional[GenderEnum]:
        if value is not None:
            validate_gender(value.value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth_field(cls, value: Optional[date]) -> Optional[date]:
        if value:
            validate_birth_date(value)
        return value
