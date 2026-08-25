from app.models import Decision, Resolution
from tests.helpers import make_storage


def test_export_includes_resolution_columns(tmp_path):
    storage = make_storage(tmp_path)
    from tests.helpers import submission

    storage.save_submissions("DS07", [submission()])
    storage.upsert_resolution(
        Resolution(
            assignment_id="DS07",
            team_id="T01",
            decision=Decision.CONFIRMED.value,
            penalty_points="2",
            reason="duration changed since baseline",
        )
    )
    rows = storage.export_rows("DS07")
    assert rows[0]["resolution"] == "confirmed"
    assert rows[0]["penalty_points"] == "2"
    path = storage.write_export("DS07")
    text = path.read_text(encoding="utf-8")
    assert "penalty_points" in text.splitlines()[0]
    assert "confirmed" in text
