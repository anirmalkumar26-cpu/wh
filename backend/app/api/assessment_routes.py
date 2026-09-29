from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from backend.app.api.dependencies import CurrentUser, DbSession
from backend.app.models import Assessment, AssessmentAttempt
from backend.app.schemas import AnswerSubmission, AssessmentRequest
from backend.app.services.assessment import create_assessment, submit_answers
from backend.app.services.learning import get_owned_lesson

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _public_assessment(assessment: Assessment) -> dict:
    questions = [
        {key: value for key, value in question.items() if key != "correct_answer"}
        for question in assessment.questions
    ]
    return {"id": assessment.id, "lesson_id": assessment.lesson_id, "questions": questions}


@router.post("", status_code=status.HTTP_201_CREATED)
def generate_assessment(body: AssessmentRequest, user: CurrentUser, session: DbSession):
    lesson = get_owned_lesson(session, body.lesson_id, user.id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return _public_assessment(create_assessment(session, user.id, lesson, body.question_count))


@router.post("/{assessment_id}/submit")
def submit_assessment(assessment_id: str, body: AnswerSubmission, user: CurrentUser, session: DbSession):
    assessment = session.scalar(
        select(Assessment).where(Assessment.id == assessment_id, Assessment.owner_id == user.id)
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    try:
        return submit_answers(session, user.id, assessment, body.answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{assessment_id}/attempts")
def list_attempts(assessment_id: str, user: CurrentUser, session: DbSession):
    assessment = session.scalar(
        select(Assessment).where(Assessment.id == assessment_id, Assessment.owner_id == user.id)
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    attempts = session.scalars(
        select(AssessmentAttempt).where(AssessmentAttempt.assessment_id == assessment_id).order_by(AssessmentAttempt.created_at)
    ).all()
    return [
        {"id": item.id, "score": item.score, "max_score": item.max_score, "created_at": item.created_at}
        for item in attempts
    ]
