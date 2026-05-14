from pathlib import Path

import typer

from eda2kicad.service import ConversionService


app = typer.Typer()


def _default_mapping_path() -> Path:
    return Path(__file__).resolve().parents[2] / "libraries" / "local_symbol_map.json"


@app.callback()
def main() -> None:
    return None


@app.command()
def convert(
    input_path: Path,
    output: Path = typer.Option(..., "--output"),
    strategy: str = typer.Option("custom", "--strategy"),
) -> None:
    service = ConversionService(_default_mapping_path())
    try:
        artifacts = service.convert_file(input_path, output, strategy=strategy)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--strategy") from exc
    typer.echo(f"strategy={strategy}")
    if "schematic" in artifacts:
        typer.echo(f"schematic={artifacts['schematic']}")
    if "board" in artifacts:
        typer.echo(f"board={artifacts['board']}")
    typer.echo(f"report={artifacts['report']}")


if __name__ == "__main__":
    app()
