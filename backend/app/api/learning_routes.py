from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from backend.app.api.dependencies import CurrentUser, DbSession
from backend.app.models import Concept, ConceptMastery, LearningPath, Lesson
from backend.app.schemas import LessonRequest, LessonResponse
from backend.app.services.learning import create_learning_path, create_lesson, get_owned_lesson, make_recommendations

router = APIRouter(tags=["lessons", "learning", "progress"])


def _lesson_response(lesson: Lesson) -> dict:
    return {"id": lesson.id, "topic": lesson.topic, "depth": lesson.depth, "content": lesson.content}


@router.post("/lessons", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
def generate_lesson(body: LessonRequest, request: Request, user: CurrentUser, session: DbSession):
    try:
        lesson = create_lesson(session, user.id, body, request.app.state.lesson_provider)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Lesson generation failed; retry or use the mock provider") from exc
    return _lesson_response(lesson)


@router.get("/lessons/{lesson_id}", response_model=LessonResponse)
def get_lesson(lesson_id: str, user: CurrentUser, session: DbSession):
    lesson = get_owned_lesson(session, lesson_id, user.id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return _lesson_response(lesson)


@router.post("/learning/paths", status_code=status.HTTP_201_CREATED)
def create_path(target_concept_id: str, user: CurrentUser, session: DbSession):
    try:
        path = create_learning_path(session, user.id, target_concept_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": path.id, "revision": path.revision, "steps": path.steps}


@router.get("/learning/paths")
def list_paths(user: CurrentUser, session: DbSession):
    paths = session.scalars(select(LearningPath).where(LearningPath.user_id == user.id)).all()
    return [{"id": path.id, "revision": path.revision, "steps": path.steps} for path in paths]


@router.get("/progress")
def progress(user: CurrentUser, session: DbSession):
    mastery = session.scalars(select(ConceptMastery).where(ConceptMastery.user_id == user.id)).all()
    by_concept = {state.concept_id: state for state in mastery}
    concepts = session.scalars(select(Concept).order_by(Concept.name)).all()
    return {
        "user_id": user.id,
        "concepts": [
            {
                "concept_id": concept.id,
                "concept": concept.name,
                "status": by_concept[concept.id].status if concept.id in by_concept else "not_assessed",
                "score": by_concept[concept.id].score if concept.id in by_concept else None,
                "evidence_count": by_concept[concept.id].evidence_count if concept.id in by_concept else 0,
            }
            for concept in concepts
        ],
        "note": "Mastery is a configurable summary of recorded assessment evidence, not a definitive measure of knowledge.",
    }


@router.get("/recommendations")
def recommendations(user: CurrentUser, session: DbSession, target_concept_id: str | None = None):
    return {"items": make_recommendations(session, user.id, target_concept_id)}
