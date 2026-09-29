from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Assessment, AssessmentAttempt, Concept, ConceptMastery, Lesson


def create_assessment(session: Session, user_id: str, lesson: Lesson, count: int) -> Assessment:
    topic = lesson.topic
    if "avl" in topic.casefold() and "rotation" in topic.casefold():
        questions = [
            {
            "id": "q1",
            "concept_name": topic,
            "type": "multiple_choice",
            "text": "Which operation repairs an AVL left-left imbalance at the root?",
            "options": [
                {"id": "A", "text": "A left rotation"},
                {"id": "B", "text": "A right rotation"},
                {"id": "C", "text": "A full tree rebuild"},
                {"id": "D", "text": "No operation"},
            ],
            "correct_answer": "B",
            "explanation": "A right rotation promotes the left child and repairs a left-left imbalance.",
            },
            {
                "id": "q2",
                "concept_name": topic,
                "type": "multiple_choice",
                "text": "In a right rotation, which node is promoted?",
                "options": [
                    {"id": "A", "text": "The root's right child"},
                    {"id": "B", "text": "The unbalanced node's left child"},
                    {"id": "C", "text": "The smallest leaf in the tree"},
                    {"id": "D", "text": "A newly created node"},
                ],
                "correct_answer": "B",
                "explanation": "The left child becomes the subtree root after a right rotation.",
            },
            {
                "id": "q3",
                "concept_name": topic,
                "type": "multiple_choice",
                "text": "What is the purpose of the AVL right rotation in this example?",
                "options": [
                    {"id": "A", "text": "To change the in-order key ordering"},
                    {"id": "B", "text": "To reduce the left-left height imbalance while preserving BST order"},
                    {"id": "C", "text": "To remove every leaf node"},
                    {"id": "D", "text": "To convert the tree into a linked list"},
                ],
                "correct_answer": "B",
                "explanation": "The rotation restores balance without changing the binary-search ordering.",
            },
        ]
    else:
        questions = [
            {
                "id": "q1",
                "concept_name": topic,
                "type": "multiple_choice",
                "text": f"Which approach best supports reasoning about {topic}?",
                "options": [
                    {"id": "A", "text": "Memorize a phrase without checking when it applies"},
                    {"id": "B", "text": f"Identify prerequisites, apply the core rules of {topic}, and check the result"},
                    {"id": "C", "text": "Ignore examples and assumptions"},
                    {"id": "D", "text": "Assume every case has the same outcome"},
                ],
                "correct_answer": "B",
                "explanation": "Reasoning from prerequisites and checking outcomes provides evidence of understanding.",
            },
            {
                "id": "q2",
                "concept_name": topic,
                "type": "multiple_choice",
                "text": f"Before applying {topic}, what should a learner check?",
                "options": [
                    {"id": "A", "text": "Whether the example is visually attractive"},
                    {"id": "B", "text": "The assumptions and conditions under which the concept applies"},
                    {"id": "C", "text": "Whether all examples use identical numbers"},
                    {"id": "D", "text": "Nothing; conditions never matter"},
                ],
                "correct_answer": "B",
                "explanation": "A concept's preconditions determine when its rules are applicable.",
            },
            {
                "id": "q3",
                "concept_name": topic,
                "type": "multiple_choice",
                "text": f"How can a learner check their reasoning about {topic}?",
                "options": [
                    {"id": "A", "text": "Repeat the conclusion without evidence"},
                    {"id": "B", "text": "Work through an example and verify the result against the rules"},
                    {"id": "C", "text": "Skip intermediate steps"},
                    {"id": "D", "text": "Assume a single example proves every case"},
                ],
                "correct_answer": "B",
                "explanation": "Worked examples and rule-based checks make reasoning inspectable.",
            },
        ]
    questions = questions[:count]
    assessment = Assessment(owner_id=user_id, lesson_id=lesson.id, questions=questions)
    session.add(assessment)
    session.commit()
    session.refresh(assessment)
    return assessment


def submit_answers(session: Session, user_id: str, assessment: Assessment, answers: dict[str, str]) -> dict:
    question_by_id = {question["id"]: question for question in assessment.questions}
    unknown = set(answers) - set(question_by_id)
    if unknown:
        raise ValueError(f"Unknown question IDs: {', '.join(sorted(unknown))}")
    if set(answers) != set(question_by_id):
        raise ValueError("An answer is required for every question")
    evidence = []
    for question in assessment.questions:
        supplied = answers[question["id"]].strip()
        correct = supplied.casefold() == question["correct_answer"].casefold()
        evidence.append(
            {
                "question_id": question["id"],
                "concept_name": question["concept_name"],
                "answer": supplied,
                "correct": correct,
                "explanation": question["explanation"],
            }
        )
    score = float(sum(item["correct"] for item in evidence))
    maximum = float(len(evidence))
    attempt = AssessmentAttempt(
        assessment_id=assessment.id,
        user_id=user_id,
        score=score,
        max_score=maximum,
        evidence=evidence,
    )
    session.add(attempt)

    concept = session.scalar(select(Concept).where(Concept.name == evidence[0]["concept_name"]))
    if concept:
        state = session.scalar(
            select(ConceptMastery).where(
                ConceptMastery.user_id == user_id,
                ConceptMastery.concept_id == concept.id,
            )
        )
        if not state:
            state = ConceptMastery(user_id=user_id, concept_id=concept.id, evidence=[], score=0.0, evidence_count=0)
            session.add(state)
            session.flush()
        state.evidence = [
            *state.evidence,
            *[{"correct": item["correct"], "assessment_id": assessment.id} for item in evidence],
        ]
        state.evidence_count += len(evidence)
        state.score = sum(bool(item["correct"]) for item in state.evidence) / state.evidence_count
        if state.evidence_count < 3:
            state.status = "insufficient_evidence"
        elif state.score >= 0.85:
            state.status = "mastered"
        elif state.score >= 0.7:
            state.status = "proficient"
        elif state.score >= 0.4:
            state.status = "developing"
        else:
            state.status = "learning"
    session.commit()
    session.refresh(attempt)
    return {
        "attempt_id": attempt.id,
        "score": score,
        "max_score": maximum,
        "percentage": round(score / maximum * 100, 2),
        "feedback": [
            {
                "question_id": item["question_id"],
                "correct": item["correct"],
                "explanation": item["explanation"],
                "classification": "possible_knowledge_gap" if not item["correct"] else "correct",
            }
            for item in evidence
        ],
    }
