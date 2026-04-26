import json
import os
import subprocess
import sys

from modules.synaps import SynapsConfig, SynapsMessageType
from tools.synaps_probe import (
    bootstrap_env_from_argv,
    build_probe_request,
    load_env_file,
    redacted_request_summary,
    redacted_send_result,
)


def test_load_env_file_parses_without_exporting_token(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SISTER_NODE_URL=http://sister.local",
                "SISTER_SYNC_TOKEN='shared-secret'",
                'ESTER_NODE_ID="ester-test"',
            ]
        ),
        encoding="utf-8",
    )

    values = load_env_file(env_file)

    assert values["SISTER_NODE_URL"] == "http://sister.local"
    assert values["SISTER_SYNC_TOKEN"] == "shared-secret"
    assert values["ESTER_NODE_ID"] == "ester-test"


def test_bootstrap_env_from_argv_loads_missing_values_without_overwrite(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SISTER_NODE_URL=http://sister.local",
                "SISTER_SYNC_TOKEN=from-file",
                "ESTER_NET_ALLOW_CIDRS=127.0.0.1/32,192.0.2.10/32",
            ]
        ),
        encoding="utf-8",
    )
    env = {"SISTER_SYNC_TOKEN": "already-set"}

    bootstrap_env_from_argv(["--env-file", str(env_file)], environ=env)

    assert env["SISTER_NODE_URL"] == "http://sister.local"
    assert env["SISTER_SYNC_TOKEN"] == "already-set"
    assert env["ESTER_NET_ALLOW_CIDRS"] == "127.0.0.1/32,192.0.2.10/32"


def test_main_bootstraps_env_file_before_synaps_import(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SISTER_NODE_URL=http://sister.local",
                "SISTER_SYNC_TOKEN=shared-secret",
                "ESTER_NODE_ID=ester-test",
                "ESTER_NET_ALLOW_CIDRS=127.0.0.1/32,::1/128,192.0.2.10/32",
                "ESTER_NET_ALLOW_HOSTS=localhost,sister.local",
            ]
        ),
        encoding="utf-8",
    )
    code = "\n".join(
        [
            "import contextlib, io, json",
            "import importlib.util",
            "spec = importlib.util.spec_from_file_location('synaps_probe_under_test', 'tools/synaps_probe.py')",
            "synaps_probe = importlib.util.module_from_spec(spec)",
            "spec.loader.exec_module(synaps_probe)",
            f"env_file = {json.dumps(str(env_file))}",
            "buf = io.StringIO()",
            "with contextlib.redirect_stdout(buf):",
            "    rc = synaps_probe.main(['--env-file', env_file, '--type', 'health'])",
            "from modules.runtime.network_deny import get_stats",
            "print(json.dumps({'rc': rc, 'stats': get_stats()}, sort_keys=True))",
        ]
    )
    env = os.environ.copy()
    env["ESTER_OFFLINE"] = "1"
    env.pop("ESTER_NET_ALLOW_CIDRS", None)
    env.pop("ESTER_NET_ALLOW_HOSTS", None)

    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout.splitlines()[-1])

    assert payload["rc"] == 0
    assert "192.0.2.10/32" in payload["stats"]["allow_cidrs"]
    assert "sister.local" in payload["stats"]["allow_hosts"]


def test_build_health_probe_request_uses_schema_payload_and_send_timeout():
    config = SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
        timeout_sec=3.0,
    )

    request = build_probe_request(config, SynapsMessageType.HEALTH)

    assert request.url == "http://sister.local/sister/inbound"
    assert request.timeout_sec == 3.0
    assert request.json["type"] == "health"
    assert request.json["schema"] == "ester.synaps.envelope.v1"
    assert request.json["metadata"] == {"probe": "synaps_probe", "mode": "health"}


def test_thought_probe_uses_opinion_timeout():
    config = SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
        timeout_sec=3.0,
        opinion_timeout_sec=44.0,
    )

    request = build_probe_request(config, SynapsMessageType.THOUGHT_REQUEST, content="bounded question")

    assert request.timeout_sec == 44.0
    assert request.json["type"] == "thought_request"
    assert request.json["content"] == "bounded question"


def test_redacted_summary_never_discloses_token_value():
    config = SynapsConfig(
        node_url="http://sister.local",
        sync_token="shared-secret",
        node_id="ester-test",
    )
    request = build_probe_request(config, SynapsMessageType.CHAT)

    summary = redacted_request_summary(request, config)

    assert summary["json"]["token"].startswith("<set len=")
    assert "shared-secret" not in str(summary)
    assert summary["synaps_health"]["has_token"] is True


def test_redacted_send_result_scrubs_nested_token_value():
    result = {
        "ok": False,
        "status": 403,
        "body": {"message": "bad shared-secret", "nested": ["shared-secret"]},
    }

    redacted = redacted_send_result(result, "shared-secret")

    assert "shared-secret" not in str(redacted)
    assert "<set len=" in str(redacted)


def test_cli_defaults_to_dry_run_and_does_not_disclose_token(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SISTER_NODE_URL=http://sister.local",
                "SISTER_SYNC_TOKEN=shared-secret",
                "ESTER_NODE_ID=ester-test",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_probe.py",
            "--env-file",
            str(env_file),
            "--type",
            "health",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["request"]["json"]["type"] == "health"
    assert "shared-secret" not in result.stdout
