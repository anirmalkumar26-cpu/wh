from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from backend.app.api.dependencies import CurrentUser, DbSession, require_roles
from backend.app.models import Concept, ConceptRelationship, User
from backend.app.schemas import ConceptRequest, RelationshipRequest
from backend.app.services.graph import GraphError, add_concept, add_relationship, serialize_graph

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge graph"])


@router.get("")
def read_graph(user: CurrentUser, session: DbSession):
    return serialize_graph(session, user.id)


@router.post("/concepts", status_code=status.HTTP_201_CREATED)
def create_concept(
    body: ConceptRequest,
    session: DbSession,
    _: Annotated[User, Depends(require_roles("teacher", "administrator"))],
):
    concept = add_concept(session, body.name, body.description, body.subject, body.difficulty)
    session.commit()
    return {"id": concept.id, "name": concept.name, "description": concept.description}


@router.post("/relationships", status_code=status.HTTP_201_CREATED)
def create_relationship(
    body: RelationshipRequest,
    session: DbSession,
    _: Annotated[User, Depends(require_roles("teacher", "administrator"))],
):
    try:
        relationship = add_relationship(session, body.source_id, body.target_id, body.relation_type)
        session.commit()
    except GraphError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise
    return {
        "id": relationship.id,
        "source_id": relationship.source_id,
        "target_id": relationship.target_id,
        "relation_type": relationship.relation_type,
    }


@router.get("/concepts")
def list_concepts(user: CurrentUser, session: DbSession):
    concepts = session.scalars(select(Concept).order_by(Concept.name)).all()
    return [{"id": item.id, "name": item.name, "description": item.description} for item in concepts]


@router.get("/concepts/{concept_id}/prerequisites")
def list_prerequisites(concept_id: str, user: CurrentUser, session: DbSession):
    if not session.get(Concept, concept_id):
        raise HTTPException(status_code=404, detail="Concept not found")
    links = session.scalars(
        select(ConceptRelationship).where(
            ConceptRelationship.target_id == concept_id,
            ConceptRelationship.relation_type == "prerequisite",
        )
    ).all()
    return {
        "concept_id": concept_id,
        "prerequisites": [
            {"id": concept.id, "name": concept.name}
            for link in links
            if (concept := session.get(Concept, link.source_id)) is not None
        ],
    }
