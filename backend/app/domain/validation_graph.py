"""Deterministic validation dependency graph and change-impact mapping.

Single source of dependency edges — do not duplicate elsewhere.
"""

from __future__ import annotations

from collections import deque

# Directed edges: parent → dependent (change parent ⇒ revalidate dependents)
VALIDATION_GRAPH_EDGES: tuple[tuple[str, str], ...] = (
    ("reference_product", "reference_evidence"),
    ("reference_evidence", "design"),
    ("design", "food"),
    ("design", "washout"),
    ("design", "sampling"),
    ("design", "statistics"),
    ("design", "subjects"),
    ("food", "analytes"),
    ("analytes", "pk"),
    ("pk", "washout"),
    ("pk", "observation"),
    ("pk", "sampling"),
    ("washout", "sampling"),
    ("observation", "sampling"),
    ("sampling", "blood_volume"),
    ("blood_volume", "statistics"),
    ("statistics", "subjects"),
    ("subjects", "protocol"),
    ("eligibility", "subjects"),
    ("subjects", "procedures"),
    ("cv", "statistics"),
    ("statistics", "subjects"),
)

# Alias nodes used by change-impact API
NODE_ALIASES: dict[str, str] = {
    "tmax": "pk",
    "half_life": "pk",
    "Tmax": "pk",
    "sample_size": "statistics",
    "cv_selection": "cv",
    "cv_studies": "cv",
}


def dependents_of(node: str) -> list[str]:
    """Return all transitive dependents of `node` (deterministic BFS order)."""
    start = NODE_ALIASES.get(node, node)
    adj: dict[str, list[str]] = {}
    for a, b in VALIDATION_GRAPH_EDGES:
        adj.setdefault(a, []).append(b)
    # stable neighbor order
    for k in adj:
        adj[k] = sorted(set(adj[k]))

    seen: set[str] = set()
    order: list[str] = []
    q: deque[str] = deque([start])
    while q:
        cur = q.popleft()
        for nxt in adj.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                order.append(nxt)
                q.append(nxt)
    return order


def change_impact(changed_entity: str) -> dict:
    """Deterministic impact report for a changed entity/field family."""
    node = NODE_ALIASES.get(changed_entity, changed_entity)
    deps = dependents_of(node)
    return {
        "changed": changed_entity,
        "normalized_node": node,
        "revalidate": [node, *deps],
        "protocol_generation_prerequisites_stale": True,
        "graph_version": "VAL.GRAPH.v1",
    }
