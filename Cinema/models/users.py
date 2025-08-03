import enum
import secrets
from datetime import timezone, datetime, timedelta
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    Boolean,
    DateTime,
    func,
    ForeignKey,
    Date,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .base import Base
from ..security.passwords import hash_password, verify_password
from ..validators import users


UserFavoriteMovie = Table(
    "user_favorite_movies",
    Base.metadata,
    Column("user_id", ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("user_id", "movie_id", name="unique_user_favorite_movie"),
)


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

    users = relationship("User", back_populates="group")


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    group_id = Column(
        Integer, ForeignKey("usergroup.id", ondelete="CASCADE"), nullable=False
    )

    group = relationship("UserGroup", back_populates="users")
    profile = relationship(
        "UserProfile", back_populates="user", cascade="all, delete-orphan"
    )
    activation_token = relationship(
        "ActivationToken", back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_token = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )
    refresh_token = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    likes = relationship("MovieLike", back_populates="user")

    favorite_movies = relationship(
        "Movie",
        secondary=UserFavoriteMovie,
        back_populates="users_favorite_movies",
    )
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")

    ratings = relationship("MovieRating", back_populates="user")

    cart = relationship("Cart", back_populates="user", uselist=False)

    payments = relationship("Payment", back_populates="user")

    def has_group(self, group_name: UserGroupEnum) -> bool:
        return self.group.name == group_name

    @classmethod
    def create(cls, email: str, raw_password: str, group_id: int) -> "User":
        user = cls(email=email, group_id=group_id)
        user.password = raw_password
        return user

    @property
    def password(self) -> None:
        raise AttributeError(
            "Password is write-only. Use the setter to set the password."
        )

    @password.setter
    def password(self, raw_password: str) -> None:
        users.validate_password_strength(raw_password)
        self.hashed_password = hash_password(raw_password)

    def verify_password(self, raw_password: str) -> bool:
        return verify_password(raw_password, self.hashed_password)


class UserProfile(Base):
    __tablename__ = "userprofile"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    avatar = Column(String, nullable=True)
    gender = Column(Enum(GenderEnum), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    info = Column(String, nullable=True)

    user = relationship("User", back_populates="profile")


class TokenBaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False, unique=True, default=secrets.token_urlsafe)
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=24),
    )
    user_id = Column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, unique=True
    )


class ActivationToken(TokenBaseModel):
    __tablename__ = "activation_token"

    user = relationship("User", back_populates="activation_token")


class PasswordResetToken(TokenBaseModel):
    __tablename__ = "password_reset_token"

    user = relationship("User", back_populates="password_reset_token")


class RefreshToken(TokenBaseModel):
    __tablename__ = "refresh_token"

    user = relationship("User", back_populates="refresh_token")

    @classmethod
    def create(cls, user_id: int, days_valid: int, token: str) -> "RefreshToken":
        expires_at = datetime.now(timezone.utc) + timedelta(days=days_valid)
        return cls(user_id=user_id, token=token, expires_at=expires_at)
