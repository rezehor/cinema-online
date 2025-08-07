import logging
from datetime import datetime, timezone
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import delete
from config.settings import settings
from database import SyncSessionLocal
from models import ActivationToken


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


celery_app = Celery(
    "tasks",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
)


@celery_app.task
def delete_expired_tokens():
    try:
        with SyncSessionLocal() as session:
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
        "task": "tasks.delete_expired_tokens",
        "schedule": crontab(minute="*/10"),
    },
}
