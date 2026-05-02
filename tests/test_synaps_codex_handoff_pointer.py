import json
import subprocess
import sys

from modules.synaps import (
    CODEX_HANDOFF_POINTER_CONFIRM_PHRASE,
    build_codex_handoff_pointer,
    write_codex_handoff_pointer,
)


def test_handoff_pointer_excludes_source_body_and_forbidden_terms(tmp_path):
    source = tmp_path / "contract.md"
    source.write_text(
        "Full contract body mentions SYNAPS_CODEX_WORKER_CAPABILITY and payload_b64 and should not appear.",
        encoding="utf-8",
    )

    payload = build_codex_handoff_pointer(
        gate="0049",
        title="Handoff hygiene pointer",
        accepted_transfer_ids=["synaps-file-test"],
        rejected_transfer_ids=["synaps-file-rejected"],
        source_files=[source],
        patch_sha256="a" * 64,
        forbid_terms=["SYNAPS_CODEX_WORKER_CAPABILITY"],
    )

    assert payload["ok"] is True
    assert "synaps-file-test" in payload["text"]
    assert "synaps-file-rejected" in payload["text"]
    assert "contract.md" in payload["text"]
    assert "SYNAPS_CODEX_WORKER_CAPABILITY" not in payload["text"]
    assert "payload_b64" not in payload["text"]
    assert "Full contract body" not in payload["text"]


def test_handoff_pointer_write_requires_confirm(tmp_path):
    payload = build_codex_handoff_pointer(gate="0049", title="Pointer", accepted_transfer_ids=["synaps-file-test"])
    output = tmp_path / "pointer.md"

    blocked = write_codex_handoff_pointer(payload, output_path=output, confirm="")
    assert blocked["ok"] is False
    assert not output.exists()

    written = write_codex_handoff_pointer(payload, output_path=output, confirm=CODEX_HANDOFF_POINTER_CONFIRM_PHRASE)

    assert written["ok"] is True
    assert output.is_file()


def test_cli_handoff_pointer_dry_run_writes_nothing(tmp_path):
    source = tmp_path / "contract.md"
    source.write_text("contract body", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_handoff_pointer.py",
            "--gate",
            "0049",
            "--title",
            "Pointer CLI",
            "--transfer-id",
            "synaps-file-test",
            "--source-file",
            str(source),
            "--output",
            str(tmp_path / "pointer.md"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert not (tmp_path / "pointer.md").exists()


def test_cli_handoff_pointer_write(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "tools/synaps_codex_handoff_pointer.py",
            "--gate",
            "0049",
            "--title",
            "Pointer CLI",
            "--transfer-id",
            "synaps-file-test",
            "--output",
            str(tmp_path / "pointer.md"),
            "--write",
            "--confirm",
            CODEX_HANDOFF_POINTER_CONFIRM_PHRASE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["write"]["ok"] is True
    assert (tmp_path / "pointer.md").is_file()
