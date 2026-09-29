from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Concept, ConceptMastery, ConceptRelationship


class GraphError(Exception):
    pass


def add_concept(session: Session, name: str, description: str = "", subject: str = "General", difficulty: str = "intermediate") -> Concept:
    normalized = name.strip()
    existing = session.scalar(select(Concept).where(Concept.name == normalized))
    if existing:
        return existing
    concept = Concept(name=normalized, description=description, subject=subject, difficulty=difficulty)
    session.add(concept)
    session.flush()
    return concept


def _reachable(session: Session, start_id: str, sought_id: str) -> bool:
    edges = session.scalars(select(ConceptRelationship)).all()
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        if edge.relation_type == "prerequisite":
            outgoing.setdefault(edge.source_id, []).append(edge.target_id)
    pending = [start_id]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == sought_id:
            return True
        if current not in visited:
            visited.add(current)
            pending.extend(outgoing.get(current, []))
    return False


def add_relationship(session: Session, source_id: str, target_id: str, relation_type: str) -> ConceptRelationship:
    if source_id == target_id:
        raise GraphError("A concept cannot be related to itself")
    if not session.get(Concept, source_id) or not session.get(Concept, target_id):
        raise GraphError("Both concepts must exist before creating a relationship")
    if relation_type == "prerequisite" and _reachable(session, target_id, source_id):
        raise GraphError("Prerequisite relationship would create a cycle")
    existing = session.scalar(
        select(ConceptRelationship).where(
            ConceptRelationship.source_id == source_id,
            ConceptRelationship.target_id == target_id,
            ConceptRelationship.relation_type == relation_type,
        )
    )
    if existing:
        return existing
    relationship = ConceptRelationship(source_id=source_id, target_id=target_id, relation_type=relation_type)
    session.add(relationship)
    session.flush()
    return relationship


def serialize_graph(session: Session, user_id: str | None = None) -> dict:
    concepts = session.scalars(select(Concept).order_by(Concept.name)).all()
    relationships = session.scalars(select(ConceptRelationship)).all()
    mastery = {}
    if user_id:
        mastery = {
            item.concept_id: {"status": item.status, "score": item.score, "evidence_count": item.evidence_count}
            for item in session.scalars(select(ConceptMastery).where(ConceptMastery.user_id == user_id)).all()
        }
    return {
        "nodes": [
            {
                "id": concept.id,
                "name": concept.name,
                "description": concept.description,
                "subject": concept.subject,
                "difficulty": concept.difficulty,
                "mastery": mastery.get(concept.id),
            }
            for concept in concepts
        ],
        "edges": [
            {"id": edge.id, "source_id": edge.source_id, "target_id": edge.target_id, "relation_type": edge.relation_type}
            for edge in relationships
        ],
    }


def prerequisite_order(session: Session, target_id: str) -> list[Concept]:
    edges = session.scalars(
        select(ConceptRelationship).where(ConceptRelationship.relation_type == "prerequisite")
    ).all()
    incoming: dict[str, list[str]] = {}
    for edge in edges:
        incoming.setdefault(edge.target_id, []).append(edge.source_id)
    ordered: list[str] = []
    visited: set[str] = set()

    def visit(concept_id: str) -> None:
        if concept_id in visited:
            return
        visited.add(concept_id)
        for prerequisite_id in incoming.get(concept_id, []):
            visit(prerequisite_id)
        ordered.append(concept_id)

    visit(target_id)
    concepts = {concept.id: concept for concept in session.scalars(select(Concept).where(Concept.id.in_(ordered))).all()}
    return [concepts[item] for item in ordered if item in concepts]
