import enum

from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.orm import relationship

from Cinema.database import Base


class UserGroupEnum(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class GenderEnum(str, enum.Enum):
    MAN = "man"
    WOMAN = "woman"


class UserGroup(Base):
    __tablename__ = "usergroup"

    id = Column(Integer, primary_key=True)
    name = Column(Enum(UserGroupEnum), nullable=False, unique=True)
    users: list["User"] = relationship("User", back_populates="group")
