"""
Live integration tests for automation commands against a real Netpicker
environment.

Prerequisites:
  1. Authenticate first:
       netpicker auth login --base-url <URL> --tenant <TENANT> --token <TOKEN>
  2. Run with:
       python -m pytest tests/integration/test_live_automation.py -v -s

These tests cover ALL 15 automation subcommands:
  - list-fixtures   – list available automation fixtures
  - list-jobs       – list automation jobs
  - store-job       – store an automation job
  - store-job-file  – store an automation job from a file
  - show-job        – get details of a specific automation job
  - delete-job      – delete an automation job
  - test-job        – test an automation job (debug)
  - execute-job     – execute an automation job
  - logs            – get job log report
  - show-log        – get details of a specific log entry
  - list-queue      – list queued jobs
  - store-queue     – store a queued job
  - show-queue      – get details of a specific queued job
  - delete-queue    – delete a queued job
  - review-queue    – review (approve/reject) a queued job

Commands whose API endpoints are functional are tested end-to-end.
Commands whose server endpoints return errors (store-job POST → 404,
execute-job POST → 500, store-queue POST → 404) verify that the CLI
handles errors gracefully.

To skip in CI: ``-m "not live"``
"""

import json
import pytest
from typer.testing import CliRunner
from netpicker_cli.cli import app

pytestmark = pytest.mark.live

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ensure_auth():
    """Verify credentials are configured before running any test."""
    result = runner.invoke(app, ["whoami", "--format", "json"])
    if result.exit_code != 0:
        pytest.skip(
            "Not authenticated — run `netpicker auth login` first.\n"
            f"  output: {result.output}"
        )
    return json.loads(result.output)


@pytest.fixture(scope="module")
def existing_job(ensure_auth):
    """Discover an existing automation job for read-only tests."""
    result = runner.invoke(app, [
        "automation", "list-jobs", "--format", "json", "--no-cache",
    ])
    assert result.exit_code == 0, f"list-jobs failed:\n{result.output}"
    jobs = json.loads(result.output)
    if not jobs:
        pytest.skip("No automation jobs in tenant")
    return jobs[0]


@pytest.fixture(scope="module")
def existing_log(ensure_auth):
    """Discover an existing log entry for read-only tests."""
    result = runner.invoke(app, [
        "automation", "logs", "--format", "json", "--size", "1",
    ])
    assert result.exit_code == 0, f"logs failed:\n{result.output}"
    logs = json.loads(result.output)
    if not logs:
        pytest.skip("No automation logs in tenant")
    return logs[0]


@pytest.fixture(scope="module")
def existing_queue_item(ensure_auth):
    """Discover an existing queue entry for read-only tests."""
    result = runner.invoke(app, [
        "automation", "list-queue", "--format", "json", "--size", "1",
    ])
    assert result.exit_code == 0, f"list-queue failed:\n{result.output}"
    items = json.loads(result.output)
    if not items:
        pytest.skip("No queue entries in tenant")
    return items[0]


# ---------------------------------------------------------------------------
# Tests — grouped by command
# ---------------------------------------------------------------------------

class TestListFixtures:
    """automation list-fixtures (GET /automation/{tenant}/fixtures)"""

    def test_01_list_fixtures_json(self, ensure_auth):
        """list-fixtures --format json returns a list of fixture names."""
        result = runner.invoke(app, [
            "automation", "list-fixtures", "--format", "json", "--no-cache",
        ])
        assert result.exit_code == 0, f"list-fixtures failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0, "no fixtures returned"
        # Fixtures may come as raw strings or {"fixture": name} dicts
        names = [
            (f["fixture"] if isinstance(f, dict) else f) for f in data
        ]
        assert any(n in names for n in ["device", "configuration", "commands"]), (
            f"expected standard fixtures, got: {names[:10]}"
        )

    def test_02_list_fixtures_table(self, ensure_auth):
        """list-fixtures in table format shows readable output."""
        result = runner.invoke(app, ["automation", "list-fixtures", "--no-cache"])
        assert result.exit_code == 0
        assert "fixture" in result.output.lower() or "device" in result.output.lower()


class TestListJobs:
    """automation list-jobs (GET /automation/{tenant}/job)"""

    def test_03_list_jobs_json(self, ensure_auth):
        """list-jobs --format json returns a list of job objects."""
        result = runner.invoke(app, [
            "automation", "list-jobs", "--format", "json", "--no-cache",
        ])
        assert result.exit_code == 0, f"list-jobs failed:\n{result.output}"
        jobs = json.loads(result.output)
        assert isinstance(jobs, list)
        assert len(jobs) > 0, "no jobs returned"
        first = jobs[0]
        assert "name" in first, f"job missing 'name' key: {list(first.keys())}"

    def test_04_list_jobs_table(self, ensure_auth):
        """list-jobs in table format shows column headers."""
        result = runner.invoke(app, ["automation", "list-jobs", "--no-cache"])
        assert result.exit_code == 0
        lower = result.output.lower()
        assert "available jobs" in lower or "name" in lower

    def test_05_list_jobs_pattern(self, ensure_auth, existing_job):
        """list-jobs --pattern filters jobs by name."""
        name = existing_job["name"]
        result = runner.invoke(app, [
            "automation", "list-jobs", "--pattern", name,
            "--format", "json", "--no-cache",
        ])
        assert result.exit_code == 0
        filtered = json.loads(result.output)
        assert isinstance(filtered, list)
        assert len(filtered) >= 1
        assert any(j["name"] == name for j in filtered)


class TestShowJob:
    """automation show-job (GET /automation/{tenant}/job/{name})"""

    def test_06_show_job_json(self, ensure_auth, existing_job):
        """show-job <name> --format json returns job details with source."""
        name = existing_job["name"]
        result = runner.invoke(app, [
            "automation", "show-job", name, "--format", "json",
        ])
        assert result.exit_code == 0, f"show-job failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "jobs" in data or "sources" in data, (
            f"expected 'jobs' or 'sources' keys, got: {list(data.keys())}"
        )

    def test_07_show_job_table(self, ensure_auth, existing_job):
        """show-job <name> in table format shows readable output."""
        name = existing_job["name"]
        result = runner.invoke(app, ["automation", "show-job", name])
        assert result.exit_code == 0
        lower = result.output.lower()
        assert "job:" in lower or name.lower() in lower

    def test_08_show_job_not_found(self, ensure_auth):
        """show-job with non-existent name handles error gracefully."""
        result = runner.invoke(app, [
            "automation", "show-job", "nonexistent_pytest_xyz_999",
        ])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestStoreJob:
    """automation store-job (POST /automation/{tenant}/job)

    Note: The server API does not currently support POST for job creation.
    These tests verify the CLI handles the API error gracefully.
    """

    def test_09_store_job_graceful_error(self, ensure_auth):
        """store-job should handle API rejection gracefully."""
        result = runner.invoke(app, [
            "automation", "store-job",
            "--name", "pytest_store_test",
            "--sources", "default.py:def test(device): pass",
            "--format", "json",
        ])
        # Accept either success (if server is fixed) or graceful error exit
        if result.exit_code == 0:
            data = json.loads(result.output)
            assert data  # created successfully
        else:
            assert result.exit_code == 1
            assert "error" in result.output.lower()


class TestStoreJobFile:
    """automation store-job-file (POST /automation/{tenant}/job from file)"""

    def test_10_store_job_file_missing_file(self, ensure_auth):
        """store-job-file with non-existent file exits with error."""
        result = runner.invoke(app, [
            "automation", "store-job-file",
            "--name", "pytest_store_file_test",
            "--file", "/tmp/nonexistent_pytest_file_xyz.py",
        ])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_11_store_job_file_graceful_error(self, ensure_auth, tmp_path):
        """store-job-file with a real file handles API errors gracefully."""
        # Create a temporary source file
        src = tmp_path / "test_job.py"
        src.write_text("def test_hello(device):\n    print('hello')\n")

        result = runner.invoke(app, [
            "automation", "store-job-file",
            "--name", "pytest_store_file_test",
            "--file", str(src),
            "--format", "json",
        ])
        if result.exit_code == 0:
            data = json.loads(result.output)
            assert data
        else:
            assert result.exit_code == 1
            assert "error" in result.output.lower()


class TestDeleteJob:
    """automation delete-job (DELETE /automation/{tenant}/job/{name})"""

    def test_12_delete_job_not_found(self, ensure_auth):
        """delete-job with non-existent name handles error gracefully."""
        result = runner.invoke(app, [
            "automation", "delete-job", "nonexistent_pytest_xyz_999",
        ])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestTestJob:
    """automation test-job (POST /automation/{tenant}/debug)"""

    def test_13_test_job_json(self, ensure_auth, existing_job):
        """test-job --format json returns debug results."""
        name = existing_job["name"]
        result = runner.invoke(app, [
            "automation", "test-job",
            "--name", name,
            "--format", "json",
        ])
        assert result.exit_code == 0, f"test-job failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, dict)
        # Debug response has specific keys
        assert "nodeid" in data or "status" in data, (
            f"unexpected debug response keys: {list(data.keys())}"
        )

    def test_14_test_job_table(self, ensure_auth, existing_job):
        """test-job in table format shows readable debug output."""
        name = existing_job["name"]
        result = runner.invoke(app, [
            "automation", "test-job", "--name", name,
        ])
        assert result.exit_code == 0
        lower = result.output.lower()
        assert "status" in lower or "node" in lower or "test results" in lower


class TestExecuteJob:
    """automation execute-job (POST /automation/{tenant}/execute)

    Note: This endpoint currently returns 500 on the dev server.
    Tests verify the CLI handles the error gracefully.
    """

    def test_15_execute_job_graceful_error(self, ensure_auth, existing_job):
        """execute-job should handle server errors gracefully."""
        name = existing_job["name"]
        result = runner.invoke(app, [
            "automation", "execute-job",
            "--name", name,
            "--format", "json",
        ])
        # Accept either success (if server is fixed) or graceful error exit
        if result.exit_code == 0:
            # Execution succeeded
            assert len(result.output.strip()) > 0
        else:
            assert result.exit_code == 1
            assert "error" in result.output.lower()


class TestLogs:
    """automation logs (GET /automation/{tenant}/logs)"""

    def test_16_logs_json(self, ensure_auth):
        """logs --format json returns paginated log entries."""
        result = runner.invoke(app, [
            "automation", "logs", "--format", "json", "--size", "5",
        ])
        assert result.exit_code == 0, f"logs failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0, "no log entries returned"
        first = data[0]
        assert "id" in first, f"log entry missing 'id' key: {list(first.keys())}"

    def test_17_logs_table(self, ensure_auth):
        """logs in table format shows readable output."""
        result = runner.invoke(app, [
            "automation", "logs", "--size", "5",
        ])
        assert result.exit_code == 0
        lower = result.output.lower()
        assert "log" in lower or "job" in lower or "id" in lower

    def test_18_logs_with_job_filter(self, ensure_auth, existing_log):
        """logs --job-name filters results by job name."""
        job_name = existing_log.get("job", existing_log.get("job_name", ""))
        if not job_name:
            pytest.skip("Log entry has no job name")

        result = runner.invoke(app, [
            "automation", "logs",
            "--job-name", job_name,
            "--format", "json", "--size", "5",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        # Filtered results should contain the specified job
        if data:
            assert any(
                entry.get("job") == job_name or entry.get("job_name") == job_name
                for entry in data
            )

    def test_19_logs_pagination(self, ensure_auth):
        """logs --page --size params control pagination."""
        result = runner.invoke(app, [
            "automation", "logs",
            "--page", "1", "--size", "2",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) <= 2


class TestShowLog:
    """automation show-log (GET /automation/{tenant}/logs/{id})"""

    def test_20_show_log_json(self, ensure_auth, existing_log):
        """show-log <id> --format json returns log entry details."""
        log_id = existing_log["id"]
        result = runner.invoke(app, [
            "automation", "show-log", log_id, "--format", "json",
        ])
        assert result.exit_code == 0, f"show-log failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert data.get("id") == log_id

    def test_21_show_log_table(self, ensure_auth, existing_log):
        """show-log <id> in table format shows readable output."""
        log_id = existing_log["id"]
        result = runner.invoke(app, ["automation", "show-log", log_id])
        assert result.exit_code == 0
        lower = result.output.lower()
        assert "log entry" in lower or "job" in lower or log_id in result.output

    def test_22_show_log_not_found(self, ensure_auth):
        """show-log with non-existent ID handles error gracefully."""
        result = runner.invoke(app, [
            "automation", "show-log", "nonexistent_log_xyz_999",
        ])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()


class TestListQueue:
    """automation list-queue (GET /automation/{tenant}/queue)"""

    def test_23_list_queue_json(self, ensure_auth):
        """list-queue --format json returns paginated queue entries."""
        result = runner.invoke(app, [
            "automation", "list-queue", "--format", "json", "--size", "5",
        ])
        assert result.exit_code == 0, f"list-queue failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, list)
        # Queue may be empty or have entries
        if data:
            first = data[0]
            assert "id" in first, f"queue entry missing 'id': {list(first.keys())}"

    def test_24_list_queue_table(self, ensure_auth):
        """list-queue in table format shows readable output."""
        result = runner.invoke(app, ["automation", "list-queue", "--size", "5"])
        assert result.exit_code == 0
        # Table output contains queue entries or "No queued jobs"
        lower = result.output.lower()
        assert (
            "queued" in lower or "queue" in lower
            or "id" in lower or "job" in lower
            or "no queued" in lower
        )

    def test_25_list_queue_pagination(self, ensure_auth):
        """list-queue respects --page --size pagination params."""
        result = runner.invoke(app, [
            "automation", "list-queue",
            "--page", "1", "--size", "2",
            "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) <= 2


class TestShowQueue:
    """automation show-queue (GET /automation/{tenant}/queue/{id})"""

    def test_26_show_queue_json(self, ensure_auth, existing_queue_item):
        """show-queue <id> --format json returns queue entry details."""
        qid = existing_queue_item["id"]
        result = runner.invoke(app, [
            "automation", "show-queue", qid, "--format", "json",
        ])
        assert result.exit_code == 0, f"show-queue failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert data.get("id") == qid

    def test_27_show_queue_table(self, ensure_auth, existing_queue_item):
        """show-queue <id> in table format shows readable output."""
        qid = existing_queue_item["id"]
        result = runner.invoke(app, ["automation", "show-queue", qid])
        assert result.exit_code == 0
        lower = result.output.lower()
        assert "queued job" in lower or "job" in lower or qid in result.output

    def test_28_show_queue_not_found(self, ensure_auth):
        """show-queue with non-existent ID handles error gracefully."""
        result = runner.invoke(app, [
            "automation", "show-queue", "nonexistent_queue_xyz_999",
        ])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()


class TestStoreQueue:
    """automation store-queue (POST /automation/{tenant}/queue)

    Note: The server API does not currently support POST for queue creation
    via REST. Tests verify the CLI handles the error gracefully.
    """

    def test_29_store_queue_graceful_error(self, ensure_auth):
        """store-queue should handle API rejection gracefully."""
        result = runner.invoke(app, [
            "automation", "store-queue",
            "--name", "add_bgp_prefix",
            "--sources", "default.py:def test(device): pass",
            "--format", "json",
        ])
        if result.exit_code == 0:
            data = json.loads(result.output)
            assert data
        else:
            assert result.exit_code == 1
            assert "error" in result.output.lower()


class TestDeleteQueue:
    """automation delete-queue (DELETE /automation/{tenant}/queue/{id})"""

    def test_30_delete_queue_not_found(self, ensure_auth):
        """delete-queue with non-existent ID handles error gracefully."""
        result = runner.invoke(app, [
            "automation", "delete-queue", "nonexistent_queue_xyz_999",
        ])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()


class TestReviewQueue:
    """automation review-queue (POST /automation/{tenant}/queue/{id}/review)"""

    def test_31_review_queue_not_found(self, ensure_auth):
        """review-queue with non-existent ID handles error gracefully."""
        result = runner.invoke(app, [
            "automation", "review-queue", "nonexistent_queue_xyz_999",
            "--approved", "true",
        ])
        assert result.exit_code == 1
        assert "error" in result.output.lower() or "not found" in result.output.lower()

    def test_32_review_queue_invalid_approved(self, ensure_auth):
        """review-queue with invalid --approved value exits with error."""
        result = runner.invoke(app, [
            "automation", "review-queue", "12345",
            "--approved", "maybe",
        ])
        assert result.exit_code == 1
        assert "true" in result.output.lower() or "false" in result.output.lower()
