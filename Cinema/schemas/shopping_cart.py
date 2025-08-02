from typing import List
from pydantic import BaseModel
from Cinema.schemas.movies import GenreSchema


class MovieInCartSchema(BaseModel):
    id: int
    name: str
    price: Decimal
    year: int
    genres: List[GenreSchema]

    model_config = {"from_attributes": True}


class CartMoviesResponseSchema(BaseModel):
    movies: List[MovieInCartSchema]

    model_config = {"from_attributes": True}


class UserCartSchema(BaseModel):
    user_id: int
