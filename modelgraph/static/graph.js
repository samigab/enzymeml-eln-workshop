// A small SVG graph view. Imports nothing on purpose — see widget.py for why.
//
// It receives a finished layout (every node already has x, y, w, h) and is
// responsible for three things only: drawing it, letting the pointer move
// around it, and telling Python which node was clicked. Anything that needs
// to be reasoned about — where nodes go, what an edge means — happens in
// Python, where it can be tested without a browser.

const NS = "http://www.w3.org/2000/svg";

// Assigned by hashing the type name rather than by order of appearance, so a
// protein is the same colour before and after you add a second reaction.
const PALETTE = [
  "#2563eb", "#059669", "#d946ef", "#ea580c", "#0891b2",
  "#7c3aed", "#ca8a04", "#dc2626", "#0d9488", "#4f46e5",
];

function colourOf(type) {
  let hash = 0;
  for (let i = 0; i < type.length; i++) {
    hash = (hash * 31 + type.charCodeAt(i)) >>> 0;
  }
  return PALETTE[hash % PALETTE.length];
}

function svg(tag, attrs = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) {
    node.setAttribute(key, value);
  }
  return node;
}

// Anchor points chosen by which way the edge actually runs: containment edges
// go left to right between columns, "is a" edges go straight up within one.
function anchors(source, target) {
  const sc = { x: source.x + source.w / 2, y: source.y + source.h / 2 };
  const tc = { x: target.x + target.w / 2, y: target.y + target.h / 2 };
  const dx = tc.x - sc.x;
  const dy = tc.y - sc.y;

  if (Math.abs(dx) >= Math.abs(dy)) {
    const bend = Math.max(28, Math.abs(dx) * 0.42);
    const from = { x: dx >= 0 ? source.x + source.w : source.x, y: sc.y };
    const to = { x: dx >= 0 ? target.x : target.x + target.w, y: tc.y };
    const sign = dx >= 0 ? 1 : -1;
    return [from, { x: from.x + bend * sign, y: from.y },
            { x: to.x - bend * sign, y: to.y }, to];
  }
  const bend = Math.max(20, Math.abs(dy) * 0.45);
  const from = { x: sc.x, y: dy >= 0 ? source.y + source.h : source.y };
  const to = { x: tc.x, y: dy >= 0 ? target.y : target.y + target.h };
  const sign = dy >= 0 ? 1 : -1;
  return [from, { x: from.x, y: from.y + bend * sign },
          { x: to.x, y: to.y - bend * sign }, to];
}

function midpoint([p0, p1, p2, p3]) {
  return {
    x: (p0.x + 3 * p1.x + 3 * p2.x + p3.x) / 8,
    y: (p0.y + 3 * p1.y + 3 * p2.y + p3.y) / 8,
  };
}

function render({ model, el }) {
  el.classList.add("mg-host");
  // Marker ids are document-global. Two graph views on one page would share
  // their arrowheads — and the second one to be removed would take them away
  // from the first — unless each instance mints its own.
  const uid = Math.random().toString(36).slice(2, 8);

  const root = document.createElement("div");
  root.className = "mg-root";
  root.innerHTML = `
    <div class="mg-bar">
      <span class="mg-count"></span>
      <span class="mg-legend">
        <span class="mg-key"><i class="mg-line mg-contains"></i>contains</span>
        <span class="mg-key"><i class="mg-line mg-reference"></i>references</span>
        <span class="mg-key"><i class="mg-line mg-instanceOf"></i>is a</span>
        <span class="mg-key"><i class="mg-swatch mg-swatch-class"></i>type</span>
      </span>
      <span class="mg-tools">
        <button class="mg-btn" data-act="out" title="Zoom out">−</button>
        <button class="mg-btn" data-act="in" title="Zoom in">+</button>
        <button class="mg-btn mg-fit" data-act="fit" title="Fit to view">Fit</button>
      </span>
    </div>
    <div class="mg-canvas"></div>
    <div class="mg-tip" hidden></div>
    <div class="mg-caption"></div>
  `;
  el.appendChild(root);

  const canvas = root.querySelector(".mg-canvas");
  const tip = root.querySelector(".mg-tip");
  const countLabel = root.querySelector(".mg-count");
  const caption = root.querySelector(".mg-caption");

  const sheet = svg("svg", { class: "mg-svg" });
  const defs = svg("defs");
  for (const [name, colour] of [["arrow", "#94a3b8"], ["arrow-ref", "#f59e0b"]]) {
    const marker = svg("marker", {
      id: `mg-${name}-${uid}`, viewBox: "0 0 10 10",
      refX: "9", refY: "5", markerWidth: "6", markerHeight: "6",
      orient: "auto-start-reverse",
    });
    marker.appendChild(svg("path", { d: "M 0 1 L 10 5 L 0 9 z", fill: colour }));
    defs.appendChild(marker);
  }
  sheet.appendChild(defs);
  const viewport = svg("g", { class: "mg-viewport" });
  const edgeLayer = svg("g", { class: "mg-edges" });
  const nodeLayer = svg("g", { class: "mg-nodes" });
  viewport.appendChild(edgeLayer);
  viewport.appendChild(nodeLayer);
  sheet.appendChild(viewport);
  canvas.appendChild(sheet);

  let view = { k: 1, x: 0, y: 0 };
  let known = new Set();      // node ids drawn last time — the rest are new
  let touched = false;        // has the participant panned or zoomed by hand?

  const applyView = () => {
    viewport.setAttribute(
      "transform", `translate(${view.x},${view.y}) scale(${view.k})`);
  };

  const bounds = (nodes) => {
    if (!nodes.length) return null;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const n of nodes) {
      x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y);
      x1 = Math.max(x1, n.x + n.w); y1 = Math.max(y1, n.y + n.h);
    }
    return { x0, y0, x1, y1 };
  };

  const fit = (nodes, { animate = true } = {}) => {
    const box = bounds(nodes);
    if (!box) return;
    const pad = 34;
    const width = canvas.clientWidth || 720;
    const height = canvas.clientHeight || 420;
    const k = Math.min(
      (width - pad * 2) / Math.max(1, box.x1 - box.x0),
      (height - pad * 2) / Math.max(1, box.y1 - box.y0),
      1.35,
    );
    const target = {
      k,
      x: (width - (box.x1 - box.x0) * k) / 2 - box.x0 * k,
      y: (height - (box.y1 - box.y0) * k) / 2 - box.y0 * k,
    };
    if (!animate) { view = target; applyView(); return; }

    const from = { ...view };
    const start = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - start) / 260);
      const e = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
      view = {
        k: from.k + (target.k - from.k) * e,
        x: from.x + (target.x - from.x) * e,
        y: from.y + (target.y - from.y) * e,
      };
      applyView();
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };

  // Everything the new content sits inside the current view? Then leave the
  // view alone — the participant put it there. Otherwise fit, because a node
  // that appears off-screen may as well not have appeared.
  const visible = (box) => {
    const width = canvas.clientWidth || 720;
    const height = canvas.clientHeight || 420;
    return box.x0 * view.k + view.x > -4 && box.y0 * view.k + view.y > -4 &&
           box.x1 * view.k + view.x < width + 4 &&
           box.y1 * view.k + view.y < height + 4;
  };

  const draw = () => {
    const graph = model.get("graph") || { nodes: [], edges: [] };
    const nodes = graph.nodes || [];
    const edges = graph.edges || [];
    const index = new Map(nodes.map((n) => [n.id, n]));
    const selected = model.get("selected");

    edgeLayer.replaceChildren();
    nodeLayer.replaceChildren();

    const incident = new Set();
    for (const edge of edges) {
      const source = index.get(edge.source);
      const target = index.get(edge.target);
      if (!source || !target) continue;
      if (selected && (edge.source === selected || edge.target === selected)) {
        incident.add(edge.source);
        incident.add(edge.target);
      }

      const points = anchors(source, target);
      const [p0, p1, p2, p3] = points;
      const group = svg("g", {
        class: `mg-edge mg-${edge.kind}` +
          (selected && (edge.source === selected || edge.target === selected)
            ? " is-lit" : ""),
      });
      group.appendChild(svg("path", {
        class: "mg-edge-path",
        d: `M ${p0.x},${p0.y} C ${p1.x},${p1.y} ${p2.x},${p2.y} ${p3.x},${p3.y}`,
        "marker-end":
          `url(#mg-${edge.kind === "reference" ? "arrow-ref" : "arrow"}-${uid})`,
      }));
      if (edge.relation) {
        const mid = midpoint(points);
        const label = svg("text", {
          class: "mg-edge-label", x: mid.x, y: mid.y - 3,
          "text-anchor": "middle",
        });
        label.textContent = edge.relation;
        group.appendChild(label);
      }
      edgeLayer.appendChild(group);
    }

    const appearing = [];
    for (const node of nodes) {
      const colour = colourOf(node.type);
      const isNew = known.size > 0 && !known.has(node.id);
      if (isNew) appearing.push(node);

      const group = svg("g", {
        class: `mg-node mg-${node.kind}` +
          (node.id === selected ? " is-selected" : "") +
          (selected && node.id !== selected && !incident.has(node.id)
            ? " is-dim" : "") +
          (isNew ? " is-new" : ""),
        transform: `translate(${node.x},${node.y})`,
        "data-id": node.id,
      });

      group.appendChild(svg("rect", {
        class: "mg-box", width: node.w, height: node.h, rx: 8,
        stroke: colour,
        fill: node.kind === "class" ? "none" : "var(--mg-node-bg)",
      }));

      if (node.kind === "instance") {
        const type = svg("text", {
          class: "mg-type", x: 11, y: 17, fill: colour,
        });
        type.textContent = node.type;
        group.appendChild(type);
        const label = svg("text", { class: "mg-label", x: 11, y: 34 });
        label.textContent = node.label;
        group.appendChild(label);
      } else {
        const label = svg("text", {
          class: "mg-class-label", x: node.w / 2, y: node.h / 2 + 4,
          "text-anchor": "middle", fill: colour,
        });
        label.textContent = node.label;
        group.appendChild(label);
      }

      nodeLayer.appendChild(group);
    }

    known = new Set(nodes.map((n) => n.id));
    countLabel.textContent =
      `${nodes.filter((n) => n.kind === "instance").length} nodes · ` +
      `${edges.filter((e) => e.kind !== "instanceOf").length} edges`;
    caption.textContent = model.get("caption") || "";
    caption.hidden = !caption.textContent;

    if (!nodes.length) return;
    const box = appearing.length ? bounds(appearing) : bounds(nodes);
    if (!touched || !visible(box)) {
      fit(nodes, { animate: touched });
    }
  };

  // ---- interaction -------------------------------------------------------

  const nodeAt = (event) => event.target.closest(".mg-node");

  canvas.addEventListener("click", (event) => {
    const hit = nodeAt(event);
    model.set("selected", hit ? hit.dataset.id : "");
    model.save_changes();
    draw();
  });

  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    touched = true;
    const rect = canvas.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const k = Math.min(3, Math.max(0.15, view.k * Math.exp(-event.deltaY * 0.0016)));
    view = {
      k,
      x: px - (px - view.x) * (k / view.k),
      y: py - (py - view.y) * (k / view.k),
    };
    applyView();
  }, { passive: false });

  let drag = null;
  canvas.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    drag = { x: event.clientX, y: event.clientY, view: { ...view }, moved: false };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    const hit = nodeAt(event);
    if (drag) {
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) {
        drag.moved = true;
        touched = true;
        canvas.classList.add("is-panning");
        view = { k: drag.view.k, x: drag.view.x + dx, y: drag.view.y + dy };
        applyView();
      }
      return;
    }
    if (!hit) { tip.hidden = true; return; }

    const graph = model.get("graph") || { nodes: [] };
    const node = (graph.nodes || []).find((n) => n.id === hit.dataset.id);
    if (!node) { tip.hidden = true; return; }

    const rows = Object.entries(node.properties || {})
      .map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join("");
    const ld = (node.ld_type || []).join(", ");
    tip.innerHTML =
      `<div class="mg-tip-head">${node.kind === "class" ? "type " : ""}` +
      `<b>${node.full_label || node.label}</b>` +
      `<span>${node.type}</span></div>` +
      (ld ? `<div class="mg-tip-ld">${ld}</div>` : "") +
      (rows ? `<table>${rows}</table>`
            : `<div class="mg-tip-empty">no properties set yet</div>`);
    tip.hidden = false;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left + 14;
    const y = event.clientY - rect.top + 14;
    tip.style.left = `${Math.min(x, rect.width - tip.offsetWidth - 8)}px`;
    tip.style.top = `${Math.min(y, rect.height - tip.offsetHeight - 8)}px`;
  });
  const endDrag = (event) => {
    if (drag && canvas.hasPointerCapture?.(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }
    // A pan that ends over a node should not also count as selecting it.
    if (drag?.moved) { event.stopPropagation(); event.preventDefault(); }
    drag = null;
    canvas.classList.remove("is-panning");
  };
  canvas.addEventListener("pointerup", endDrag, true);
  canvas.addEventListener("pointercancel", endDrag, true);
  canvas.addEventListener("pointerleave", () => { tip.hidden = true; });

  root.querySelector(".mg-tools").addEventListener("click", (event) => {
    const act = event.target.dataset?.act;
    if (!act) return;
    if (act === "fit") {
      touched = false;
      fit((model.get("graph") || { nodes: [] }).nodes || []);
      return;
    }
    touched = true;
    const width = canvas.clientWidth / 2;
    const height = canvas.clientHeight / 2;
    const k = Math.min(3, Math.max(0.15, view.k * (act === "in" ? 1.25 : 0.8)));
    view = {
      k,
      x: width - (width - view.x) * (k / view.k),
      y: height - (height - view.y) * (k / view.k),
    };
    applyView();
  });

  const applyHeight = () => {
    canvas.style.height = `${model.get("height")}px`;
  };
  applyHeight();

  model.on("change:graph", draw);
  model.on("change:selected", draw);
  model.on("change:caption", draw);
  model.on("change:height", () => { applyHeight(); });

  // The first fit has to wait for the canvas to have a width; in marimo the
  // widget is measured a frame after it is inserted.
  requestAnimationFrame(() => {
    draw();
    const nodes = (model.get("graph") || { nodes: [] }).nodes || [];
    fit(nodes, { animate: false });
  });

  return () => { model.off("change:graph", draw); };
}

export default { render };
