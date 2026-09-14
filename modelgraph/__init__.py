"""Build a data model step by step, and watch the graph it makes.

    step log  ──►  pydantic object  ──┬──►  JSON
                                      └──►  graph  ──►  layout  ──►  widget

Read left to right, that is the whole architecture, and the one rule worth
stating: **everything downstream of the pydantic object is derived**. The graph
is not maintained; it is recomputed. There is no second copy of the data to
keep in step, which is why the picture cannot go stale and why a bug in the
drawing can never corrupt a document.

`toy.py` and `enzymeml.py` are the only two modules that know what a domain
looks like. Everything else works on any pydantic model at all.
"""

from .graph import Edge, Graph, Node, build_graph, describe_class, new_nodes
from .layout import layout
from .store import Entity, Step, children_of, next_key, of_kind, replay
from .widget import GraphWidget

__all__ = [
    "Edge",
    "Entity",
    "Graph",
    "GraphWidget",
    "Node",
    "Step",
    "build_graph",
    "children_of",
    "describe_class",
    "layout",
    "new_nodes",
    "next_key",
    "of_kind",
    "replay",
]


def view(root, **options) -> dict:
    """The shortcut the notebooks use: a pydantic object, laid out.

    Keyword arguments are passed through to `build_graph` — `inline` and
    `classes` are the two worth knowing about.
    """
    return layout(build_graph(root, **options))
