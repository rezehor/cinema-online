import enum

from sqlalchemy import Column, Integer, String, Enum, Boolean, DateTime, func, ForeignKey
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


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
    group_id = Column(Integer, ForeignKey("usergroup.id", ondelete="CASCADE"), nullable=False)

    group = relationship("UserGroup", back_populates="user")
    profile = relationship("UserProfile", back_populates="user", cascade="all, delete-orphan")
    activation_token = relationship("ActivationToken", back_populates="user", cascade="all, delete-orphan")
    password_reset_token = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    refresh_token = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")