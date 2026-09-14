"""Where every node goes — computed in Python, once, deterministically.

The obvious alternative is a force simulation in the browser, and it is the
wrong choice for this application. A physics layout reshuffles the whole
picture when a node is added, which is precisely the moment the participant is
supposed to be looking at *one new node*. Here, adding a protein moves the
proteins below it down and leaves the rest of the document where it was.

The layout is a left-to-right layering: depth in the containment tree gives the
column, and within a column the nodes are stacked in the order their parents
are, so a reaction's participants sit next to the reaction rather than
scattered among the measurements.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .graph import Graph

NODE_HEIGHT = 46
CLASS_HEIGHT = 30
ROW_GAP = 14
BAND_GAP = 34  # between the class band and the instances below it
COLUMN_GAP = 96
CHAR_WIDTH = 7.1  # 13px system sans, measured badly but consistently
MIN_WIDTH = 104
MAX_WIDTH = 230
LABEL_LIMIT = 30


def _width(label: str, *, kind: str) -> float:
    padding = 26 if kind == "instance" else 20
    return max(MIN_WIDTH, min(MAX_WIDTH, len(label) * CHAR_WIDTH + padding))


def _truncate(label: str) -> str:
    return label if len(label) <= LABEL_LIMIT else label[: LABEL_LIMIT - 1] + "…"


def _columns(graph: Graph) -> dict[str, int]:
    """Depth in the containment tree, breadth-first from the roots.

    Reference edges are deliberately ignored. They are what makes the picture a
    graph, and letting them set the columns too would drag every species into
    the vessel's column and flatten the document's actual shape.
    """
    contains = defaultdict(list)
    has_parent: set[str] = set()
    for edge in graph.edges:
        if edge.kind == "contains":
            contains[edge.source].append(edge.target)
            has_parent.add(edge.target)

    instances = [n.id for n in graph.nodes if n.kind == "instance"]
    column = {node: 0 for node in instances if node not in has_parent}
    queue = list(column)
    while queue:
        node = queue.pop(0)
        for child in contains[node]:
            if child not in column:
                column[child] = column[node] + 1
                queue.append(child)
    # Anything unreachable (a document with no root, mid-edit) still needs a
    # place to stand rather than an exception.
    for node in instances:
        column.setdefault(node, 0)

    # A class node belongs above the leftmost of its instances, so the "is a"
    # edges stay short and vertical instead of crossing the whole diagram.
    for edge in graph.edges:
        if edge.kind == "instanceOf":
            here = column.get(edge.source, 0)
            column[edge.target] = min(column.get(edge.target, here), here)
    return column


def layout(graph: Graph) -> dict[str, Any]:
    """The graph as the widget wants it: nodes with x, y, width and height."""
    column = _columns(graph)
    nodes = {n.id: n for n in graph.nodes}

    parent_of = {
        e.target: e.source for e in graph.edges if e.kind == "contains"
    }
    order = {n.id: i for i, n in enumerate(graph.nodes)}

    placed: dict[str, dict[str, float]] = {}
    by_column: dict[int, list[str]] = defaultdict(list)
    for node_id, col in column.items():
        by_column[col].append(node_id)

    column_width: dict[int, float] = {}
    for col, members in by_column.items():
        column_width[col] = max(
            (_width(_truncate(nodes[m].label), kind=nodes[m].kind) for m in members),
            default=MIN_WIDTH,
        )

    column_x: dict[int, float] = {}
    x = 0.0
    for col in sorted(by_column):
        column_x[col] = x
        members = by_column[col]
        # Children follow their parent's vertical order; siblings keep the
        # order they appear in the document. Between them that is enough to
        # keep a subtree together without a proper crossing-minimisation pass.
        members.sort(
            key=lambda m: (
                placed.get(parent_of.get(m, ""), {}).get("y", -1e9),
                order.get(m, 0),
            )
        )
        y = 0.0
        for node_id in members:
            if nodes[node_id].kind == "class":
                continue  # the class band is placed afterwards, see below
            placed[node_id] = {"x": x, "y": y, "h": NODE_HEIGHT}
            y += NODE_HEIGHT + ROW_GAP

        for node_id in members:
            if node_id in placed:
                placed[node_id]["w"] = column_width[col]
        x += column_width[col] + COLUMN_GAP

    # Centre every column against the tallest one, so the diagram reads from
    # the middle outwards instead of hanging off the top edge.
    tallest = max(
        (
            max((placed[m]["y"] + placed[m]["h"] for m in members if m in placed),
                default=0.0)
            for members in by_column.values()
        ),
        default=0.0,
    )
    for members in by_column.values():
        heights = [placed[m]["y"] + placed[m]["h"] for m in members if m in placed]
        if not heights:
            continue
        offset = (tallest - max(heights)) / 2
        for node_id in members:
            if node_id in placed:
                placed[node_id]["y"] += offset

    # The class band is a single row across the top, not a stack per column.
    # An EnzymeML document has ten types in two columns, and stacking them
    # there doubled the height of the whole diagram — which cost far more
    # readability than the long "is a" edges cost, and those are drawn faint
    # precisely so they can be ignored.
    #
    # Each chip starts over its own column and slides right only as far as it
    # must to clear its neighbour, so the band still reads left to right in the
    # same order as the graph beneath it.
    # It wraps to the width of the graph beneath it rather than running off the
    # side: a band wider than the diagram would set the zoom for the whole
    # view, and the instances — the part anybody is actually reading — would
    # shrink to fit a row of labels.
    chips = [
        (node_id, _width(_truncate(nodes[node_id].label), kind="class"))
        for col in sorted(by_column)
        for node_id in by_column[col]
        if nodes[node_id].kind == "class"
    ]
    # A little overhang is cheaper than a second row: one chip sticking out by
    # a fifth of the width barely moves the zoom, while an extra row costs
    # every node some height.
    span = max((p["x"] + p["w"] for p in placed.values()), default=0.0) * 1.2

    rows: list[list[tuple[str, float]]] = [[]]
    used = 0.0
    for node_id, width in chips:
        if used and used + width > span:
            rows.append([])
            used = 0.0
        rows[-1].append((node_id, width))
        used += width + ROW_GAP

    band_y = min((p["y"] for p in placed.values()), default=0.0) - BAND_GAP
    for index, row in enumerate(rows):
        y = band_y - (len(rows) - index) * (CLASS_HEIGHT + ROW_GAP)
        left = 0.0
        for node_id, width in row:
            placed[node_id] = {"x": left, "y": y, "w": width, "h": CLASS_HEIGHT}
            left += width + ROW_GAP

    return {
        "nodes": [
            {
                "id": node.id,
                "type": node.type,
                "label": _truncate(node.label),
                "full_label": node.label,
                "kind": node.kind,
                "properties": {k: str(v) for k, v in node.properties.items()},
                "path": node.path,
                "ld_type": list(node.ld_type),
                **placed.get(node.id, {"x": 0, "y": 0, "w": MIN_WIDTH, "h": NODE_HEIGHT}),
            }
            for node in graph.nodes
        ],
        "edges": [
            {
                "source": e.source,
                "target": e.target,
                "relation": e.relation,
                "kind": e.kind,
            }
            for e in graph.edges
        ],
    }
