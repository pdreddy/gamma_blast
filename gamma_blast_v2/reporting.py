from datetime import datetime
from pathlib import Path

import pandas as pd


OPTION_UNAVAILABLE = "Option-premium backtest unavailable: no historical option data"


def _markdown_table(frame):
    if frame.empty:
        return "_No rows._"
    values = frame.fillna("").astype(str)
    header = "| " + " | ".join(values.columns) + " |"
    rule = "| " + " | ".join("---" for _ in values.columns) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in values.itertuples(index=False, name=None)]
    return "\n".join([header, rule, *rows])


def write_research_report(comparison, slices, option_results=None, directory="reports"):
    """Persist honest research output; never substitutes underlying returns for option P&L."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = target / f"gamma_blast_v2_{stamp}"
    combined = pd.concat(
        [comparison.assign(report_section="comparison"), slices.assign(report_section="slices")],
        ignore_index=True, sort=False,
    )
    combined.to_csv(base.with_suffix(".csv"), index=False)
    lines = ["# Gamma Blast v2 research report", "", "## v1 vs v2", "",
             _markdown_table(comparison), "", "## Option-premium mode", ""]
    if option_results is None:
        lines.append(OPTION_UNAVAILABLE)
    else:
        lines.extend([_markdown_table(option_results)])
    lines.extend(["", "## Diagnostic slices", "", _markdown_table(slices)])
    base.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    return base.with_suffix(".csv"), base.with_suffix(".md")
