# Knowledge graph

Concept definitions are shared platform records. A prerequisite edge is directed
from the required concept to the concept that depends on it. Other relation
types (`part_of`, `related_to`, `applied_in`, `extends`, `contrasts_with`) do not
participate in prerequisite ordering.

The graph service:

- stores concepts and typed relationships in relational tables;
- rejects self-edges, missing endpoints, and prerequisite cycles;
- traverses prerequisite chains in prerequisite-first order;
- maps user-specific `concept_mastery` onto graph nodes without sharing
  assessment evidence across students;
- returns graph nodes and edges at `/api/v1/knowledge-graph`;
- creates inferred prerequisite concepts when a validated lesson is stored.

Only teachers and administrators can directly mutate shared concepts and
relationships. Student lesson requests may add concepts/prerequisite links
through the lesson service. The current implementation does not yet provide
teacher review/approval of inferred graph definitions or source citations.

Learning paths snapshot prerequisite-first concepts and current mastery at
creation. Recommendations use the latest mastery rows and explain which
mastery status/evidence count drove the next recommendation. Path step
completion and historical path revisions are not yet recalculated after each
assessment; these are tracked as incomplete in
[IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md).
