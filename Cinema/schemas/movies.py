from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from Cinema.models.movies import LikeStatusEnum


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class StarSchema(BaseModel):
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


class MovieBaseSchema(BaseModel):
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


class MovieDetailSchema(MovieBaseSchema):
    id: int
    uuid: str
    certification: CertificationSchema
    genres: List[GenreSchema]
    stars: List[StarSchema]
    directors: List[DirectorSchema]
    likes: int
    dislikes: int

    model_config = {"from_attributes": True}


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: float
    description: str

    model_config = {"from_attributes": True}


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: Optional[int]
    total_items: Optional[int]

    model_config = {"from_attributes": True}


class MovieCreateSchema(MovieBaseSchema):
    certification: str
    genres: List[str]
    stars: List[str]
    directors: List[str]

    model_config = {"from_attributes": True}

    @field_validator("genres", "stars", "directors", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: List[str]) -> List[str]:
        return [item.title() for item in value]


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = None
    time: Optional[int] = None
    imdb: Optional[float] = None
    votes: Optional[int] = None
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class MovieLikeRequestSchema(BaseModel):
    like_status: LikeStatusEnum


class MovieLikeResponseSchema(BaseModel):
    likes: int
    dislikes: int
    user_status: Optional[LikeStatusEnum] = None
