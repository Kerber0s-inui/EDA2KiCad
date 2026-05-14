# Altium ASCII 到 KiCad 原理图转换器实现计划

> **供智能体执行：** 必需子技能：使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项实现。步骤使用复选框 `- [ ]` 语法跟踪。

**目标：** 构建一个基于 Python 的 Altium ASCII 到 KiCad 原理图转换框架，同时接入自研链路、KiCad 官方能力辅助链路、第三方库链路三种方法，保留已确认的工程语义，提供 CLI 和本地 Web 入口，并输出机器可读的转换报告与质量对比结果。

**架构：** 实现采用共享转换核心和策略层。自研链路按 `Altium ASCII 解析 -> IR 归一化 -> 符号解析 -> KiCad 写出 -> 校验/报告` 执行；同时预留 KiCad 官方能力辅助链路和第三方库链路，通过统一策略接口接入同一套评测框架。CLI 和本地 Web 共用同一个 `ConversionService`，保证行为一致，并为未来云端 API 复用相同边界。

**技术栈：** Python 3.11+、pytest、Typer、FastAPI、Jinja2、dataclasses、pathlib、标准库 `json`

---

## 计划文件结构

### 项目启动层

- 创建：`C:\dev\EDA2KiCad\pyproject.toml`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\__init__.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\paths.py`
- 创建：`C:\dev\EDA2KiCad\tests\test_bootstrap.py`

### 核心领域模型

- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\core\ir.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\core\report.py`
- 创建：`C:\dev\EDA2KiCad\tests\core\test_ir.py`
- 创建：`C:\dev\EDA2KiCad\tests\core\test_report.py`

### Altium ASCII 输入层

- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\altium_ascii\lexer.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\altium_ascii\parser.py`
- 创建：`C:\dev\EDA2KiCad\tests\fixtures\altium_ascii\minimal_ascii_schematic.txt`
- 创建：`C:\dev\EDA2KiCad\tests\altium_ascii\test_parser.py`

### 归一化与符号解析层

- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\normalize\transform.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\symbols\resolver.py`
- 创建：`C:\dev\EDA2KiCad\libraries\local_symbol_map.json`
- 创建：`C:\dev\EDA2KiCad\tests\normalize\test_transform.py`
- 创建：`C:\dev\EDA2KiCad\tests\symbols\test_resolver.py`

### KiCad 输出与校验层

- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\kicad\writer.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\validation\checks.py`
- 创建：`C:\dev\EDA2KiCad\tests\kicad\test_writer.py`
- 创建：`C:\dev\EDA2KiCad\tests\validation\test_checks.py`

### 多策略层

- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\strategies\base.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\strategies\custom_pipeline.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\strategies\kicad_official.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\strategies\third_party.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\strategies\compare.py`
- 创建：`C:\dev\EDA2KiCad\tests\strategies\test_compare.py`

### 应用入口层

- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\service.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\cli.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\web\app.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\web\templates\index.html`
- 创建：`C:\dev\EDA2KiCad\tests\test_cli.py`
- 创建：`C:\dev\EDA2KiCad\tests\web\test_app.py`

### Golden 测试与用户文档

- 创建：`C:\dev\EDA2KiCad\tests\golden\test_end_to_end.py`
- 创建：`C:\dev\EDA2KiCad\tests\golden\test_strategy_comparison.py`
- 创建：`C:\dev\EDA2KiCad\tests\fixtures\golden\manifest.json`
- 创建：`C:\dev\EDA2KiCad\README.md`

## 任务 1：初始化 Python 项目

**文件：**
- 创建：`C:\dev\EDA2KiCad\pyproject.toml`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\__init__.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\paths.py`
- 创建：`C:\dev\EDA2KiCad\tests\test_bootstrap.py`

- [ ] **步骤 1：先写失败测试**

```python
# C:\dev\EDA2KiCad\tests\test_bootstrap.py
from pathlib import Path

from eda2kicad import __version__
from eda2kicad.paths import ensure_output_dir


def test_package_exposes_version_and_output_dir(tmp_path: Path) -> None:
    assert __version__ == "0.1.0"

    output_dir = ensure_output_dir(tmp_path / "artifacts")

    assert output_dir.exists()
    assert output_dir.is_dir()
```

- [ ] **步骤 2：运行测试，确认它失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\test_bootstrap.py -v`

预期：`ModuleNotFoundError: No module named 'eda2kicad'`

- [ ] **步骤 3：写最小实现**

```toml
# C:\dev\EDA2KiCad\pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "eda2kicad"
version = "0.1.0"
description = "Altium ASCII to KiCad converter"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "typer>=0.12,<1.0",
  "fastapi>=0.111,<1.0",
  "uvicorn>=0.30,<1.0",
  "jinja2>=3.1,<4.0",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
# C:\dev\EDA2KiCad\src\eda2kicad\__init__.py
__version__ = "0.1.0"
```

```python
# C:\dev\EDA2KiCad\src\eda2kicad\paths.py
from pathlib import Path


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\test_bootstrap.py -v`

预期：`1 passed`

- [ ] **步骤 5：提交**

```bash
git add pyproject.toml src/eda2kicad/__init__.py src/eda2kicad/paths.py tests/test_bootstrap.py
git commit -m "chore: bootstrap eda2kicad python project"
```

## 任务 2：定义 IR 和转换报告模型

**文件：**
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\core\ir.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\core\report.py`
- 创建：`C:\dev\EDA2KiCad\tests\core\test_ir.py`
- 创建：`C:\dev\EDA2KiCad\tests\core\test_report.py`

- [ ] **步骤 1：先写失败测试**

```python
# C:\dev\EDA2KiCad\tests\core\test_ir.py
from eda2kicad.core.ir import ComponentInstance, Field, NetLabel, Project, Sheet, WireSegment


def test_project_keeps_confirmed_engineering_fields() -> None:
    project = Project(
        name="demo",
        sheets=[
            Sheet(
                name="Main",
                components=[
                    ComponentInstance(
                        designator="R1",
                        library_key="RES_0603",
                        value="10k",
                        footprint="Resistor_SMD:R_0603_1608Metric",
                        fields=[
                            Field("Part Number", "RC0603FR-0710KL"),
                            Field("Manufacturer", "Yageo"),
                            Field("Supplier", "LCSC"),
                        ],
                    )
                ],
                wires=[WireSegment((0, 0), (100, 0))],
                net_labels=[NetLabel("NET_A", (100, 0))],
            )
        ],
    )

    component = project.sheets[0].components[0]

    assert component.designator == "R1"
    assert component.footprint.endswith("0603_1608Metric")
    assert [field.name for field in component.fields] == [
        "Part Number",
        "Manufacturer",
        "Supplier",
    ]
```

```python
# C:\dev\EDA2KiCad\tests\core\test_report.py
from eda2kicad.core.report import ConversionIssue, ConversionReport


def test_report_serializes_conversion_issues() -> None:
    report = ConversionReport()
    report.add_issue(
        ConversionIssue(
            severity="error",
            code="net_label_mismatch",
            message="NET_A label was not emitted at the expected coordinate",
        )
    )

    payload = report.to_dict()

    assert payload["summary"]["error_count"] == 1
    assert payload["issues"][0]["code"] == "net_label_mismatch"
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\core -v`

预期：`eda2kicad.core.ir` 和 `eda2kicad.core.report` 导入失败

- [ ] **步骤 3：写最小实现**

```python
# C:\dev\EDA2KiCad\src\eda2kicad\core\ir.py
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
```

```python
# C:\dev\EDA2KiCad\src\eda2kicad\core\report.py
from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class ConversionIssue:
    severity: str
    code: str
    message: str


@dataclass(slots=True)
class ConversionReport:
    issues: list[ConversionIssue] = field(default_factory=list)

    def add_issue(self, issue: ConversionIssue) -> None:
        self.issues.append(issue)

    def to_dict(self) -> dict:
        return {
            "summary": {
                "error_count": sum(issue.severity == "error" for issue in self.issues),
                "warning_count": sum(issue.severity == "warning" for issue in self.issues),
            },
            "issues": [asdict(issue) for issue in self.issues],
        }
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\core -v`

预期：`2 passed`

- [ ] **步骤 5：提交**

```bash
git add src/eda2kicad/core/ir.py src/eda2kicad/core/report.py tests/core/test_ir.py tests/core/test_report.py
git commit -m "feat: add ir and conversion report models"
```

## 任务 3：解析最小 Altium ASCII 原理图片段

**文件：**
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\altium_ascii\lexer.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\altium_ascii\parser.py`
- 创建：`C:\dev\EDA2KiCad\tests\fixtures\altium_ascii\minimal_ascii_schematic.txt`
- 创建：`C:\dev\EDA2KiCad\tests\altium_ascii\test_parser.py`

- [ ] **步骤 1：先写失败测试和夹具**

```text
# C:\dev\EDA2KiCad\tests\fixtures\altium_ascii\minimal_ascii_schematic.txt
RECORD=COMPONENT
DESIGNATOR=R1
LIBRARY=RES_0603
VALUE=10k
FOOTPRINT=Resistor_SMD:R_0603_1608Metric

RECORD=FIELD
OWNER=R1
NAME=Manufacturer
VALUE=Yageo

RECORD=WIRE
X1=0
Y1=0
X2=100
Y2=0

RECORD=NET_LABEL
TEXT=NET_A
X=100
Y=0
```

```python
# C:\dev\EDA2KiCad\tests\altium_ascii\test_parser.py
from pathlib import Path

from eda2kicad.altium_ascii.parser import parse_ascii_schematic


def test_parse_ascii_schematic_reads_records() -> None:
    fixture = Path("C:/dev/EDA2KiCad/tests/fixtures/altium_ascii/minimal_ascii_schematic.txt")

    parsed = parse_ascii_schematic(fixture.read_text(encoding="utf-8"))

    assert parsed["components"][0]["DESIGNATOR"] == "R1"
    assert parsed["fields"][0]["NAME"] == "Manufacturer"
    assert parsed["wires"][0]["X2"] == "100"
    assert parsed["net_labels"][0]["TEXT"] == "NET_A"
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\altium_ascii\test_parser.py -v`

预期：`eda2kicad.altium_ascii.parser` 导入失败

- [ ] **步骤 3：写最小 lexer/parser**

```python
# C:\dev\EDA2KiCad\src\eda2kicad\altium_ascii\lexer.py
def split_records(text: str) -> list[dict[str, str]]:
    blocks = [block.strip() for block in text.strip().split("\n\n") if block.strip()]
    records: list[dict[str, str]] = []
    for block in blocks:
        record: dict[str, str] = {}
        for line in block.splitlines():
            key, value = line.split("=", 1)
            record[key.strip()] = value.strip()
        records.append(record)
    return records
```

```python
# C:\dev\EDA2KiCad\src\eda2kicad\altium_ascii\parser.py
from eda2kicad.altium_ascii.lexer import split_records


def parse_ascii_schematic(text: str) -> dict[str, list[dict[str, str]]]:
    buckets = {
        "components": [],
        "fields": [],
        "wires": [],
        "net_labels": [],
    }
    for record in split_records(text):
        record_type = record["RECORD"]
        if record_type == "COMPONENT":
            buckets["components"].append(record)
        elif record_type == "FIELD":
            buckets["fields"].append(record)
        elif record_type == "WIRE":
            buckets["wires"].append(record)
        elif record_type == "NET_LABEL":
            buckets["net_labels"].append(record)
    return buckets
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\altium_ascii\test_parser.py -v`

预期：`1 passed`

- [ ] **步骤 5：提交**

```bash
git add src/eda2kicad/altium_ascii/lexer.py src/eda2kicad/altium_ascii/parser.py tests/fixtures/altium_ascii/minimal_ascii_schematic.txt tests/altium_ascii/test_parser.py
git commit -m "feat: add minimal altium ascii parser"
```

## 任务 4：把解析结果归一化成 IR

**文件：**
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\normalize\transform.py`
- 创建：`C:\dev\EDA2KiCad\tests\normalize\test_transform.py`

- [ ] **步骤 1：先写失败测试**

```python
# C:\dev\EDA2KiCad\tests\normalize\test_transform.py
from eda2kicad.altium_ascii.parser import parse_ascii_schematic
from eda2kicad.normalize.transform import parsed_records_to_project


ASCII_TEXT = """\
RECORD=COMPONENT
DESIGNATOR=R1
LIBRARY=RES_0603
VALUE=10k
FOOTPRINT=Resistor_SMD:R_0603_1608Metric

RECORD=FIELD
OWNER=R1
NAME=Manufacturer
VALUE=Yageo

RECORD=WIRE
X1=0
Y1=0
X2=100
Y2=0

RECORD=NET_LABEL
TEXT=NET_A
X=100
Y=0
"""


def test_transform_builds_single_sheet_project() -> None:
    parsed = parse_ascii_schematic(ASCII_TEXT)

    project = parsed_records_to_project("demo", parsed)

    component = project.sheets[0].components[0]
    assert project.name == "demo"
    assert component.designator == "R1"
    assert component.fields[0].value == "Yageo"
    assert project.sheets[0].net_labels[0].text == "NET_A"
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\normalize\test_transform.py -v`

预期：`eda2kicad.normalize.transform` 导入失败

- [ ] **步骤 3：写最小归一化实现**

```python
# C:\dev\EDA2KiCad\src\eda2kicad\normalize\transform.py
from eda2kicad.core.ir import ComponentInstance, Field, NetLabel, Project, Sheet, WireSegment


def parsed_records_to_project(name: str, parsed: dict[str, list[dict[str, str]]]) -> Project:
    component_fields: dict[str, list[Field]] = {}
    for field_record in parsed["fields"]:
        owner = field_record["OWNER"]
        component_fields.setdefault(owner, []).append(Field(field_record["NAME"], field_record["VALUE"]))

    components = [
        ComponentInstance(
            designator=record["DESIGNATOR"],
            library_key=record["LIBRARY"],
            value=record["VALUE"],
            footprint=record["FOOTPRINT"],
            fields=component_fields.get(record["DESIGNATOR"], []),
        )
        for record in parsed["components"]
    ]
    wires = [
        WireSegment(
            (int(record["X1"]), int(record["Y1"])),
            (int(record["X2"]), int(record["Y2"])),
        )
        for record in parsed["wires"]
    ]
    net_labels = [
        NetLabel(record["TEXT"], (int(record["X"]), int(record["Y"])))
        for record in parsed["net_labels"]
    ]
    return Project(name=name, sheets=[Sheet(name="Sheet1", components=components, wires=wires, net_labels=net_labels)])
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\normalize\test_transform.py -v`

预期：`1 passed`

- [ ] **步骤 5：提交**

```bash
git add src/eda2kicad/normalize/transform.py tests/normalize/test_transform.py
git commit -m "feat: normalize parsed records into ir"
```

## 任务 5：按本地库映射规则解析符号

**文件：**
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\symbols\resolver.py`
- 创建：`C:\dev\EDA2KiCad\libraries\local_symbol_map.json`
- 创建：`C:\dev\EDA2KiCad\tests\symbols\test_resolver.py`

- [ ] **步骤 1：先写失败测试和映射文件**

```json
// C:\dev\EDA2KiCad\libraries\local_symbol_map.json
{
  "RES_0603": "CompanyLib:RES_0603",
  "CAP_0402": "CompanyLib:CAP_0402"
}
```

```python
# C:\dev\EDA2KiCad\tests\symbols\test_resolver.py
from pathlib import Path

from eda2kicad.core.ir import ComponentInstance
from eda2kicad.symbols.resolver import SymbolResolutionResult, resolve_symbol


def test_resolver_prefers_local_library() -> None:
    component = ComponentInstance(
        designator="R1",
        library_key="RES_0603",
        value="10k",
        footprint="Resistor_SMD:R_0603_1608Metric",
    )

    result = resolve_symbol(
        component,
        Path("C:/dev/EDA2KiCad/libraries/local_symbol_map.json"),
    )

    assert isinstance(result, SymbolResolutionResult)
    assert result.library_id == "CompanyLib:RES_0603"
    assert result.source == "local-map"
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\symbols\test_resolver.py -v`

预期：`eda2kicad.symbols.resolver` 导入失败

- [ ] **步骤 3：写最小解析实现**

```python
# C:\dev\EDA2KiCad\src\eda2kicad\symbols\resolver.py
import json
from dataclasses import dataclass
from pathlib import Path

from eda2kicad.core.ir import ComponentInstance


@dataclass(slots=True)
class SymbolResolutionResult:
    library_id: str
    source: str
    needs_private_symbol: bool


def resolve_symbol(component: ComponentInstance, mapping_path: Path) -> SymbolResolutionResult:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if component.library_key in mapping:
        return SymbolResolutionResult(
            library_id=mapping[component.library_key],
            source="local-map",
            needs_private_symbol=False,
        )
    return SymbolResolutionResult(
        library_id=f"Generated:{component.library_key}",
        source="private-symbol",
        needs_private_symbol=True,
    )
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\symbols\test_resolver.py -v`

预期：`1 passed`

- [ ] **步骤 5：提交**

```bash
git add src/eda2kicad/symbols/resolver.py libraries/local_symbol_map.json tests/symbols/test_resolver.py
git commit -m "feat: resolve symbols from local library map"
```

## 任务 6：生成 KiCad 原理图并校验已确认语义

**文件：**
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\kicad\writer.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\validation\checks.py`
- 创建：`C:\dev\EDA2KiCad\tests\kicad\test_writer.py`
- 创建：`C:\dev\EDA2KiCad\tests\validation\test_checks.py`

- [ ] **步骤 1：先写失败测试**

```python
# C:\dev\EDA2KiCad\tests\kicad\test_writer.py
from eda2kicad.core.ir import ComponentInstance, NetLabel, Project, Sheet, WireSegment
from eda2kicad.kicad.writer import render_kicad_schematic


def test_writer_emits_components_wires_and_labels() -> None:
    project = Project(
        name="demo",
        sheets=[
            Sheet(
                name="Sheet1",
                components=[
                    ComponentInstance(
                        designator="R1",
                        library_key="RES_0603",
                        value="10k",
                        footprint="Resistor_SMD:R_0603_1608Metric",
                    )
                ],
                wires=[WireSegment((0, 0), (100, 0))],
                net_labels=[NetLabel("NET_A", (100, 0))],
            )
        ],
    )

    output = render_kicad_schematic(project, {"R1": "CompanyLib:RES_0603"})

    assert "(symbol" in output
    assert "CompanyLib:RES_0603" in output
    assert "NET_A" in output
```

```python
# C:\dev\EDA2KiCad\tests\validation\test_checks.py
from eda2kicad.core.ir import NetLabel, Project, Sheet
from eda2kicad.validation.checks import validate_project


def test_validation_rejects_missing_net_label() -> None:
    project = Project(name="demo", sheets=[Sheet(name="Sheet1", net_labels=[NetLabel("", (0, 0))])])

    report = validate_project(project)

    assert report["summary"]["error_count"] == 1
    assert report["issues"][0]["code"] == "invalid_net_label"
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\kicad\test_writer.py C:\dev\EDA2KiCad\tests\validation\test_checks.py -v`

预期：`eda2kicad.kicad.writer` 和 `eda2kicad.validation.checks` 导入失败

- [ ] **步骤 3：写最小实现**

```python
# C:\dev\EDA2KiCad\src\eda2kicad\kicad\writer.py
from eda2kicad.core.ir import Project


def render_kicad_schematic(project: Project, resolved_symbols: dict[str, str]) -> str:
    lines = ["(kicad_sch (version 20231120) (generator eda2kicad)"]
    for sheet in project.sheets:
        for component in sheet.components:
            library_id = resolved_symbols[component.designator]
            lines.append(
                f'  (symbol (lib_id "{library_id}") (property "Reference" "{component.designator}") (property "Value" "{component.value}"))'
            )
        for wire in sheet.wires:
            lines.append(f"  (wire (pts (xy {wire.start[0]} {wire.start[1]}) (xy {wire.end[0]} {wire.end[1]})))")
        for label in sheet.net_labels:
            lines.append(f'  (label "{label.text}" (at {label.position[0]} {label.position[1]} 0))')
    lines.append(")")
    return "\n".join(lines)
```

```python
# C:\dev\EDA2KiCad\src\eda2kicad\validation\checks.py
from eda2kicad.core.ir import Project
from eda2kicad.core.report import ConversionIssue, ConversionReport


def validate_project(project: Project) -> dict:
    report = ConversionReport()
    for sheet in project.sheets:
        for label in sheet.net_labels:
            if not label.text.strip():
                report.add_issue(
                    ConversionIssue(
                        severity="error",
                        code="invalid_net_label",
                        message="Net labels must not be empty",
                    )
                )
    return report.to_dict()
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\kicad\test_writer.py C:\dev\EDA2KiCad\tests\validation\test_checks.py -v`

预期：`2 passed`

- [ ] **步骤 5：提交**

```bash
git add src/eda2kicad/kicad/writer.py src/eda2kicad/validation/checks.py tests/kicad/test_writer.py tests/validation/test_checks.py
git commit -m "feat: emit kicad schematic and validate labels"
```

## 任务 7：添加转换服务和 CLI 入口

**文件：**
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\service.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\cli.py`
- 创建：`C:\dev\EDA2KiCad\tests\test_cli.py`

- [ ] **步骤 1：先写失败测试**

```python
# C:\dev\EDA2KiCad\tests\test_cli.py
from pathlib import Path

from typer.testing import CliRunner

from eda2kicad.cli import app


def test_cli_convert_writes_kicad_output(tmp_path: Path) -> None:
    input_file = tmp_path / "demo.txt"
    input_file.write_text(
        "RECORD=COMPONENT\nDESIGNATOR=R1\nLIBRARY=RES_0603\nVALUE=10k\nFOOTPRINT=Resistor_SMD:R_0603_1608Metric\n\nRECORD=NET_LABEL\nTEXT=NET_A\nX=100\nY=0\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"

    result = CliRunner().invoke(app, ["convert", str(input_file), "--output", str(output_dir)])

    assert result.exit_code == 0
    assert (output_dir / "demo.kicad_sch").exists()
    assert (output_dir / "report.json").exists()
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\test_cli.py -v`

预期：`eda2kicad.cli` 导入失败

- [ ] **步骤 3：写最小实现**

```python
# C:\dev\EDA2KiCad\src\eda2kicad\service.py
import json
from pathlib import Path

from eda2kicad.altium_ascii.parser import parse_ascii_schematic
from eda2kicad.kicad.writer import render_kicad_schematic
from eda2kicad.normalize.transform import parsed_records_to_project
from eda2kicad.paths import ensure_output_dir
from eda2kicad.symbols.resolver import resolve_symbol
from eda2kicad.validation.checks import validate_project


class ConversionService:
    def __init__(self, mapping_path: Path) -> None:
        self.mapping_path = mapping_path

    def convert_file(self, input_path: Path, output_dir: Path) -> dict[str, Path]:
        text = input_path.read_text(encoding="utf-8")
        parsed = parse_ascii_schematic(text)
        project = parsed_records_to_project(input_path.stem, parsed)
        resolved_symbols = {
            component.designator: resolve_symbol(component, self.mapping_path).library_id
            for component in project.sheets[0].components
        }
        report = validate_project(project)
        output_dir = ensure_output_dir(output_dir)
        (output_dir / f"{project.name}.kicad_sch").write_text(
            render_kicad_schematic(project, resolved_symbols),
            encoding="utf-8",
        )
        (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return {
            "schematic": output_dir / f"{project.name}.kicad_sch",
            "report": output_dir / "report.json",
        }
```

```python
# C:\dev\EDA2KiCad\src\eda2kicad\cli.py
from pathlib import Path

import typer

from eda2kicad.service import ConversionService


app = typer.Typer()


@app.command()
def convert(input_path: Path, output: Path = typer.Option(..., "--output")) -> None:
    service = ConversionService(Path("C:/dev/EDA2KiCad/libraries/local_symbol_map.json"))
    artifacts = service.convert_file(input_path, output)
    typer.echo(f"schematic={artifacts['schematic']}")
    typer.echo(f"report={artifacts['report']}")


if __name__ == "__main__":
    app()
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\test_cli.py -v`

预期：`1 passed`

- [ ] **步骤 5：提交**

```bash
git add src/eda2kicad/service.py src/eda2kicad/cli.py tests/test_cli.py
git commit -m "feat: add conversion service and cli entrypoint"
```

## 任务 8：建立多策略统一接口

**文件：**
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\strategies\base.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\strategies\custom_pipeline.py`
- 创建：`C:\dev\EDA2KiCad\tests\strategies\test_compare.py`

- [ ] **步骤 1：先写失败测试**

```python
# C:\dev\EDA2KiCad\tests\strategies\test_compare.py
from eda2kicad.strategies.base import StrategyResult
from eda2kicad.strategies.compare import compare_results


def test_compare_results_summarizes_three_strategies() -> None:
    results = [
        StrategyResult("custom", True, {"error_count": 0, "warning_count": 1}, {"net_label_ok": True}),
        StrategyResult("kicad-official", True, {"error_count": 0, "warning_count": 0}, {"net_label_ok": True}),
        StrategyResult("third-party", False, {"error_count": 1, "warning_count": 0}, {"net_label_ok": False}),
    ]

    summary = compare_results(results)

    assert summary["strategies"] == ["custom", "kicad-official", "third-party"]
    assert summary["success_count"] == 2
    assert summary["net_label_pass_count"] == 2
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\strategies\test_compare.py -v`

预期：`eda2kicad.strategies.base` 或 `eda2kicad.strategies.compare` 导入失败

- [ ] **步骤 3：写最小策略抽象**

```python
# C:\dev\EDA2KiCad\src\eda2kicad\strategies\base.py
from dataclasses import dataclass


@dataclass(slots=True)
class StrategyResult:
    strategy_id: str
    succeeded: bool
    report_summary: dict
    quality_signals: dict
```

```python
# C:\dev\EDA2KiCad\src\eda2kicad\strategies\compare.py
from eda2kicad.strategies.base import StrategyResult


def compare_results(results: list[StrategyResult]) -> dict:
    return {
        "strategies": [result.strategy_id for result in results],
        "success_count": sum(result.succeeded for result in results),
        "net_label_pass_count": sum(bool(result.quality_signals.get("net_label_ok")) for result in results),
    }
```

```python
# C:\dev\EDA2KiCad\src\eda2kicad\strategies\custom_pipeline.py
STRATEGY_ID = "custom"
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\strategies\test_compare.py -v`

预期：`1 passed`

- [ ] **步骤 5：提交**

```bash
git add src/eda2kicad/strategies/base.py src/eda2kicad/strategies/compare.py src/eda2kicad/strategies/custom_pipeline.py tests/strategies/test_compare.py
git commit -m "feat: add multi-strategy comparison primitives"
```

## 任务 9：接入 KiCad 官方能力辅助链路骨架

**文件：**
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\strategies\kicad_official.py`
- 修改：`C:\dev\EDA2KiCad\tests\strategies\test_compare.py`

- [ ] **步骤 1：先补失败测试**

```python
def test_kicad_official_strategy_exposes_metadata() -> None:
    from eda2kicad.strategies.kicad_official import get_strategy_metadata

    metadata = get_strategy_metadata()

    assert metadata["strategy_id"] == "kicad-official"
    assert metadata["mode"] == "candidate"
    assert metadata["uses_kicad_capability"] is True
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\strategies\test_compare.py -v`

预期：`eda2kicad.strategies.kicad_official` 导入失败

- [ ] **步骤 3：写最小 KiCad 官方链路骨架**

```python
# C:\dev\EDA2KiCad\src\eda2kicad\strategies\kicad_official.py
def get_strategy_metadata() -> dict:
    return {
        "strategy_id": "kicad-official",
        "mode": "candidate",
        "uses_kicad_capability": True,
        "status": "stubbed-until-kicad-capability-is-wired",
    }
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\strategies\test_compare.py -v`

预期：`2 passed`

- [ ] **步骤 5：提交**

```bash
git add src/eda2kicad/strategies/kicad_official.py tests/strategies/test_compare.py
git commit -m "feat: add kicad official strategy placeholder"
```

## 任务 10：接入第三方库链路骨架

**文件：**
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\strategies\third_party.py`
- 修改：`C:\dev\EDA2KiCad\tests\strategies\test_compare.py`

- [ ] **步骤 1：先补失败测试**

```python
def test_third_party_strategy_exposes_metadata() -> None:
    from eda2kicad.strategies.third_party import get_strategy_metadata

    metadata = get_strategy_metadata()

    assert metadata["strategy_id"] == "third-party"
    assert metadata["mode"] == "candidate"
    assert metadata["uses_external_project"] is True
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\strategies\test_compare.py -v`

预期：`eda2kicad.strategies.third_party` 导入失败

- [ ] **步骤 3：写最小第三方链路骨架**

```python
# C:\dev\EDA2KiCad\src\eda2kicad\strategies\third_party.py
def get_strategy_metadata() -> dict:
    return {
        "strategy_id": "third-party",
        "mode": "candidate",
        "uses_external_project": True,
        "status": "stubbed-until-third-party-integration-is-selected",
    }
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\strategies\test_compare.py -v`

预期：`3 passed`

- [ ] **步骤 5：提交**

```bash
git add src/eda2kicad/strategies/third_party.py tests/strategies/test_compare.py
git commit -m "feat: add third party strategy placeholder"
```

## 任务 11：在同一服务之上增加本地 Web 入口

**文件：**
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\web\app.py`
- 创建：`C:\dev\EDA2KiCad\src\eda2kicad\web\templates\index.html`
- 创建：`C:\dev\EDA2KiCad\tests\web\test_app.py`

- [ ] **步骤 1：先写失败测试**

```python
# C:\dev\EDA2KiCad\tests\web\test_app.py
from fastapi.testclient import TestClient

from eda2kicad.web.app import app


def test_web_home_page_loads() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Altium ASCII to KiCad" in response.text
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\web\test_app.py -v`

预期：`eda2kicad.web.app` 导入失败

- [ ] **步骤 3：写最小实现**

```python
# C:\dev\EDA2KiCad\src\eda2kicad\web\app.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


app = FastAPI(title="eda2kicad local web")
templates = Jinja2Templates(directory="C:/dev/EDA2KiCad/src/eda2kicad/web/templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "Altium ASCII to KiCad"})
```

```html
<!-- C:\dev\EDA2KiCad\src\eda2kicad\web\templates\index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{{ title }}</title>
  </head>
  <body>
    <h1>Altium ASCII to KiCad</h1>
    <p>Local conversion UI backed by the shared conversion service.</p>
  </body>
</html>
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\web\test_app.py -v`

预期：`1 passed`

- [ ] **步骤 5：提交**

```bash
git add src/eda2kicad/web/app.py src/eda2kicad/web/templates/index.html tests/web/test_app.py
git commit -m "feat: add local web shell"
```

## 任务 12：补齐多策略 Golden 覆盖和顶层使用文档

**文件：**
- 创建：`C:\dev\EDA2KiCad\tests\golden\test_end_to_end.py`
- 创建：`C:\dev\EDA2KiCad\tests\golden\test_strategy_comparison.py`
- 创建：`C:\dev\EDA2KiCad\tests\fixtures\golden\manifest.json`
- 创建：`C:\dev\EDA2KiCad\README.md`

- [ ] **步骤 1：先写失败测试和 manifest**

```json
// C:\dev\EDA2KiCad\tests\fixtures\golden\manifest.json
{
  "projects": [
    {
      "name": "minimal_ascii_demo",
      "input": "C:/dev/EDA2KiCad/tests/fixtures/altium_ascii/minimal_ascii_schematic.txt",
      "expected_report_errors": 0
    }
  ]
}
```

```python
# C:\dev\EDA2KiCad\tests\golden\test_end_to_end.py
import json
from pathlib import Path

from eda2kicad.service import ConversionService


def test_end_to_end_fixture_manifest(tmp_path: Path) -> None:
    manifest = json.loads(
        Path("C:/dev/EDA2KiCad/tests/fixtures/golden/manifest.json").read_text(encoding="utf-8")
    )
    service = ConversionService(Path("C:/dev/EDA2KiCad/libraries/local_symbol_map.json"))

    project = manifest["projects"][0]
    output_dir = tmp_path / project["name"]
    artifacts = service.convert_file(Path(project["input"]), output_dir)
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert artifacts["schematic"].exists()
    assert report["summary"]["error_count"] == project["expected_report_errors"]
```

```python
# C:\dev\EDA2KiCad\tests\golden\test_strategy_comparison.py
from eda2kicad.strategies.base import StrategyResult
from eda2kicad.strategies.compare import compare_results


def test_strategy_comparison_fixture_summary() -> None:
    summary = compare_results(
        [
            StrategyResult("custom", True, {"error_count": 0}, {"net_label_ok": True}),
            StrategyResult("kicad-official", True, {"error_count": 0}, {"net_label_ok": True}),
            StrategyResult("third-party", True, {"error_count": 1}, {"net_label_ok": False}),
        ]
    )

    assert summary["success_count"] == 3
    assert summary["net_label_pass_count"] == 2
```

- [ ] **步骤 2：运行测试，确认失败**

运行：`python -m pytest C:\dev\EDA2KiCad\tests\golden\test_end_to_end.py -v`

预期：缺少 manifest 或 `README.md` 仍未满足项目元数据引用

- [ ] **步骤 3：补齐 Golden 骨架和 README**

```markdown
# C:\dev\EDA2KiCad\README.md
# EDA2KiCad

Python tools for converting Altium ASCII schematic input into KiCad schematic output.

## Local development

```bash
python -m pytest -v
python -m eda2kicad.cli convert C:\path\to\input.txt --output C:\path\to\out
python -m uvicorn eda2kicad.web.app:app --reload
```

## Confirmed first-phase behavior

- Altium Designer ASCII schematic input
- single shared conversion core
- three candidate strategy paths: custom / kicad-official / third-party
- local library symbol mapping with private fallback
- KiCad schematic output plus `report.json`
- strategy comparison output for later quality ranking
```

- [ ] **步骤 4：运行完整测试集，确认纵向切片通过**

运行：`python -m pytest C:\dev\EDA2KiCad\tests -v`

预期：全部测试通过，包括 Golden 端到端测试

- [ ] **步骤 5：提交**

```bash
git add tests/golden/test_end_to_end.py tests/fixtures/golden/manifest.json README.md
git add tests/golden/test_strategy_comparison.py
git commit -m "test: add multi-strategy golden harness and docs"
```

## 自检

### 规格覆盖

- 已确认输入来源和输入格式：由任务 3、7、9 覆盖
- 共享转换核心、CLI 和本地 Web：由任务 7、11 覆盖
- 本地/自定义库优先：由任务 5 覆盖
- 必保字段：由任务 2、4 覆盖
- `net label` 正确性与致命语义错误：由任务 6、12 覆盖
- 多策略并行和质量对比：由任务 8、9、10、12 覆盖
- 机器可读报告与 Golden 基线：由任务 2、6、12 覆盖

### 明确保留在范围外的内容

- 多页支持当前不进入第一轮实现，因为需求仍未最终确认。
- `sheet symbol` / `bus` / `harness` / `channel` / 跨页 `port` 继续留在范围外，直到真实样例证明必须支持。
- 云端 API 故意延后；当前本地 Web 只用于证明共享应用边界。
- `KiCad` 官方能力链路和第三方库链路当前先落成可对比的候选接入点，不在本轮计划里完成深度集成。

### 占位符扫描结果

- 本计划中没有残留 `TODO` / `TBD` 标记。
- 每个任务都给出了明确文件、测试代码、运行命令和提交命令。
- 来自硬件团队的真实 Golden 样例已经通过固定 manifest 路径预留了接入形态，不需要改变测试结构。
