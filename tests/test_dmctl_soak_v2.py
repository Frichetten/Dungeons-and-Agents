import json
import os
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


@unittest.skipUnless(os.getenv("DMCTL_LONG_SOAK") == "1", "Set DMCTL_LONG_SOAK=1 to run 500-turn soak test")
class TestDMCTLSoakV2(unittest.TestCase):
    def setUp(self):
        self.campaign_id = f"soak_{uuid.uuid4().hex[:8]}"
        run_dmctl("campaign", "create", "--campaign", self.campaign_id)
        run_dmctl("turn", "begin", "--campaign", self.campaign_id)
        run_dmctl(
            "campaign",
            "seed",
            "--campaign",
            self.campaign_id,
            payload={
                "locations": [{"id": "loc_a", "name": "A"}, {"id": "loc_b", "name": "B"}],
                "player_characters": [{"id": "pc_hero", "name": "Arin", "max_hp": 20, "current_hp": 20, "location_id": "loc_a"}],
                "npcs": [{"name": "N1"}, {"name": "N2"}, {"name": "N3"}],
                "world_state": {"world_time": "08:00", "location_id": "loc_a"},
            },
        )
        run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", "Soak baseline")

    def tearDown(self):
        cdir = CAMPAIGNS_ROOT / self.campaign_id
        if cdir.exists():
            shutil.rmtree(cdir)

    def test_500_turn_soak(self):
        for idx in range(500):
            run_dmctl("turn", "begin", "--campaign", self.campaign_id)
            run_dmctl(
                "dice",
                "roll",
                "--campaign",
                self.campaign_id,
                "--formula",
                "1d20+2",
                "--context",
                f"soak_{idx}",
            )
            run_dmctl(
                "world",
                "pulse",
                "--campaign",
                self.campaign_id,
                payload={
                    "hours": 1,
                    "clock_ticks": [{"name": "Soak Clock", "amount": 1, "max_segments": 8}],
                    "add_hooks": [f"hook_{idx%5}"],
                },
            )
            if idx % 10 == 0:
                run_dmctl(
                    "item",
                    "grant",
                    "--campaign",
                    self.campaign_id,
                    payload={"owner_type": "pc", "owner_id": "pc_hero", "item_name": "Arrow", "quantity": 1},
                )
            run_dmctl("turn", "commit", "--campaign", self.campaign_id, "--summary", f"Soak turn {idx}")

            if idx % 50 == 0:
                run_dmctl("campaign", "load", "--campaign", self.campaign_id)

        validate = run_dmctl("validate", "--campaign", self.campaign_id)
        self.assertTrue(validate["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
