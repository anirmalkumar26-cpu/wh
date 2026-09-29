from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from backend.app.api.dependencies import CurrentUser, DbSession
from backend.app.core.config import settings
from backend.app.models import Lesson, VideoJob
from backend.app.schemas import VideoRequest
from backend.app.services.video_jobs import process_video_job

router = APIRouter(prefix="/videos", tags=["video"])


def _job_response(job: VideoJob) -> dict:
    report = dict(job.report) if job.report else None
    if report is not None:
        report.pop("relative_video", None)
    return {
        "id": job.id,
        "lesson_id": job.lesson_id,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "error": job.error_detail,
        "report": report,
        "created_at": job.created_at,
    }


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
def create_job(body: VideoRequest, background_tasks: BackgroundTasks, request: Request, user: CurrentUser, session: DbSession):
    lesson = session.scalar(select(Lesson).where(Lesson.id == body.lesson_id, Lesson.owner_id == user.id))
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    job = VideoJob(owner_id=user.id, lesson_id=lesson.id)
    session.add(job)
    session.commit()
    session.refresh(job)
    background_tasks.add_task(process_video_job, request.app.state.session_factory, job.id, request.app.state.video_adapter)
    return _job_response(job)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: CurrentUser, session: DbSession):
    job = session.scalar(select(VideoJob).where(VideoJob.id == job_id, VideoJob.owner_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    return _job_response(job)


@router.post("/jobs/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: str, background_tasks: BackgroundTasks, request: Request, user: CurrentUser, session: DbSession):
    job = session.scalar(select(VideoJob).where(VideoJob.id == job_id, VideoJob.owner_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed video jobs can be retried")
    job.status, job.stage, job.progress, job.error_detail, job.report = "queued", "queued", 0, None, None
    session.commit()
    background_tasks.add_task(process_video_job, request.app.state.session_factory, job.id, request.app.state.video_adapter)
    return _job_response(job)


@router.get("/jobs/{job_id}/download")
def download_video(job_id: str, user: CurrentUser, session: DbSession):
    job = session.scalar(select(VideoJob).where(VideoJob.id == job_id, VideoJob.owner_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    relative = (job.report or {}).get("relative_video")
    if job.status != "completed" or not relative:
        raise HTTPException(status_code=409, detail="Video output is not available")
    root = settings.video_jobs_path.resolve()
    output = (root / relative).resolve()
    if root not in output.parents or not output.is_file():
        raise HTTPException(status_code=404, detail="Video output not found")
    return FileResponse(output, media_type="video/mp4", filename="lesson.mp4")
