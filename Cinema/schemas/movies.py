from pydantic import BaseModel


class GenreSchema(BaseModel):
    id: int
    name: str


class StarsSchema(BaseModel):
    id: int
    name: str


class DirectorSchema(BaseModel):
    id: int
    name: str
