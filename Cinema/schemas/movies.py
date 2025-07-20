from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class StarsSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class DirectorSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class CertificationSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class MoviesBaseSchema(BaseModel):
    uuid: str
    name: str = Field(max_length=255)
    year: int = Field(gt=1880)
    time: int = Field(gt=0, lt=300)
    imdb: float = Field(ge=0, le=10)
    votes: int = Field(ge=0)
    meta_score: float = Field(ge=0, le=100)
    gross: float = Field(ge=0)
    description: str = Field(min_length=1, max_length=1000)
    price: Decimal = Field(ge=0)

    model_config = {"from_attributes": True}

    @field_validator("year")
    @classmethod
    def validate_year(cls, value):
        current_year = datetime.now().year
        if value > current_year + 1:
            raise ValueError(f"The year in 'year' cannot be greater than {current_year + 1}.")
        return value
