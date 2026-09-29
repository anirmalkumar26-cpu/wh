from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.ai.providers import LessonProvider
from backend.app.models import Concept, ConceptMastery, LearningPath, Lesson
from backend.app.schemas import LessonRequest
from backend.app.services.graph import add_concept, add_relationship, prerequisite_order


def create_lesson(session: Session, user_id: str, request: LessonRequest, provider: LessonProvider) -> Lesson:
    topic = request.topic or (request.text or "").splitlines()[0][:300]
    content = provider.generate_lesson(topic, request.text, request.depth)
    lesson = Lesson(owner_id=user_id, topic=topic, source_text=request.text, depth=request.depth, content=content.model_dump())
    session.add(lesson)
    session.flush()

    target = add_concept(session, topic, content.overview, difficulty=request.depth)
    prerequisite_concepts = [add_concept(session, name) for name in content.prerequisites]
    for prerequisite in prerequisite_concepts:
        add_relationship(session, prerequisite.id, target.id, "prerequisite")
    session.commit()
    session.refresh(lesson)
    return lesson


def get_owned_lesson(session: Session, lesson_id: str, user_id: str) -> Lesson | None:
    return session.scalar(select(Lesson).where(Lesson.id == lesson_id, Lesson.owner_id == user_id))


def create_learning_path(session: Session, user_id: str, target_concept_id: str) -> LearningPath:
    concepts = prerequisite_order(session, target_concept_id)
    if not concepts:
        raise ValueError("Target concept was not found")
    existing_mastery = {
        item.concept_id: item
        for item in session.scalars(select(ConceptMastery).where(ConceptMastery.user_id == user_id)).all()
    }
    steps = []
    for concept in concepts:
        mastery = existing_mastery.get(concept.id)
        status = mastery.status if mastery else "not_assessed"
        steps.append(
            {
                "concept_id": concept.id,
                "concept": concept.name,
                "status": "completed" if status == "mastered" else "pending",
                "mastery_status": status,
            }
        )
    path = LearningPath(user_id=user_id, target_concept_id=target_concept_id, steps=steps)
    session.add(path)
    session.commit()
    session.refresh(path)
    return path


def make_recommendations(session: Session, user_id: str, target_concept_id: str | None = None) -> list[dict]:
    if target_concept_id:
        concepts = prerequisite_order(session, target_concept_id)
    else:
        concepts = session.scalars(select(Concept).order_by(Concept.name)).all()
    mastery = {
        item.concept_id: item
        for item in session.scalars(select(ConceptMastery).where(ConceptMastery.user_id == user_id)).all()
    }
    for concept in concepts:
        state = mastery.get(concept.id)
        if state is None or state.status not in {"proficient", "mastered"}:
            evidence_count = state.evidence_count if state else 0
            return [
                {
                    "concept_id": concept.id,
                    "concept": concept.name,
                    "kind": "study_concept",
                    "reason": "This concept is an unmet prerequisite or has not yet been assessed.",
                    "evidence": {"mastery_status": state.status if state else "not_assessed", "evidence_count": evidence_count},
                }
            ]
    if concepts:
        concept = concepts[-1]
        return [
            {
                "concept_id": concept.id,
                "concept": concept.name,
                "kind": "practice_or_advance",
                "reason": "Recorded evidence shows proficiency in the prerequisite sequence.",
                "evidence": {"mastery_status": mastery[concept.id].status},
            }
        ]
    return []
