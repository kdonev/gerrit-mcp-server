# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import asyncio
import os
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock, Mock
from gerrit_mcp_server import main

# --- Fixtures ---

@pytest.fixture
def mock_load_config():
    """Provides a mocked load_gerrit_config."""
    with patch("gerrit_mcp_server.main.load_gerrit_config") as m:
        yield m

@pytest.fixture
def mock_run_curl():
    """Provides a mocked run_curl."""
    with patch("gerrit_mcp_server.main.run_curl", new_callable=AsyncMock) as m:
        yield m

@pytest.fixture
def mock_exec():
    """Provides a mocked asyncio.create_subprocess_exec."""
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as m:
        yield m

# --- Tests ---

def test_get_gerrit_base_url_with_env_var():
    """Tests that the base URL is retrieved from the environment variable."""
    with patch.dict(os.environ, {"GERRIT_BASE_URL": "https://another-gerrit.com"}):
        assert main._get_gerrit_base_url() == "https://another-gerrit.com"

def test_get_gerrit_base_url_with_parameter(mock_load_config):
    """Tests that the provided parameter overrides the configuration."""
    assert main._get_gerrit_base_url("https://parameter-gerrit.com") == "https://parameter-gerrit.com"
    mock_load_config.assert_not_called()

@pytest.mark.parametrize("input_url, expected", [
    ("fuchsia-review.git.private.corporation.com", "https://fuchsia-review.googlesource.com"),
    ("https://fuchsia-review.git.private.corporation.com", "https://fuchsia-review.googlesource.com"),
    ("fuchsia-review.googlesource.com", "https://fuchsia-review.googlesource.com"),
    ("another-gerrit.com", "https://another-gerrit.com"),
    ("http://another-gerrit.com", "https://another-gerrit.com"),
    ("https://another-gerrit.com", "https://another-gerrit.com"),
])
def test_normalize_gerrit_url(mock_load_config, input_url, expected):
    """Tests that URLs are correctly normalized based on the configuration."""
    mock_load_config.return_value = {
        "gerrit_hosts": [
            {
                "name": "Fuchsia",
                "internal_url": "https://fuchsia-review.git.private.corporation.com/",
                "external_url": "https://fuchsia-review.googlesource.com/",
            }
        ]
    }
    gerrit_hosts = mock_load_config.return_value["gerrit_hosts"]
    assert main._normalize_gerrit_url(input_url, gerrit_hosts) == expected

def test_load_gerrit_config_not_found():
    """Tests that FileNotFoundError is raised when the config file is missing."""
    with patch("gerrit_mcp_server.main.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError):
            main.load_gerrit_config()

def test_load_gerrit_config_with_env_var():
    """Tests loading the configuration from a path specified in an environment variable."""
    with patch("builtins.open", new_callable=AsyncMock) as mock_open: # using AsyncMock just for convenience of mocking, though it's sync open
        # Actually, builtins.open is sync. Let's use mock_open properly.
        from unittest.mock import mock_open as sync_mock_open
        m = sync_mock_open(read_data='{"key": "value"}')
        with patch("builtins.open", m) as mock_file, \
             patch("pathlib.Path.exists", return_value=True), \
             patch.dict(os.environ, {"GERRIT_CONFIG_PATH": "/fake/path/gerrit_config.json"}):
            
            config = main.load_gerrit_config()
            assert config == {"key": "value"}

def test_get_gerrit_base_url_with_no_env_var(mock_load_config):
    """Tests that the default base URL is used when no environment variable is set."""
    with patch.dict(os.environ, {}, clear=True):
        mock_load_config.return_value = {
            "default_gerrit_base_url": "https://fuchsia-review.googlesource.com",
            "gerrit_hosts": [{"external_url": "https://fuchsia-review.googlesource.com"}]
        }
        assert main._get_gerrit_base_url() == "https://fuchsia-review.googlesource.com"

def test_configure_text_stream_encoding_uses_utf8():
    """Tests that text streams are reconfigured to UTF-8 when supported."""
    stream = Mock()

    main._configure_text_stream_encoding(stream)

    stream.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")

def test_configure_text_stream_encoding_is_noop_without_reconfigure():
    """Tests that stream encoding configuration is skipped for unsupported streams."""
    class StreamWithoutReconfigure:
        pass

    main._configure_text_stream_encoding(StreamWithoutReconfigure())

def test_configure_stdio_encoding_updates_stdout_and_stderr():
    """Tests that both stdio streams are configured."""
    stdout = Mock()
    stderr = Mock()

    with patch.object(main.sys, "stdout", stdout), patch.object(main.sys, "stderr", stderr):
        main._configure_stdio_encoding()

    stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
    stderr.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")

def test_cli_main_stdio_configures_utf8_before_run():
    """Tests that stdio mode reconfigures encoding before starting the MCP server."""
    with patch("gerrit_mcp_server.main._configure_stdio_encoding") as mock_configure, \
         patch.object(main.mcp, "run") as mock_run:
        main.cli_main(["main.py", "stdio"])

    mock_configure.assert_called_once_with()
    mock_run.assert_called_once_with(transport="stdio")

@pytest.mark.asyncio
async def test_run_curl_timeout(mock_exec, mock_load_config):
    """Tests that a TimeoutError is raised when the curl command times out."""
    mock_load_config.return_value = {
        "gerrit_hosts": [{"external_url": "https://example.com", "authentication": {"type": "gob_curl"}}]
    }
    mock_exec.return_value.communicate.side_effect = asyncio.TimeoutError

    with pytest.raises(asyncio.TimeoutError):
        await main.run_curl(["https://example.com"], "https://example.com")

@pytest.mark.asyncio
async def test_run_curl_large_output(mock_exec, mock_load_config):
    """Tests handling of large output from the curl command."""
    mock_load_config.return_value = {
        "gerrit_hosts": [{"external_url": "https://example.com", "authentication": {"type": "gob_curl"}}]
    }
    large_output = "a" * 10000
    mock_exec.return_value.communicate.return_value = (large_output.encode(), b"")
    mock_exec.return_value.returncode = 0

    result = await main.run_curl(["https://example.com"], "https://example.com")
    assert result == large_output

@pytest.mark.asyncio
async def test_run_curl_logs_unicode_output_with_utf8(mock_exec, mock_load_config):
    """Tests that curl output containing non-ASCII text can be logged on Windows."""
    mock_load_config.return_value = {
        "gerrit_hosts": [{"external_url": "https://example.com", "authentication": {"type": "gob_curl"}}]
    }
    unicode_output = ')]}\'\n{"message":"Коментар на кирилица"}'
    mock_exec.return_value.communicate.return_value = (unicode_output.encode("utf-8"), b"")
    mock_exec.return_value.returncode = 0
    log_dir = Path("build") / "pytest-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "unicode-server.log"
    if log_path.exists():
        log_path.unlink()

    with patch.object(main, "LOG_FILE_PATH", log_path):
        result = await main.run_curl(["https://example.com"], "https://example.com")

    assert result == '{"message":"Коментар на кирилица"}'
    assert "Коментар на кирилица" in log_path.read_text(encoding="utf-8")

@pytest.mark.asyncio
async def test_run_curl_non_zero_exit(mock_exec, mock_load_config):
    """Tests that an exception is raised when the curl command exits with a non-zero code."""
    mock_load_config.return_value = {
        "gerrit_hosts": [{"external_url": "https://example.com", "authentication": {"type": "gob_curl"}}]
    }
    mock_exec.return_value.communicate.return_value = (b"", b"error")
    mock_exec.return_value.returncode = 1

    with pytest.raises(Exception):
        await main.run_curl(["https://example.com"], "https://example.com")

@pytest.mark.asyncio
async def test_run_curl_removes_gerrit_prefix(mock_exec, mock_load_config):
    """Tests that the Gerrit JSON prefix is removed from the response."""
    mock_load_config.return_value = {
        "gerrit_hosts": [{"external_url": "https://example.com", "authentication": {"type": "gob_curl"}}]
    }
    mock_exec.return_value.communicate.return_value = (b')]}\'\n{"key": "value"}', b"")
    mock_exec.return_value.returncode = 0

    result = await main.run_curl(["https://example.com"], "https://example.com")
    assert result == '{"key": "value"}'

@pytest.mark.asyncio
async def test_get_bugs_from_cl_with_one_bug(mock_run_curl):
    """Tests extracting a single bug ID from a CL message."""
    mock_run_curl.return_value = '{"message": "Fixes: b/12345"}'
    result = await main.get_bugs_from_cl("123")
    assert "Found bug(s): 12345" in result[0]["text"]

@pytest.mark.asyncio
async def test_get_bugs_from_cl_with_multiple_bugs(mock_run_curl):
    """Tests extracting multiple bug IDs from a CL message."""
    mock_run_curl.return_value = '{"message": "Fixes: b/12345, b/67890"}'
    result = await main.get_bugs_from_cl("123")
    assert "Found bug(s): 12345, 67890" in result[0]["text"]

@pytest.mark.asyncio
async def test_get_bugs_from_cl_no_bugs(mock_run_curl):
    """Tests that the correct message is returned when no bugs are found."""
    mock_run_curl.return_value = '{"message": "No bugs here"}'
    result = await main.get_bugs_from_cl("123")
    assert "No bug IDs found" in result[0]["text"]

@pytest.mark.asyncio
async def test_get_bugs_from_cl_no_commit_message(mock_run_curl):
    """Tests handling of a missing commit message."""
    mock_run_curl.return_value = "{}"
    result = await main.get_bugs_from_cl("123")
    assert "No commit message found" in result[0]["text"]

@pytest.mark.asyncio
@pytest.mark.parametrize("unresolved_arg, expected_unresolved", [
    (None, True),   # Default
    (False, False),
    (True, True),
])
async def test_post_review_comment(mock_run_curl, unresolved_arg, expected_unresolved):
    """Tests posting a review comment with different 'unresolved' states."""
    mock_run_curl.return_value = '{"comments": {}}'
    
    kwargs = {}
    if unresolved_arg is not None:
        kwargs["unresolved"] = unresolved_arg

    result = await main.post_review_comment("123", "file.py", 10, "test comment", **kwargs)
    
    assert "Successfully posted comment" in result[0]["text"]
    
    # Verify the payload
    args, _ = mock_run_curl.call_args
    curl_args = args[0]
    data_index = curl_args.index("--data")
    request_body = json.loads(curl_args[data_index + 1])
    assert request_body["comments"]["file.py"][0]["unresolved"] is expected_unresolved

@pytest.mark.asyncio
async def test_post_review_comment_failure(mock_run_curl):
    """Tests handling of a failure response when posting a comment."""
    mock_run_curl.return_value = '{"error": "failed"}'
    result = await main.post_review_comment("123", "file.py", 10, "test comment")
    assert "Failed to post comment" in result[0]["text"]

@pytest.mark.asyncio
async def test_reply_to_comment_success(mock_run_curl):
    """Tests posting a reply with a validated parent comment."""
    mock_run_curl.side_effect = [
        json.dumps({
            "file.py": [
                {
                    "id": "parent-1",
                    "line": 10,
                    "author": {"name": "user@example.com"},
                    "message": "Original comment",
                    "unresolved": True,
                    "updated": "2025-07-15T10:00:00Z",
                }
            ]
        }),
        '{"comments": {}}',
    ]

    result = await main.reply_to_comment(
        "123",
        "file.py",
        "parent-1",
        "reply text",
        unresolved=False,
    )

    assert "Successfully posted reply to comment parent-1 on CL 123 in file file.py." in result[0]["text"]

    args, _ = mock_run_curl.call_args_list[1]
    curl_args = args[0]
    data_index = curl_args.index("--data")
    request_body = json.loads(curl_args[data_index + 1])
    assert request_body == {
        "comments": {
            "file.py": [
                {
                    "in_reply_to": "parent-1",
                    "message": "reply text",
                    "unresolved": False,
                }
            ]
        }
    }

@pytest.mark.asyncio
async def test_reply_to_comment_missing_parent(mock_run_curl):
    """Tests rejecting a reply when the parent comment cannot be found."""
    mock_run_curl.return_value = json.dumps({"file.py": []})

    result = await main.reply_to_comment(
        "123",
        "file.py",
        "missing-id",
        "reply text",
    )

    assert "Failed to post reply. Comment missing-id was not found on CL 123." in result[0]["text"]

@pytest.mark.asyncio
async def test_reply_to_comment_wrong_file(mock_run_curl):
    """Tests rejecting a reply when the parent comment belongs to another file."""
    mock_run_curl.return_value = json.dumps({
        "other.py": [
            {
                "id": "parent-1",
                "line": 10,
                "author": {"name": "user@example.com"},
                "message": "Original comment",
                "unresolved": True,
                "updated": "2025-07-15T10:00:00Z",
            }
        ]
    })

    result = await main.reply_to_comment(
        "123",
        "file.py",
        "parent-1",
        "reply text",
    )

    assert "Failed to post reply. Comment parent-1 belongs to file other.py, not file.py." in result[0]["text"]

# --- Edge Case Tests ---

@pytest.mark.asyncio
async def test_get_change_details_handles_missing_reviewers(mock_run_curl):
    """Tests that get_change_details handles missing 'reviewers' field gracefully."""
    mock_run_curl.return_value = json.dumps({
        "_number": 123,
        "subject": "Test",
        "owner": {"email": "a@b.com"},
        "status": "NEW",
    })
    result = await main.get_change_details("123")
    assert "Reviewers:" not in result[0]["text"]

@pytest.mark.asyncio
async def test_get_change_details_handles_empty_reviewers_list(mock_run_curl):
    """Tests that get_change_details handles an empty reviewers list gracefully."""
    mock_run_curl.return_value = json.dumps({
        "_number": 123,
        "subject": "Test",
        "owner": {"email": "a@b.com"},
        "status": "NEW",
        "reviewers": {"REVIEWER": []},
    })
    result = await main.get_change_details("123")
    assert "Reviewers:" in result[0]["text"]

@pytest.mark.asyncio
async def test_list_change_files_handles_empty_response(mock_run_curl):
    """Tests that list_change_files handles an empty response gracefully."""
    mock_run_curl.side_effect = [
        json.dumps({}),
        json.dumps({"current_revision_number": 1}),
    ]
    result = await main.list_change_files("123")
    assert "Files in CL 123 (Patch Set 1)" in result[0]["text"]
    assert "[" not in result[0]["text"]
