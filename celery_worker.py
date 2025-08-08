from datetime import datetime, timezone

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select, delete

import models
from database import SessionLocal

celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

celery_app.conf.beat_schedule = {
    "delete-expired-activation-tokens-every-day": {
        "task": "celery_worker.delete_expired_act_tokens",
        "schedule": crontab(hour=10, minute=30)
    }
}


@celery_app.task
async def delete_expired_act_tokens():
    print("start deleting all old tokens")
    async with SessionLocal() as db:
        try:
            current_time = datetime.now(timezone.utc)
            all_act_tokens = await db.execute(delete(models.ActivationToken).where(models.ActivationToken.expires_at < current_time))
            await db.commit()
            print(f"all old tokens was successfully deleted")
        except Exception as e:
            await db.rollback()
            print(f"An error occcured {e}")
