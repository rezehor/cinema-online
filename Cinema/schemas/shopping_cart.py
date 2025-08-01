from typing import List
from pydantic import BaseModel
from Cinema.schemas.movies import GenreSchema


class MovieInCartSchema(BaseModel):
    id: int
    name: str
    price: float
    year: int
    genres: List[GenreSchema]

    model_config = {"from_attributes": True}



