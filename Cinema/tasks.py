import logging
from datetime import datetime, timezone
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import delete, create_engine
from sqlalchemy.orm import sessionmaker
from Cinema.config.settings import settings
from Cinema.models import ActivationToken
import pathlib


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DATABASE_URL_SYNC = f"sqlite:///{BASE_DIR / 'online_cinema.db'}"
engine = create_engine(DATABASE_URL_SYNC, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)

celery_app = Celery(
    "tasks",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
)


@celery_app.task
def delete_expired_tokens():
    try:
        with SessionLocal() as session:
            session.execute(
                delete(ActivationToken).where(
                    ActivationToken.expires_at < datetime.now(timezone.utc)
                )
            )
            session.commit()
            logger.info("Expired tokens deleted.")
    except Exception as e:
        logger.error(f"Failed to delete expired tokens: {e}", exc_info=True)
        raise


celery_app.conf.beat_schedule = {
    "delete-expired-tokens-every-ten-minutes": {
        "task": "Cinema.tasks.delete_expired_tokens",
        "schedule": crontab(minute="*/10"),
    },
}
