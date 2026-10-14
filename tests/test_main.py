import json
import logging

from main import (
    ErrorCategory,
    SyncStatus,
    UserSyncResult,
    categorize_error,
    determine_sync_exit_code,
    log_json,
)
from src.utils.constants import (
    EXIT_CODE_PARTIAL_FAILURE,
    EXIT_CODE_SUCCESS,
    EXIT_CODE_TOTAL_FAILURE,
)


def test_rejected_dietly_login_is_auth_not_transient():
    # A transient category triggers per-user retries, which hammered Dietly's
    # login into 429s when it started demanding a CSRF token.
    msg = "Login failed - credentials rejected or Dietly auth flow changed"
    assert categorize_error(msg) == ErrorCategory.AUTH


def test_server_errors_are_transient():
    assert categorize_error("HTTP 503 error: upstream") == ErrorCategory.TRANSIENT
    assert categorize_error("Read timeout") == ErrorCategory.TRANSIENT


def _result(status):
    return UserSyncResult("u", status, "msg")


def test_exit_codes():
    ok, failed = _result(SyncStatus.SUCCESS), _result(SyncStatus.FAILED)
    assert determine_sync_exit_code([ok, ok]) == EXIT_CODE_SUCCESS
    assert determine_sync_exit_code([ok, failed]) == EXIT_CODE_PARTIAL_FAILURE
    assert determine_sync_exit_code([failed, failed]) == EXIT_CODE_TOTAL_FAILURE


def test_log_json_emits_one_parseable_json_object(caplog):
    # The workflow summary step greps '{.*"message":"Sync summary".*}' and
    # pipes it to jq, so the payload must be real JSON, not a dict repr.
    with caplog.at_level(logging.INFO):
        log_json("info", "Sync summary", user="Mateusz Góral", failed=0)
    payload = json.loads(caplog.records[-1].getMessage())
    assert payload["message"] == "Sync summary"
    assert payload["user"] == "Mateusz Góral"
    assert '"message":"Sync summary"' in caplog.records[-1].getMessage()
