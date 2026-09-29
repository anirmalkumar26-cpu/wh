import logging

from sqlalchemy.orm import sessionmaker

from backend.app.models import Lesson, VideoJob
from backend.app.video.adapter import VideoAdapter

logger = logging.getLogger(__name__)


def process_video_job(factory: sessionmaker, job_id: str, adapter: VideoAdapter) -> None:
    with factory() as session:
        job = session.get(VideoJob, job_id)
        if not job:
            return
        lesson = session.get(Lesson, job.lesson_id)
        if not lesson:
            job.status = "failed"
            job.stage = "failed"
            job.error_detail = "The lesson for this video job is unavailable."
            session.commit()
            return
        job.status = "running"
        job.stage = "preparing"
        job.progress = 10
        session.commit()
        lesson_data = {"topic": lesson.topic, "depth": lesson.depth, "content": lesson.content}

    try:
        report = adapter.generate(lesson_data, job_id)
    except Exception:
        logger.exception("Video job %s failed", job_id)
        with factory() as session:
            job = session.get(VideoJob, job_id)
            if job:
                job.status = "failed"
                job.stage = "failed"
                job.progress = 100
                job.error_detail = "Video rendering failed. Retry the job or check the server diagnostic logs."
                job.report = {"status": "failed", "diagnostic": "The configured video adapter failed."}
                session.commit()
        return

    with factory() as session:
        job = session.get(VideoJob, job_id)
        if job:
            job.status = "completed"
            job.stage = "complete"
            job.progress = 100
            job.report = report
            session.commit()
