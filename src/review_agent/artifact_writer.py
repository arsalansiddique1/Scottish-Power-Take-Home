import csv
import json
from pathlib import Path

from review_agent.models import Finding


class ArtifactWriter:
    def __init__(self, output_dir: str | Path = "artifacts") -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        findings: list[Finding],
        summary_comment: str,
        run_metadata: dict[str, str],
    ) -> dict[str, str]:
        findings_path = self._output_dir / "findings.jsonl"
        summary_path = self._output_dir / "summary.json"
        metrics_path = self._output_dir / "metrics.csv"

        self._write_findings_jsonl(findings_path, findings)
        self._write_summary_json(summary_path, summary_comment, run_metadata, findings)
        self._write_metrics_csv(metrics_path, findings, run_metadata)

        return {
            "findings_jsonl": str(findings_path),
            "summary_json": str(summary_path),
            "metrics_csv": str(metrics_path),
        }

    def _write_findings_jsonl(self, path: Path, findings: list[Finding]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for finding in findings:
                handle.write(json.dumps(finding.model_dump(), ensure_ascii=True))
                handle.write("\n")

    def _write_summary_json(
        self,
        path: Path,
        summary_comment: str,
        run_metadata: dict[str, str],
        findings: list[Finding],
    ) -> None:
        payload = {
            "summary_comment": summary_comment,
            "run_metadata": run_metadata,
            "total_findings": len(findings),
        }
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _write_metrics_csv(
        self,
        path: Path,
        findings: list[Finding],
        run_metadata: dict[str, str],
    ) -> None:
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_source = {"static": 0, "llm": 0}
        for finding in findings:
            by_severity[finding.severity] += 1
            by_source[finding.source] += 1

        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "run_id",
                    "head_sha",
                    "total_findings",
                    "critical",
                    "high",
                    "medium",
                    "low",
                    "static",
                    "llm",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "run_id": run_metadata.get("run_id", ""),
                    "head_sha": run_metadata.get("head_sha", ""),
                    "total_findings": len(findings),
                    "critical": by_severity["critical"],
                    "high": by_severity["high"],
                    "medium": by_severity["medium"],
                    "low": by_severity["low"],
                    "static": by_source["static"],
                    "llm": by_source["llm"],
                }
            )
