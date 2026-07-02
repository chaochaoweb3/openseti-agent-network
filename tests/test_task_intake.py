import json
from pathlib import Path

from osan.task_intake import check_tasks, main, score_task
from osan.validator import ValidationError


ROOT = Path(__file__).resolve().parents[1]


def load_demo_task():
    return json.loads((ROOT / "tasks" / "openseti-demo-001.json").read_text())


def test_current_tasks_pass_intake_rubric():
    reports = check_tasks(ROOT, [])

    assert {report["status"] for report in reports} == {"pass"}
    assert min(report["score"] for report in reports) >= 10


def test_empty_task_directory_fails(tmp_path):
    (tmp_path / "tasks").mkdir()

    try:
        check_tasks(tmp_path, [])
    except ValidationError as exc:
        assert "no task files" in str(exc)
    else:
        raise AssertionError("empty task directory should fail")


def test_low_score_task_fails_without_hard_rejection():
    task = load_demo_task()
    task.update(
        {
            "dataset_source": "named archive without citation",
            "source_license": "Custom Research Terms",
            "input_uri": "archive lookup required",
            "input_sha256": "manual-lookup",
            "objective": "Review this candidate.",
            "caveats": ["Needs care."],
            "review_questions": ["What should be checked?"],
            "expected_outputs": ["short_summary"],
        }
    )

    report = score_task(task)

    assert report["status"] == "fail"
    assert report["score"] < 10
    assert report["hard_rejections"] == []


def test_private_input_path_is_hard_rejected():
    task = load_demo_task()
    task["input_uri"] = "/Users/example/private/raw-candidate.json"

    report = score_task(task)

    assert report["status"] == "fail"
    assert "private local input path" in " ".join(report["hard_rejections"])


def test_cli_json_report(capsys):
    exit_code = main(["--root", str(ROOT), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    report = json.loads(captured.out)
    assert len(report["tasks"]) == 2
    assert {task["status"] for task in report["tasks"]} == {"pass"}
