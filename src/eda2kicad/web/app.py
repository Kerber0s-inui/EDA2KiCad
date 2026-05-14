from pathlib import Path
import tempfile

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from eda2kicad.service import ConversionService

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

app = FastAPI(title="eda2kicad local web")

_STRATEGY_ORDER = [
    "pcbnew-api",
    "kicad-gui-official",
    "kicad-official",
    "third-party",
    "custom",
]

_STRATEGY_SUMMARIES = {
    "pcbnew-api": {
        "label": "pcbnew API 导入",
        "summary": "支持 PCB 图，效果较好，未来可能不再支持。",
        "tag": "API",
    },
    "kicad-gui-official": {
        "label": "KiCad GUI 自动导入",
        "summary": "支持原理图、PCB 图，效果较好，但稳定性差，不适合作为长期策略。",
        "tag": "GUI",
    },
    "kicad-official": {
        "label": "KiCad 官方导入",
        "summary": "支持 PCB 图，暂不可用，理论最佳策略，需等待官方进一步支持。",
        "tag": "官方",
    },
    "third-party": {
        "label": "第三方转换",
        "summary": "来源：altium2kicad。支持原理图、PCB 图，原理图效果差，PCB 效果较好。",
        "tag": "第三方",
    },
    "custom": {
        "label": "自研策略",
        "summary": "支持原理图，效果极差，待开发。",
        "tag": "自研",
    },
}


def _default_mapping_path() -> Path:
    return Path(__file__).resolve().parents[3] / "libraries" / "local_symbol_map.json"


def _service() -> ConversionService:
    return ConversionService(_default_mapping_path())


def _strategy_sort_key(strategy_id: str) -> tuple[int, str]:
    try:
        return (_STRATEGY_ORDER.index(strategy_id), strategy_id)
    except ValueError:
        return (len(_STRATEGY_ORDER), strategy_id)


def _strategy_cards(service: ConversionService) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    strategies = sorted(service.available_strategies(), key=lambda item: _strategy_sort_key(str(item["strategy_id"])))
    for strategy in strategies:
        summary = _STRATEGY_SUMMARIES.get(
            str(strategy["strategy_id"]),
            {
                "label": str(strategy["strategy_id"]),
                "summary": "未配置说明。",
                "tag": "通用",
            },
        )
        cards.append(
            {
                **strategy,
                "label": summary["label"],
                "summary": summary["summary"],
                "tag": summary["tag"],
            }
        )
    return cards


def _render_index(
    request: Request,
    service: ConversionService,
    *,
    strategy: str = "custom",
    result: dict[str, object] | None = None,
    message: str | None = None,
    message_kind: str | None = None,
    reset_url_to_root: bool = False,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "Altium 转 KiCad",
            "strategies": _strategy_cards(service),
            "result": result,
            "message": message,
            "message_kind": message_kind,
            "default_strategy": strategy,
            "reset_url_to_root": reset_url_to_root,
        },
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
def read_index(request: Request) -> HTMLResponse:
    service = _service()
    return _render_index(request, service)


@app.post("/convert", response_class=HTMLResponse)
async def convert(request: Request) -> HTMLResponse:
    form = await request.form()
    service = _service()

    output_dir_value = str(form.get("output_dir", "")).strip()
    if not output_dir_value:
        return _render_index(
            request,
            service,
            message="转换失败：output_dir 不能为空",
            message_kind="error",
            reset_url_to_root=True,
            status_code=400,
        )
    output_dir = Path(output_dir_value)

    strategy = str(form.get("strategy", "custom"))
    uploaded_file = form.get("input_file")

    try:
        if uploaded_file is not None and getattr(uploaded_file, "filename", ""):
            with tempfile.TemporaryDirectory(prefix="eda2kicad-upload-") as staging_dir:
                staged_path = Path(staging_dir) / Path(uploaded_file.filename).name
                staged_path.write_bytes(await uploaded_file.read())
                artifacts = service.convert_file(staged_path, output_dir, strategy=strategy)
        else:
            input_path_value = str(form.get("input_path", "")).strip()
            if not input_path_value:
                return _render_index(
                    request,
                    service,
                    message="转换失败：缺少 input_path 或 output_dir",
                    message_kind="error",
                    reset_url_to_root=True,
                    status_code=400,
                )
            artifacts = service.convert_file(Path(input_path_value), output_dir, strategy=strategy)
    except ValueError as exc:
        return _render_index(
            request,
            service,
            strategy=strategy,
            message=f"转换失败：{exc}",
            message_kind="error",
            reset_url_to_root=True,
            status_code=400,
        )
    except Exception as exc:
        return _render_index(
            request,
            service,
            strategy=strategy,
            message=f"转换失败：内部错误 {type(exc).__name__}: {exc}",
            message_kind="error",
            reset_url_to_root=True,
            status_code=500,
        )

    return _render_index(
        request,
        service,
        strategy=strategy,
        result={
            "strategy": strategy,
            "job_dir": str(artifacts["job_dir"]),
            "schematic": str(artifacts["schematic"]) if "schematic" in artifacts else None,
            "board": str(artifacts["board"]) if "board" in artifacts else None,
            "project": str(artifacts["project"]) if "project" in artifacts else None,
            "report": str(artifacts["report"]),
        },
        message="转换成功",
        message_kind="success",
        reset_url_to_root=True,
    )
