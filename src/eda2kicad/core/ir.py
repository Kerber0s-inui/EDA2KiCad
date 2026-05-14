from dataclasses import dataclass, field


Point = tuple[int, int]


@dataclass(slots=True)
class Field:
    name: str
    value: str


@dataclass(slots=True)
class WireSegment:
    start: Point
    end: Point


@dataclass(slots=True)
class NetLabel:
    text: str
    position: Point


@dataclass(slots=True)
class ComponentInstance:
    designator: str
    library_key: str
    value: str
    footprint: str
    fields: list[Field] = field(default_factory=list)


@dataclass(slots=True)
class Sheet:
    name: str
    components: list[ComponentInstance] = field(default_factory=list)
    wires: list[WireSegment] = field(default_factory=list)
    net_labels: list[NetLabel] = field(default_factory=list)


@dataclass(slots=True)
class Project:
    name: str
    sheets: list[Sheet] = field(default_factory=list)
