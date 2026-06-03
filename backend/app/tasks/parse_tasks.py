import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.upload import UploadBatch
from app.services.parser_service import parse_xlsx, parse_txt
from app.tasks import celery_app
from app.utils.s3 import download_file

engine = create_engine(settings.DATABASE_URL_SYNC)


@celery_app.task(name="app.tasks.parse_tasks.parse_upload_batch", bind=True, max_retries=2)
def parse_upload_batch(self, batch_id: str):
    batch_uuid = uuid.UUID(batch_id)

    with Session(engine) as db:
        batch = db.execute(select(UploadBatch).where(UploadBatch.id == batch_uuid)).scalar_one_or_none()
        if not batch:
            return {"error": "Batch not found"}

        batch.status = "parsing"
        db.commit()

        all_warnings = []

        try:
            # Parse xlsx
            if batch.xlsx_s3_key:
                xlsx_data = download_file(batch.xlsx_s3_key)
                row_count, xlsx_warnings = parse_xlsx(
                    db, xlsx_data, batch.workspace_id, batch.id, batch.week_date,
                )
                batch.row_count = row_count
                all_warnings.extend(xlsx_warnings)
                db.commit()

            # Parse txt
            if batch.txt_s3_key:
                txt_data = download_file(batch.txt_s3_key)
                txt_warnings = parse_txt(
                    db, txt_data, batch.workspace_id, batch.id, batch.week_date,
                )
                all_warnings.extend(txt_warnings)
                db.commit()

            # Trigger price backfill for new tickers
            from app.tasks.price_tasks import backfill_new_tickers
            backfill_new_tickers.delay()

            batch.duplicate_count = sum(1 for w in all_warnings if "Duplicate" in w)
            batch.warning_count = len(all_warnings)
            batch.status = "complete"
            batch.error_detail = "\n".join(all_warnings) if all_warnings else None
            db.commit()

            return {"status": "complete", "rows": batch.row_count, "warnings": all_warnings}

        except Exception as e:
            batch.status = "error"
            batch.error_detail = str(e)
            db.commit()
            raise self.retry(exc=e, countdown=30)
