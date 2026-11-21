# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from pathlib import Path
import os
import re
import subprocess
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "compose-upgrade.yml"
SCRIPT_PATH = REPOSITORY_ROOT / ".github" / "scripts" / "compose-upgrade.sh"
SEED_PATH = REPOSITORY_ROOT / ".github" / "scripts" / "compose_seed.py"


class ComposeUpgradeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_runs_on_call_dispatch_and_weekly(self):
        triggers = self.workflow.split("\non:\n", maxsplit=1)[1].split("\npermissions:", maxsplit=1)[0]
        self.assertIn("  workflow_call:\n", triggers)
        self.assertIn("  workflow_dispatch:\n", triggers)
        self.assertIn("  schedule:\n", triggers)
        pull_request = triggers.split("  pull_request:\n", maxsplit=1)[1].split("  schedule:", maxsplit=1)[0]
        for path in ("install.sh", "docker-compose.yml", "restore.sh"):
            self.assertIn(f'      - "deployments/cli/community/{path}"\n', pull_request)
        # A release qualification must never be cancelled by a newer run.
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", self.workflow)
        for trigger in ("workflow_call", "workflow_dispatch"):
            inputs = triggers.split(f"  {trigger}:\n", maxsplit=1)[1]
            self.assertIn("      from_release:\n", inputs)
            self.assertIn("      to_image_tag:\n", inputs)

    def test_job_is_bounded_and_read_only(self):
        self.assertIn("permissions:\n  contents: read\n\n", self.workflow)
        self.assertNotIn("write", self.workflow.split("\njobs:", maxsplit=1)[0])
        self.assertIn("    runs-on: ubuntu-22.04\n", self.workflow)
        self.assertIn("    timeout-minutes: 45\n", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)

    def test_inputs_reach_the_shell_only_through_the_environment(self):
        for step in self.workflow.split("      - name: ")[1:]:
            run = step.split("        run: |", maxsplit=1)
            if len(run) == 2:
                self.assertNotIn("${{", run[1], step.splitlines()[0])

    def test_never_upgrades_from_a_prerelease(self):
        self.assertIn('gh release view --repo "$REPOSITORY" --json tagName --jq .tagName', self.workflow)
        self.assertIn(r'^(hangar-)?v[0-9]+\.[0-9]+\.[0-9]+$', self.workflow)

    def test_candidate_images_must_exist_before_the_run(self):
        self.assertIn('TO_IMAGE_TAG="preview-sha-${CANDIDATE_SHA}"', self.workflow)
        self.assertIn("TO_IMAGE_TAG=${FROM_RELEASE#hangar-}", self.workflow)
        self.assertIn("CANDIDATE_SHA: ${{ github.event.pull_request.head.sha || github.sha }}", self.workflow)
        # A moving preview tag can be older than the release it would upgrade.
        self.assertNotIn("TO_IMAGE_TAG=preview-preview", self.workflow)
        self.assertIn('docker manifest inspect "${IMAGE_PREFIX}${image}:${TO_IMAGE_TAG}"', self.workflow)

    def test_failure_uploads_logs_but_not_the_backup(self):
        upload = self.workflow.split("      - name: Upload the deployment logs\n", maxsplit=1)[1]
        self.assertIn("        if: failure()\n", upload)
        self.assertIn("actions/upload-artifact@", upload)
        self.assertIn("compose-upgrade-artifacts/logs", upload)
        self.assertNotIn("backup", upload.split("path: |", maxsplit=1)[1].split("if-no-files-found")[0])
        self.assertNotIn("plane.env", upload.split("path: |", maxsplit=1)[1])

    def test_workflow_delegates_to_the_script(self):
        self.assertIn(
            '.github/scripts/compose-upgrade.sh --from "$FROM_RELEASE" --to "$TO_IMAGE_TAG"',
            self.workflow,
        )


class ComposeUpgradeScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT_PATH.read_text(encoding="utf-8")

    def test_script_is_executable(self):
        self.assertTrue(os.access(SCRIPT_PATH, os.X_OK))

    def test_previous_release_is_installed_with_its_own_assets(self):
        self.assertIn(
            '"https://github.com/$GITHUB_REPOSITORY/releases/download/$FROM_RELEASE/$asset"',
            self.script,
        )
        self.assertIn("for asset in setup.sh docker-compose.yml variables.env; do", self.script)
        self.assertIn('(cd "$FROM_DIR" && bash ./setup.sh install < /dev/null)', self.script)
        self.assertIn('(cd "$FROM_DIR" && bash ./setup.sh start < /dev/null)', self.script)

    def test_upgrade_uses_the_candidate_installer_unattended(self):
        self.assertIn(
            'export HANGAR_ASSUME_YES=1 HANGAR_INSTALL_SOURCE_DIR="$SOURCE_DIR" HANGAR_RELEASE="$TO_IMAGE_TAG"',
            self.script,
        )
        self.assertIn('bash "$SOURCE_DIR/install.sh" --yes upgrade < /dev/null', self.script)
        self.assertIn("is still empty or a template value after the upgrade", self.script)
        self.assertIn("the upgrade changed POSTGRES_PASSWORD of an existing database", self.script)

    def test_backup_and_restore_use_the_shipped_scripts(self):
        self.assertIn('bash "$SOURCE_DIR/install.sh" --yes backup < /dev/null', self.script)
        self.assertIn('cp "$SOURCE_DIR/restore.sh" "$RESTORE_DIR/restore.sh"', self.script)
        self.assertIn('bash ./restore.sh "$BACKUP_DIR" < /dev/null', self.script)
        # The restore removes the upgraded deployment and its volumes first.
        self.assertLess(self.script.index("PHASE=remove-upgraded"), self.script.index("PHASE=restore\n"))

    def test_every_stage_is_verified(self):
        for label in ("upgrade", "restore"):
            self.assertIn(f'compare_fingerprint {label} "$ARTIFACT_DIR/fingerprint-', self.script)
        for label in ('"$FROM_VERSION"', "upgraded", "restored"):
            self.assertIn(f"check_http {label}\n", self.script)
        self.assertIn('"$BASE_URL/auth/sign-in/"', self.script)
        self.assertIn('-H "@$SECRETS_DIR/api-key-header"', self.script)
        # The token stays off curl's command line.
        self.assertNotIn('-H "X-API-Key: $SEED_API_TOKEN"', self.script)

    def test_refuses_to_touch_an_existing_deployment(self):
        self.assertIn("refusing to touch it", self.script)
        self.assertLess(self.script.index("refusing to touch it"), self.script.index("PHASE=install-from"))

    def test_rejects_an_invalid_tag_before_doing_anything(self):
        result = subprocess.run(
            ["bash", str(SCRIPT_PATH), "--to", "../bad tag"],
            capture_output=True,
            text=True,
            env={"PATH": os.environ["PATH"]},
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a valid OCI image tag", result.stdout + result.stderr)

    def test_help_documents_the_arguments(self):
        result = subprocess.run(["bash", str(SCRIPT_PATH), "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--to", result.stdout)
        self.assertIn("--from", result.stdout)


class RestoreScriptTests(unittest.TestCase):
    def test_object_storage_is_restored_to_the_user_seaweedfs_runs_as(self):
        compose = (REPOSITORY_ROOT / "deployments" / "cli" / "community" / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
        restore = (REPOSITORY_ROOT / "deployments" / "cli" / "community" / "restore.sh").read_text(encoding="utf-8")
        minio = compose.split("\n  plane-minio:\n", maxsplit=1)[1].split("\n  proxy:\n", maxsplit=1)[0]
        user = re.search(r'^    user: "([0-9]+:[0-9]+)"$', minio, re.MULTILINE)
        self.assertIsNotNone(user)
        self.assertIn("      - ALL\n", minio.split("cap_drop:", maxsplit=1)[1])
        self.assertIn(
            f'if [ "$restoreFile" == "object-storage" ]; then\n        owner="{user.group(1)}"', restore
        )
        self.assertIn('chown -R "$OWNER" /vol', restore)

    def test_a_failed_volume_fails_the_restore(self):
        restore = (REPOSITORY_ROOT / "deployments" / "cli" / "community" / "restore.sh").read_text(encoding="utf-8")
        self.assertIn('restoreSingleVolume "$docVol" "$BACKUP_FOLDER" "$restoreFileName" || failed=1', restore)
        self.assertLess(restore.index('if [ "$failed" -ne 0 ]; then'), restore.index("Restore completed successfully."))
        # An empty archive (a Valkey volume with nothing saved) restores too.
        self.assertIn('cp -a "/restore/${TAR_NAME}/." /vol/', restore)

    def test_the_archive_is_streamed_rather_than_mounted(self):
        # S28: setup.sh backup writes the archives 0600 in a 0700 folder, which
        # the container's root cannot read under user-namespace remapping.
        restore = (REPOSITORY_ROOT / "deployments" / "cli" / "community" / "restore.sh").read_text(encoding="utf-8")
        single = restore.split("function restoreSingleVolume()", maxsplit=1)[1].split("\nfunction ", maxsplit=1)[0]
        self.assertIn("docker run --rm -i \\\n", single)
        self.assertIn("tar -xzf - -C /restore", single)
        self.assertIn('< "$backupFolder/${restoreFile}.tar.gz"', single)
        self.assertNotIn(":/backup", single)


class ComposeSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = SEED_PATH.read_text(encoding="utf-8")

    def test_covers_roles_content_files_and_fork_objects(self):
        for model in (
            "Workspace",
            "WorkspaceMember",
            "Project",
            "ProjectMember",
            "Issue",
            "IssueComment",
            "FileAsset",
            "APIToken",
            "IssueWorkLog",
        ):
            self.assertIn(f"{model}.objects.create(", self.seed)
        self.assertIn('"admin@upgrade.hangar.invalid": ("Ada", 20, 15)', self.seed)
        self.assertIn('"guest@upgrade.hangar.invalid": ("Gus", 5, None)', self.seed)
        self.assertIn("S3Storage().upload_file(", self.seed)
        self.assertIn('"stored_sha256": stored_object_sha256(asset.asset.name)', self.seed)

    def test_fingerprint_never_contains_the_credentials(self):
        fingerprint = self.seed.split("def fingerprint(", maxsplit=1)[1].split("\ndef main(", maxsplit=1)[0]
        self.assertNotIn('"password": password', fingerprint)
        self.assertNotIn(": api_token", fingerprint)
        self.assertIn('"matches": token.token == api_token', fingerprint)
        self.assertIn('"password_matches": user.check_password(password)', fingerprint)

    def test_rejects_unknown_modes_without_django(self):
        result = subprocess.run(
            ["python3", "-I", str(SEED_PATH), "--drop"], capture_output=True, text=True, check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage: compose_seed.py --seed | --verify", result.stderr)


if __name__ == "__main__":
    unittest.main()
