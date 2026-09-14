"""Phase 1 — a data model small enough to hold in your head.

A company, its departments, the people in them and what they cost. Nothing
here is about enzymes, and that is the point: the machinery in `store.py`,
`graph.py` and `layout.py` has no idea what domain it is drawing, and this
module exists to prove it. `enzymeml.py` is the same 80 lines against a model
nobody in the room wrote.

The field names are German because the graph labels its edges with them, and a
participant who sees `angestellte` on an edge has learned the actual key in the
JSON — which is the one thing a prettier invented label would take away.
"""

from __future__ import annotations

from typing import Mapping, Optional

from pydantic import BaseModel, Field

from .store import Entity, FormField, Step, children_of, of_kind


class Geld(BaseModel):
    einnahmen: float = 0.0
    ausgaben: float = 0.0

    @property
    def saldo(self) -> float:
        return self.einnahmen - self.ausgaben


class Leiter(BaseModel):
    id: str
    name: str = ""
    vorname: str = ""
    email: str = ""
    gehalt: Optional[float] = None


class Angestellter(BaseModel):
    id: str
    name: str = ""
    vorname: str = ""
    gehalt: Optional[float] = None
    einstellungsdatum: str = ""


class Abteilung(BaseModel):
    id: str
    name: str = ""
    leiter: Optional[Leiter] = None
    angestellte: list[Angestellter] = Field(default_factory=list)
    geld: Optional[Geld] = None


class Firma(BaseModel):
    id: str = "firma"
    name: str = "Neue Firma"
    abteilungen: list[Abteilung] = Field(default_factory=list)


#: What each kind of entity needs, in the order the forms ask for it. The
#: notebook builds its forms from this rather than repeating the field names,
#: so adding a field to the model above is one edit, not three.
FIELDS: dict[str, tuple[FormField, ...]] = {
    "Firma": (
        FormField("id", "ID", "text", "example_university", required=True),
        FormField("name", "Name", "text", "Example University", required=True),
    ),
    "Abteilung": (
        FormField("id", "ID", "text", required=True,
                  placeholder="biotech",
                  hint="the handle, not the label — no spaces"),
        FormField("name", "Name", "text", required=True,
                  placeholder="Biotechnologie"),
    ),
    "Leiter": (
        FormField("abteilung", "Abteilung", "select",
                  choices_from="abteilungen", required=True,
                  needs="Abteilung"),
        FormField("id", "ID", "text", required=True, placeholder="mustermann"),
        FormField("vorname", "Vorname", "text", placeholder="Max"),
        FormField("name", "Nachname", "text", placeholder="Mustermann"),
        FormField("email", "E-Mail", "text", placeholder="max@example.edu"),
        FormField("gehalt", "Gehalt (€)", "number"),
    ),
    "Angestellter": (
        FormField("abteilung", "Abteilung", "select",
                  choices_from="abteilungen", required=True,
                  needs="Abteilung"),
        FormField("id", "ID", "text", required=True, placeholder="mueller"),
        FormField("vorname", "Vorname", "text", placeholder="Anna"),
        FormField("name", "Nachname", "text", placeholder="Müller"),
        FormField("gehalt", "Gehalt (€)", "number"),
        FormField("einstellungsdatum", "Einstellungsdatum", "text",
                  placeholder="2021-04-01"),
    ),
    "Geld": (
        FormField("abteilung", "Abteilung", "select",
                  choices_from="abteilungen", required=True,
                  needs="Abteilung"),
        FormField("einnahmen", "Einnahmen (€)", "number", 0.0),
        FormField("ausgaben", "Ausgaben (€)", "number", 0.0),
    ),
}

#: The order the notebook offers them in, with a line on what each one proves.
STEPS: tuple[tuple[str, str, str], ...] = (
    ("Firma", "Firma",
     "There is one company and you rename it rather than adding another — so "
     "this tab submits an *update*, and the node keeps its identity."),
    ("Abteilung", "Abteilung",
     "A department. Add a second one and the company node grows a second "
     "branch — nothing merges, because two departments are two things."),
    ("Leiter", "Leiter",
     "At most one per department. The edge is labelled `leiter`, which is the "
     "actual field name in the model and the actual key in the JSON."),
    ("Angestellter", "Angestellter",
     "Any number per department. This is the case worth watching: every "
     "employee gets their own node, and all of them point at the one "
     "`Angestellter` type node."),
    ("Geld", "Geld",
     "A nested object with no identifier of its own. Its node id comes from "
     "where it sits — `Abteilung:biotech/geld[0]` — because it has nothing "
     "else to be called."),
)


#: Class name to class, so the inspector can answer "what else fits in here?"
#: by reading the model rather than by being told.
MODELS = {m.__name__: m for m in (Firma, Abteilung, Leiter, Angestellter, Geld)}


#: There is one company, and you rename it rather than adding another.
SINGLETONS = {"Firma": "firma"}

#: Kinds whose objects carry their own `id`, and so get a node id of the form
#: `Angestellter:mueller`. `Geld` is missing on purpose: it has no identifier,
#: its node id is the position it sits at, and positions move.
IDENTIFIED = ("Firma", "Abteilung", "Leiter", "Angestellter")


def node_keys(entities: Mapping[str, Entity]) -> dict[str, str]:
    """Graph node id → the key of the entity behind it."""
    return {
        f"{kind}:{entity.text('id', entity.key)}": entity.key
        for kind in IDENTIFIED
        for entity in of_kind(entities, kind)
    }


def choices(entities: Mapping[str, Entity], source: str) -> list[str]:
    """The keys a `choices_from` field may point at."""
    if source == "abteilungen":
        return [e.key for e in of_kind(entities, "Abteilung")]
    return []


def label_for(entities: Mapping[str, Entity], key: str) -> str:
    entity = entities.get(key)
    return (entity.text("name") or entity.text("id", key)) if entity else key


def build_firma(entities: Mapping[str, Entity]) -> Firma:
    """Fold the flat entity log into the nested model.

    The log is flat because history is flat — one edit after another. The model
    is nested because that is the shape of the JSON. Reconciling the two is
    this function's whole job, and it is the only place in the application that
    knows the toy model's shape.
    """
    company = next(iter(of_kind(entities, "Firma")), None)
    firma = Firma(
        id=company.text("id", "firma") if company else "firma",
        name=company.text("name", "Neue Firma") if company else "Neue Firma",
    )

    for entity in of_kind(entities, "Abteilung"):
        abteilung = Abteilung(
            id=entity.text("id", entity.key), name=entity.text("name")
        )
        leader = next(
            iter(children_of(entities, entity.key, via="abteilung", kind="Leiter")),
            None,
        )
        if leader is not None:
            abteilung.leiter = Leiter(
                id=leader.text("id", leader.key),
                name=leader.text("name"),
                vorname=leader.text("vorname"),
                email=leader.text("email"),
                gehalt=leader.number("gehalt"),
            )
        abteilung.angestellte = [
            Angestellter(
                id=person.text("id", person.key),
                name=person.text("name"),
                vorname=person.text("vorname"),
                gehalt=person.number("gehalt"),
                einstellungsdatum=person.text("einstellungsdatum"),
            )
            for person in children_of(
                entities, entity.key, via="abteilung", kind="Angestellter"
            )
        ]
        budget = next(
            iter(children_of(entities, entity.key, via="abteilung", kind="Geld")), None
        )
        if budget is not None:
            abteilung.geld = Geld(
                einnahmen=budget.number("einnahmen", 0.0) or 0.0,
                ausgaben=budget.number("ausgaben", 0.0) or 0.0,
            )
        firma.abteilungen.append(abteilung)

    return firma


def example_log() -> list[Step]:
    """The instance from the workshop brief, as a log you can step through."""
    return [
        Step("add", "Firma", "firma", {"id": "example_university",
                                       "name": "Example University"},
             "Firma **Example University** angelegt"),
        Step("add", "Abteilung", "abteilung_1",
             {"id": "biotech", "name": "Biotechnologie"},
             "Abteilung **Biotechnologie** hinzugefügt"),
        Step("add", "Leiter", "leiter_1",
             {"abteilung": "abteilung_1", "id": "mustermann", "vorname": "Max",
              "name": "Mustermann", "email": "max@example.edu",
              "gehalt": 92000},
             "Leiter **Max Mustermann** hinzugefügt"),
        Step("add", "Angestellter", "angestellter_1",
             {"abteilung": "abteilung_1", "id": "mueller", "vorname": "Anna",
              "name": "Müller", "gehalt": 61000,
              "einstellungsdatum": "2021-04-01"},
             "Angestellte **Anna Müller** hinzugefügt"),
        Step("add", "Angestellter", "angestellter_2",
             {"abteilung": "abteilung_1", "id": "schmidt", "vorname": "Peter",
              "name": "Schmidt", "gehalt": 58000,
              "einstellungsdatum": "2023-09-15"},
             "Angestellter **Peter Schmidt** hinzugefügt"),
        Step("add", "Geld", "geld_1",
             {"abteilung": "abteilung_1", "einnahmen": 1_200_000,
              "ausgaben": 900_000},
             "Budget der Abteilung eingetragen"),
    ]
