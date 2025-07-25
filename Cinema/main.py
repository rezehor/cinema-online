from fastapi import FastAPI

from routes import movies, users

app = FastAPI(
    title="Online Cinema",
)

api_version_prefix = "/api/v1"

app.include_router(movies.router, prefix=f"{api_version_prefix}/movies", tags=["movies"])
app.include_router(users.router, prefix=f"{api_version_prefix}/users", tags=["users"])