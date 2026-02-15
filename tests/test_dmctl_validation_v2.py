import json
import random
import shutil
import subprocess
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DMCTL = ROOT / "tools" / "dmctl"
CAMPAIGNS_ROOT = ROOT / ".dm" / "campaigns"


def run_dmctl(*parts, payload=None, expect_ok=True):
    cmd = [str(DMCTL), *parts]
    if payload is not None:
        cmd.extend(["--payload", json.dumps(payload, separators=(",", ":"))])
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), check=False)
    body = json.loads(result.stdout.strip())
    if expect_ok and not body.get("ok"):
        raise AssertionError(f"Unexpected failure: {cmd} -> {body}")
    if not expect_ok and body.get("ok"):
        raise AssertionError(f"Unexpected success: {cmd} -> {body}")
    return body


class TestDMCTLValidationV2(unittest.TestCase):
    def setUp(self):
        self.campaign_id = f"val_{uuid.uuid4().hex[:10]}"
        run_dmctl("campaign", "create", "--campaign", self.campaign_id)
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)

    def tearDown(self):
        cdir = CAMPAIGNS_ROOT / self.campaign_id
        if cdir.exists():
            shutil.rmtree(cdir)

    def test_dice_formula_fuzz(self):
        rng = random.Random(1337)
        for _ in range(80):
            pools = []
            pool_count = rng.randint(1, 3)
            for _ in range(pool_count):
                n = rng.randint(1, 4)
                sides = rng.choice([4, 6, 8, 10, 12, 20])
                pools.append(f"{n}d{sides}")
            modifier = rng.randint(-5, 5)
            formula = "+".join(pools)
            if modifier < 0:
                formula += str(modifier)
            elif modifier > 0:
                formula += f"+{modifier}"

            body = run_dmctl("dice", "roll", "--campaign", self.campaign_id, "--formula", formula)
            self.assertTrue(body["ok"])
            self.assertIn("total", body["data"])
            self.assertIn("raw_dice", body["data"])

    def test_invalid_formula_and_payload_errors(self):
        bad_formula = run_dmctl(
            "dice",
            "roll",
            "--campaign",
            self.campaign_id,
            "--formula",
            "2dd20",
            expect_ok=False,
        )
        self.assertEqual(bad_formula["error"], "invalid_dice_formula")
        self.assertIn("message", bad_formula["details"])

        bad_payload = run_dmctl(
            "state",
            "set",
            "--campaign",
            self.campaign_id,
            payload={"world_state": "not-an-object"},
            expect_ok=False,
        )
        self.assertEqual(bad_payload["error"], "invalid_world_state_payload")
        self.assertIn("message", bad_payload["details"])

    def test_validate_reports_event_log_parity_details_on_mismatch(self):
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "validation parity baseline")
        events_path = CAMPAIGNS_ROOT / self.campaign_id / "events.ndjson"
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "id": f"evt_extra_{uuid.uuid4().hex[:8]}",
                        "campaign_id": self.campaign_id,
                        "turn_id": 9999,
                        "command": "fake",
                        "payload": {},
                        "timestamp": "2000-01-01T00:00:00+00:00",
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )

        validate = run_dmctl("validate", "--campaign", self.campaign_id, expect_ok=False)
        self.assertEqual(validate["error"], "validation_failed")
        result = validate["details"]["results"][0]
        self.assertIn("event_log_parity", result)
        parity = result["event_log_parity"]
        for key in [
            "db_count",
            "file_count",
            "first_mismatch_index",
            "only_in_db_sample",
            "only_in_file_sample",
        ]:
            self.assertIn(key, parity)
        self.assertGreater(parity["file_count"], parity["db_count"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
