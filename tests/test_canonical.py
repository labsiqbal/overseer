from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CORE_PATH = Path(__file__).resolve().parents[1] / "skill" / "overseer" / "scripts"
sys.path.insert(0, str(CORE_PATH))

from overseer_core.common import OverseerError, canonical_json, digest  # noqa: E402
from overseer_core.ledger import merge_ledger, render_managed  # noqa: E402
from overseer_core.paths import mutation_capability, normalize_relative, open_root  # noqa: E402


class CanonicalTests(unittest.TestCase):
    def test_canonical_json_and_domain_digest_are_stable(self) -> None:
        self.assertEqual(canonical_json({"b": 2, "a": [3, 1]}), '{"a":[3,1],"b":2}')
        self.assertEqual(digest("plan", {"b": 2, "a": [3, 1]}), digest("plan", {"a": [3, 1], "b": 2}))
        self.assertNotEqual(digest("plan", {}), digest("snapshot", {}))

    def test_floats_fail_closed(self) -> None:
        with self.assertRaises(OverseerError) as caught:
            canonical_json({"value": 1.5})
        self.assertEqual(caught.exception.code, "INVALID_REQUEST")

    def test_exact_paths_reject_escape_and_globs(self) -> None:
        for value in ("../outside", "/absolute", "*.md", "a/../b", ""):
            with self.subTest(value=value), self.assertRaises(OverseerError):
                normalize_relative(value)

    def test_ledger_preserves_owner_bytes_and_is_deterministic(self) -> None:
        model = {
            "last_material_review": "2026-07-22T12:00:00Z",
            "last_complete_audit": "never",
            "resume_from": "none",
            "canonical_context": [],
            "open_findings": [],
            "history": [],
        }
        initial = merge_ledger(None, model)
        existing = b"Owner notes\n\n" + initial + b"Owner suffix\n"
        merged = merge_ledger(existing, model)
        self.assertTrue(merged.startswith(b"Owner notes\n\n"))
        self.assertTrue(merged.endswith(b"Owner suffix\n"))
        self.assertEqual(merged, merge_ledger(merged, model))

    def test_blocked_finding_controls_status(self) -> None:
        rendered = render_managed(
            {
                "last_material_review": "never",
                "last_complete_audit": "never",
                "resume_from": "Resolve the conflict.",
                "canonical_context": [],
                "open_findings": [
                    {
                        "severity": "BLOCKED",
                        "kind": "ambiguous_canonical",
                        "subject": "Current report",
                        "evidence": "Two equal candidates",
                        "resolution": "Owner must choose",
                    }
                ],
                "history": [],
            }
        )
        self.assertIn("Project context health: BLOCKED", rendered)

    def test_symbolic_link_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            actual = base / "actual"
            actual.mkdir()
            link = base / "link"
            link.symlink_to(actual, target_is_directory=True)
            with self.assertRaises(OverseerError) as caught:
                open_root(str(link))
            self.assertEqual(caught.exception.code, "ROOT_ESCAPE")

    def test_non_posix_platform_is_preview_only(self) -> None:
        with patch("overseer_core.paths.os.name", "nt"):
            supported, reason = mutation_capability()
        self.assertFalse(supported)
        self.assertIn("POSIX", reason)


if __name__ == "__main__":
    unittest.main()
