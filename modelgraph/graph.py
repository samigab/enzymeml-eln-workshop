"""A graph read *off* a pydantic object — never maintained alongside one.

This is the load-bearing rule of the whole application. The graph on screen is
not a second data structure that someone has to keep in step with the document;
it is what you get when you walk the document with `model_fields` and write
down what you find. Delete this module and nothing about the document changes.
Break it and the document is still correct — the picture is simply wrong.

Three kinds of edge come out of the walk, and the difference between them is
most of what the workshop is trying to teach:

`contains`
    A field holds another object. `EnzymeMLDocument.proteins` contains a
    `Protein`. This is the tree the JSON is nested along.

`reference`
    A field holds the *identifier* of another object. `SmallMolecule.vessel_id`
    is the string `"v1"`, and somewhere else there is a vessel whose `id` is
    `"v1"`. Nothing in the JSON nesting shows this link; it exists only because
    two strings match. Drawing it is the moment a participant sees that the
    document is a graph and not a tree.

`instanceOf`
    An object and its class. `Anna Müller` is not the same node as
    `Angestellter`, and for pyenzyme the class node carries the real JSON-LD
    type — `enzml:Protein`, `OBO:PR_000000001` — which is where this workshop's
    documents get their meaning from in the first place.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Sequence

from pydantic import BaseModel

# Bookkeeping pyenzyme attaches to every entity. It belongs in the file and is
# noise in a node's property list — except `ld_type`, which is lifted out and
# shown on the class node, where it is the whole point.
JSONLD_FIELDS = ("ld_id", "ld_type", "ld_context")

# Fields tried in order when a node needs something a human can read on it.
LABEL_FIELDS = ("name", "id", "species_id", "symbol", "family_name")


@dataclass(frozen=True)
class Node:
    id: str
    type: str
    label: str
    kind: str  # "instance" | "class"
    properties: dict[str, Any] = field(default_factory=dict)
    path: str = ""  # where it sits in the document, e.g. "proteins[2]"
    ld_type: tuple[str, ...] = ()


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    relation: str
    kind: str  # "contains" | "reference" | "instanceOf"


@dataclass
class Graph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    # References that name an identifier no object in the document has. Not an
    # error the model can catch — it is a valid document that quietly means
    # nothing — so it is surfaced rather than swallowed.
    dangling: list[tuple[str, str, str]] = field(default_factory=list)

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def counts(self) -> dict[str, int]:
        """How many instances of each type, in first-appearance order."""
        out: dict[str, int] = {}
        for node in self.nodes:
            if node.kind == "instance":
                out[node.type] = out.get(node.type, 0) + 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [asdict(n) | {"ld_type": list(n.ld_type)} for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
        }


def _summarize(value: Any, *, max_values: int = 4) -> Any:
    """A field value as one short, readable thing.

    Eleven time points are a fact about the measurement, not eleven facts, and
    a node that prints all of them stops being readable. The count and the ends
    say what matters: *there is data here, and it runs from 0 to 20*.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return getattr(value, "name", None) or type(value).__name__
    if isinstance(value, (list, tuple)):
        parts = [_summarize(v, max_values=max_values) for v in value]
        if len(parts) > max_values:
            return f"{len(parts)} values: {parts[0]} … {parts[-1]}"
        return ", ".join(str(p) for p in parts)
    if isinstance(value, float):
        return f"{value:g}"
    return value


def _label(obj: BaseModel) -> str:
    for name in LABEL_FIELDS:
        value = getattr(obj, name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return type(obj).__name__


def _identity(obj: BaseModel, parent: str, relation: str, index: int) -> str:
    """A node id that survives the document being rebuilt.

    Stability matters more than beauty here: the layout is derived from the
    graph, so an id that changes when an unrelated field is edited makes the
    picture jump for no reason the participant can see.
    """
    own = getattr(obj, "id", None)
    if isinstance(own, str) and own.strip():
        return f"{type(obj).__name__}:{own.strip()}"
    if not parent:
        return type(obj).__name__
    return f"{parent}/{relation}[{index}]"


def build_graph(
    root: BaseModel,
    *,
    inline: Sequence[str] = (),
    classes: bool = True,
    max_values: int = 4,
    skip: Sequence[str] = (),
    not_references: Sequence[str] = (),
) -> Graph:
    """Walk a pydantic object and write down what is there.

    Args:
        root: any pydantic model — the toy `Firma`, an `EnzymeMLDocument`.
        inline: type names to fold into the parent's properties instead of
            giving them a node. A `UnitDefinition` decomposed into SBML base
            units is four more objects and no more meaning; `ml` says it.
        classes: emit a class node per type, and an `instanceOf` edge to it.
        max_values: how many entries of a scalar list to print before the value
            is summarised.
        skip: field names never to descend into or display.
        not_references: `*_id` fields that hold somebody *else's* identifier —
            an NCBI taxon, a series name — rather than pointing at an object in
            this document. Without the list they would be reported as broken
            references, which is worse than not drawing them.
    """
    graph = Graph()
    hidden = set(JSONLD_FIELDS) | set(skip)
    external = set(not_references)
    inlined = set(inline)
    by_identifier: dict[str, str] = {}  # an entity's own `id` -> its node id
    references: list[tuple[str, str, str]] = []  # (node, field, identifier)
    seen: set[int] = set()

    def visit(obj: BaseModel, node_id: str, path: str) -> None:
        if id(obj) in seen:
            return
        seen.add(id(obj))

        properties: dict[str, Any] = {}
        children: list[tuple[str, str, BaseModel, str]] = []

        for name in type(obj).model_fields:
            if name in hidden:
                continue
            value = getattr(obj, name, None)
            if value is None or value == [] or value == "":
                continue

            items = list(value) if isinstance(value, (list, tuple)) else [value]
            nested = [x for x in items if isinstance(x, BaseModel)]
            if nested and type(nested[0]).__name__ not in inlined:
                for index, child in enumerate(nested):
                    child_path = (
                        f"{path}.{name}[{index}]"
                        if isinstance(value, (list, tuple))
                        else f"{path}.{name}"
                    )
                    children.append(
                        (
                            name,
                            _identity(child, node_id, name, index),
                            child,
                            child_path.lstrip("."),
                        )
                    )
                continue

            properties[name] = _summarize(value, max_values=max_values)
            # The convention that makes reference edges findable without a
            # hand-written schema: a string field whose name ends in `_id`
            # holds somebody else's identifier. EnzymeML follows it
            # throughout — vessel_id, species_id, organism_tax_id.
            if (
                name.endswith("_id")
                and name not in external
                and isinstance(value, str)
                and value.strip()
            ):
                references.append((node_id, name, value.strip()))

        graph.nodes.append(
            Node(
                id=node_id,
                type=type(obj).__name__,
                label=_label(obj),
                kind="instance",
                properties=properties,
                path=path or type(obj).__name__,
                ld_type=tuple(getattr(obj, "ld_type", ()) or ()),
            )
        )
        own = getattr(obj, "id", None)
        if isinstance(own, str) and own.strip():
            by_identifier[own.strip()] = node_id

        for relation, child_id, child, child_path in children:
            graph.edges.append(Edge(node_id, child_id, relation, "contains"))
            visit(child, child_id, child_path)

    visit(root, _identity(root, "", "", 0), "")

    # Resolved only now: a species may be declared after the reaction that
    # names it, and an edge that depends on reading order is an edge that
    # appears and disappears as the participant reorders their forms.
    for source, relation, identifier in references:
        target = by_identifier.get(identifier)
        if target is None:
            graph.dangling.append((source, relation, identifier))
        elif target != source:
            graph.edges.append(Edge(source, target, relation, "reference"))

    if classes:
        _add_class_nodes(graph)
    return graph


def _add_class_nodes(graph: Graph) -> None:
    """One node per type, and an edge from every instance of it.

    `Angestellter` and `Anna Müller` are two nodes because they are two things:
    a shape a record can have, and a record. Participants who have only ever
    seen spreadsheets tend to discover this here rather than in a lecture.
    """
    types: dict[str, type[BaseModel]] = {}
    for node in list(graph.nodes):
        if node.kind != "instance":
            continue
        class_id = f"class:{node.type}"
        if class_id not in types:
            graph.nodes.append(
                Node(
                    id=class_id,
                    type=node.type,
                    label=node.type,
                    kind="class",
                    properties={},
                    path=node.type,
                    ld_type=node.ld_type,
                )
            )
            types[class_id] = node.type
        graph.edges.append(Edge(node.id, class_id, "is a", "instanceOf"))


def describe_class(model: type[BaseModel]) -> dict[str, str]:
    """The fields a type can hold, as the detail panel shows them.

    Answers the question a class node invites — *what else could go in here?* —
    from the model itself, so it stays true when the model changes.
    """
    out: dict[str, str] = {}
    for name, info in model.model_fields.items():
        if name in JSONLD_FIELDS:
            continue
        annotation = info.annotation
        text = getattr(annotation, "__name__", None) or str(annotation)
        text = text.replace("typing.", "").replace("pyenzyme.versions.v2.", "")
        out[name] = text + ("" if info.is_required() else "  (optional)")
    return out


def new_nodes(before: Graph | None, after: Graph) -> list[str]:
    """Which nodes this step added — what the animation highlights."""
    known = {n.id for n in before.nodes} if before else set()
    return [n.id for n in after.nodes if n.id not in known]
