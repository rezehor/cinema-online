from fastapi import FastAPI

from Cinema.routes import movies, users, profiles, favorites

app = FastAPI(
    title="Online Cinema",
)

api_version_prefix = "/api/v1"

app.include_router(movies.router, prefix=f"{api_version_prefix}/movies", tags=["movies"])
app.include_router(users.router, prefix=f"{api_version_prefix}/users", tags=["users"])
app.include_router(profiles.router, prefix=f"{api_version_prefix}/profiles", tags=["profiles"])
app.include_router(favorites.router, prefix=f"{api_version_prefix}/favorites", tags=["favorites"])