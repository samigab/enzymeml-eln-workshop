"""The graph view: an anywidget with a hand-written, dependency-free renderer.

Why not Cytoscape, pyvis, plotly or graphviz — the four obvious candidates:

*pyvis* and *graphviz* produce finished HTML or SVG. Embedding either in
marimo is one line and works well, but neither can tell Python that a node was
clicked, and clicking a node to see what is in it is half of what this
application is for.

*plotly* can report clicks through `mo.ui.plotly`, but a network drawn in
plotly is line traces and annotations pretending to be a diagram: no arrowheads
without hand-placed shapes, no edge labels without hand-placed text, and no
node that can be styled as a card.

*Cytoscape.js* is the right library for the job and the wrong dependency for
this room. It has to reach a CDN at import time or be vendored as a 400 kB
blob inlined into a Python string, and a workshop whose graph goes blank when
the conference wifi does is a workshop with no graph.

What is left is about 300 lines of ES module that imports nothing. It draws
boxes and curves, and it hands a node id back to Python. The layout — the part
that would actually be hard — is computed in `layout.py`, where it can be
tested with `pytest` instead of a browser.
"""

from __future__ import annotations

import pathlib
from typing import Any

import anywidget
import traitlets

_HERE = pathlib.Path(__file__).parent / "static"


class GraphWidget(anywidget.AnyWidget):
    """A live view of a data model.

    Traits are the whole API. `graph` is written from Python and pushed to the
    browser over the widget comm — which is why the notebooks create the widget
    in a cell with no dependencies and update the trait from elsewhere: the
    view stays mounted, so pan and zoom survive an edit and new nodes can
    animate in rather than the picture being rebuilt from nothing.

    `selected` travels the other way, and is the only thing the browser is
    trusted to decide.
    """

    _esm = _HERE / "graph.js"
    _css = _HERE / "graph.css"

    graph = traitlets.Dict({"nodes": [], "edges": []}).tag(sync=True)
    selected = traitlets.Unicode("").tag(sync=True)
    height = traitlets.Int(460).tag(sync=True)
    caption = traitlets.Unicode("").tag(sync=True)

    def show(self, laid_out: dict[str, Any]) -> None:
        """Push a new layout, keeping the selection if the node still exists."""
        if self.selected and self.selected not in {
            n["id"] for n in laid_out.get("nodes", [])
        }:
            self.selected = ""
        self.graph = laid_out
