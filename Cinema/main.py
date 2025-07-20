from fastapi import FastAPI

from Cinema.routes import movies

app = FastAPI(
    title="Online Cinema",
)

api_version_prefix = "/api/v1"

app.include_router(movies.router, prefix=f"{api_version_prefix}/movies", tags=["movies"])
