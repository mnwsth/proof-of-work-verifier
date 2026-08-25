"""Assignment-scoped filesystem storage. No database."""

from __future__ import annotations

from pathlib import Path

from app.config import AssignmentConfig, dump_yaml, load_yaml
from app.models import (
    BASELINE_FIELDS,
    EXPORT_FIELDS,
    RESOLUTION_FIELDS,
    RESULT_FIELDS,
    ROSTER_FIELDS,
    SUBMISSION_FIELDS,
    BaselineRow,
    CheckMetadata,
    Resolution,
    RosterEntry,
    Submission,
    VerificationResult,
)
from app.utils import (
    atomic_write_json,
    check_folder_name,
    format_iso,
    now_tz,
    parse_iso,
    read_csv,
    read_json,
    safe_assignment_id,
    write_csv,
)


class BaselineExistsError(RuntimeError):
    pass


class Storage:
    def __init__(self, data_root: Path):
        self.data_root = data_root
        self.data_root.mkdir(parents=True, exist_ok=True)

    def assignment_dir(self, assignment_id: str) -> Path:
        return self.data_root / safe_assignment_id(assignment_id)

    def list_assignment_ids(self) -> list[str]:
        if not self.data_root.exists():
            return []
        ids = []
        for path in sorted(self.data_root.iterdir()):
            if path.is_dir() and (path / "assignment.yaml").exists():
                ids.append(path.name)
        return ids

    def find_assignment_id_for_coursework(self, course_id: str, coursework_id: str) -> str | None:
        if not course_id or not coursework_id:
            return None
        for assignment_id in self.list_assignment_ids():
            config = self.load_assignment(assignment_id)
            if config.google_course_id == course_id and config.google_coursework_id == coursework_id:
                return assignment_id
        return None

    def create_assignment(self, config: AssignmentConfig) -> Path:
        directory = self.assignment_dir(config.assignment_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "checks").mkdir(exist_ok=True)
        dump_yaml(directory / "assignment.yaml", config.model_dump())
        for name, fields in [
            ("roster.csv", ROSTER_FIELDS),
            ("submissions.csv", SUBMISSION_FIELDS),
            ("baseline.csv", BASELINE_FIELDS),
            ("resolutions.csv", RESOLUTION_FIELDS),
        ]:
            path = directory / name
            if not path.exists():
                write_csv(path, fields, [])
        return directory

    def load_assignment(self, assignment_id: str) -> AssignmentConfig:
        path = self.assignment_dir(assignment_id) / "assignment.yaml"
        return AssignmentConfig.model_validate(load_yaml(path))

    def save_assignment(self, config: AssignmentConfig) -> None:
        dump_yaml(self.assignment_dir(config.assignment_id) / "assignment.yaml", config.model_dump())

    def load_roster(self, assignment_id: str) -> list[RosterEntry]:
        rows = read_csv(self.assignment_dir(assignment_id) / "roster.csv")
        return [RosterEntry.model_validate(row) for row in rows]

    def save_roster(self, assignment_id: str, rows: list[RosterEntry]) -> None:
        write_csv(
            self.assignment_dir(assignment_id) / "roster.csv",
            ROSTER_FIELDS,
            [row.model_dump() for row in rows],
        )

    def load_submissions(self, assignment_id: str) -> list[Submission]:
        rows = read_csv(self.assignment_dir(assignment_id) / "submissions.csv")
        parsed = []
        for row in rows:
            if row.get("classroom_late") in ("true", "false"):
                row["classroom_late"] = row["classroom_late"] == "true"
            elif row.get("classroom_late") == "":
                row["classroom_late"] = None
            parsed.append(Submission.model_validate(row))
        return parsed

    def save_submissions(self, assignment_id: str, rows: list[Submission]) -> None:
        write_csv(
            self.assignment_dir(assignment_id) / "submissions.csv",
            SUBMISSION_FIELDS,
            [row.model_dump() for row in rows],
        )

    def load_baselines(self, assignment_id: str) -> list[BaselineRow]:
        rows = read_csv(self.assignment_dir(assignment_id) / "baseline.csv")
        return [BaselineRow.model_validate(row) for row in rows]

    def baseline_by_team(self, assignment_id: str) -> dict[str, BaselineRow]:
        return {row.team_id: row for row in self.load_baselines(assignment_id)}

    def has_complete_baseline(self, assignment_id: str) -> bool:
        rows = self.load_baselines(assignment_id)
        return bool(rows) and all(row.is_complete() for row in rows)

    def has_any_baseline(self, assignment_id: str) -> bool:
        return bool(self.load_baselines(assignment_id))

    def incomplete_baseline_teams(self, assignment_id: str) -> list[str]:
        return [row.team_id for row in self.load_baselines(assignment_id) if not row.is_complete()]

    def save_baselines(
        self,
        assignment_id: str,
        rows: list[BaselineRow],
        *,
        allow_create: bool = False,
        complete_incomplete: bool = False,
    ) -> None:
        existing = self.baseline_by_team(assignment_id)
        if existing and not allow_create and not complete_incomplete:
            raise BaselineExistsError("Baseline already exists; refusing to overwrite")
        if existing and complete_incomplete:
            merged = dict(existing)
            for row in rows:
                current = merged.get(row.team_id)
                if current is None:
                    continue
                if current.is_complete():
                    continue
                merged[row.team_id] = row
            rows = list(merged.values())
        elif existing and not allow_create:
            raise BaselineExistsError("Baseline already exists; refusing to overwrite")
        write_csv(
            self.assignment_dir(assignment_id) / "baseline.csv",
            BASELINE_FIELDS,
            [row.model_dump() for row in rows],
        )

    def load_resolutions(self, assignment_id: str) -> list[Resolution]:
        rows = read_csv(self.assignment_dir(assignment_id) / "resolutions.csv")
        return [Resolution.model_validate(row) for row in rows]

    def upsert_resolution(self, resolution: Resolution) -> None:
        rows = {row.team_id: row for row in self.load_resolutions(resolution.assignment_id)}
        rows[resolution.team_id] = resolution
        write_csv(
            self.assignment_dir(resolution.assignment_id) / "resolutions.csv",
            RESOLUTION_FIELDS,
            [row.model_dump() for row in rows.values()],
        )

    def create_check_dir(self, assignment_id: str, tz_name: str, when=None) -> Path:
        stamp = check_folder_name(when or now_tz(tz_name))
        path = self.assignment_dir(assignment_id) / "checks" / stamp
        extra = 0
        while path.exists():
            extra += 1
            path = self.assignment_dir(assignment_id) / "checks" / f"{stamp}_{extra}"
        (path / "raw").mkdir(parents=True)
        return path

    def write_check_metadata(self, check_dir: Path, metadata: CheckMetadata) -> None:
        atomic_write_json(check_dir / "metadata.json", metadata.model_dump())

    def write_check_results(self, check_dir: Path, results: list[VerificationResult]) -> None:
        write_csv(
            check_dir / "results.csv",
            RESULT_FIELDS,
            [result.model_dump() for result in results],
        )

    def write_raw(self, check_dir: Path, team_id: str, payload: object) -> None:
        safe = safe_assignment_id(team_id)
        atomic_write_json(check_dir / "raw" / f"{safe}.json", payload)

    def list_checks(self, assignment_id: str) -> list[dict]:
        checks_root = self.assignment_dir(assignment_id) / "checks"
        if not checks_root.exists():
            return []
        items = []
        for path in sorted(checks_root.iterdir()):
            if not path.is_dir():
                continue
            meta = read_json(path / "metadata.json")
            items.append(
                {
                    "timestamp": path.name,
                    "path": path,
                    "status": meta.get("status", "unknown"),
                    "kind": meta.get("kind", "verification"),
                    "started_at": meta.get("started_at", ""),
                    "completed_at": meta.get("completed_at", ""),
                    "green": meta.get("green", 0),
                    "yellow": meta.get("yellow", 0),
                    "red": meta.get("red", 0),
                    "error": meta.get("error", 0),
                    "metadata": meta,
                }
            )
        return items

    def latest_completed_verification(self, assignment_id: str) -> dict | None:
        completed = [
            item
            for item in self.list_checks(assignment_id)
            if item["status"] == "completed" and item.get("kind") != "baseline"
        ]
        return completed[-1] if completed else None

    def load_results(self, assignment_id: str, timestamp: str) -> list[dict[str, str]]:
        path = self.assignment_dir(assignment_id) / "checks" / safe_assignment_id(timestamp) / "results.csv"
        return read_csv(path)

    def load_result_for_team(self, assignment_id: str, timestamp: str, team_id: str) -> dict[str, str] | None:
        for row in self.load_results(assignment_id, timestamp):
            if row.get("team_id") == team_id:
                return row
        return None

    def baseline_captured_at(self, assignment_id: str) -> str:
        rows = self.load_baselines(assignment_id)
        times = [parse_iso(row.baseline_captured_at) for row in rows if row.baseline_captured_at]
        times = [item for item in times if item is not None]
        if not times:
            return ""
        return format_iso(min(times))

    def export_rows(self, assignment_id: str) -> list[dict]:
        submissions = {row.team_id: row for row in self.load_submissions(assignment_id)}
        baselines = self.baseline_by_team(assignment_id)
        resolutions = {row.team_id: row for row in self.load_resolutions(assignment_id)}
        latest = self.latest_completed_verification(assignment_id)
        latest_results = {
            row["team_id"]: row
            for row in (self.load_results(assignment_id, latest["timestamp"]) if latest else [])
        }
        rows = []
        for team_id, submission in submissions.items():
            baseline = baselines.get(team_id)
            resolution = resolutions.get(team_id)
            result = latest_results.get(team_id, {})
            rows.append(
                {
                    "team_id": team_id,
                    "team_name": submission.team_name,
                    "submitted_at": submission.submitted_at,
                    "youtube_url": submission.youtube_url,
                    "video_id": submission.video_id,
                    "baseline_captured_at": baseline.baseline_captured_at if baseline else "",
                    "last_verified_at": result.get("verification_time", ""),
                    "status": result.get("status", submission.current_status),
                    "events": result.get("event_codes", ""),
                    "resolution": resolution.decision if resolution else "",
                    "penalty_points": resolution.penalty_points if resolution else "",
                    "resolution_reason": resolution.reason if resolution else "",
                }
            )
        return rows

    def write_export(self, assignment_id: str, dest: Path | None = None) -> Path:
        path = dest or (self.assignment_dir(assignment_id) / "export.csv")
        write_csv(path, EXPORT_FIELDS, self.export_rows(assignment_id))
        return path
