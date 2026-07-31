from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ad_machine.jobs import create_job, load_job, record_artifact, reusable_artifacts
from ad_machine.util import sha256_file, write_json_atomic


class JobTests(unittest.TestCase):
    def test_job_is_unique_and_original_is_not_modified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "camera.mov"
            source.write_bytes(b"camera-original")
            before = source.read_bytes()
            first = create_job(source, root / "jobs")
            second = create_job(source, root / "jobs")
            self.assertNotEqual(first, second)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(load_job(first)["approval"]["status"], "pending")

    def test_artifact_reuse_requires_matching_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "camera.mov"
            source.write_bytes(b"camera-original")
            job = create_job(source, root / "jobs")
            preview = job / "previews" / "preview.mp4"
            preview.write_bytes(b"preview-one")
            record_artifact(job, "preview", preview, producer="test")
            self.assertTrue(reusable_artifacts(job)["preview"])
            preview.write_bytes(b"changed")
            self.assertFalse(reusable_artifacts(job)["preview"])

    def test_changed_plan_invalidates_dependent_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "camera.mov"
            source.write_bytes(b"camera-original")
            job = create_job(source, root / "jobs")
            plan = job / "plans" / "edit-plan.normalized.json"
            write_json_atomic(plan, {"schemaVersion": 1, "value": "first"})
            preview = job / "previews" / "preview.mp4"
            preview.write_bytes(b"preview")
            record_artifact(job, "preview", preview, producer="test", input_hashes={"plan": sha256_file(plan)})
            self.assertTrue(reusable_artifacts(job)["preview"])
            write_json_atomic(plan, {"schemaVersion": 1, "value": "changed"})
            self.assertFalse(reusable_artifacts(job)["preview"])

    def test_artifact_from_an_old_product_version_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "camera.mov"
            source.write_bytes(b"camera-original")
            job = create_job(source, root / "jobs")
            preview = job / "previews" / "preview.mp4"
            preview.write_bytes(b"preview")
            record_artifact(job, "preview", preview, producer="test")
            value = load_job(job)
            value["artifacts"]["preview"]["productVersion"] = "0.0.0"
            write_json_atomic(job / "job.json", value)
            self.assertFalse(reusable_artifacts(job)["preview"])


if __name__ == "__main__":
    unittest.main()
