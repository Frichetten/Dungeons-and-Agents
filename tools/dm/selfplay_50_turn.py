#!/usr/bin/env python3
"""Run a persisted multi-turn self-play campaign for QA regression testing."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
DMCTL = ROOT / "tools" / "dmctl"
CAMPAIGNS_ROOT = ROOT / ".dm" / "campaigns"
PLAYER_ID = "pc_hero"
MAYOR_ID = "npc_mayor"


class CommandFailure(RuntimeError):
    """Raised when dmctl returns an error response."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_dmctl(
    campaign_id: str,
    *parts: str,
    payload: Optional[Dict[str, Any]] = None,
    expect_ok: Optional[bool] = True,
) -> Dict[str, Any]:
    cmd: List[str] = [str(DMCTL), *parts, "--campaign", campaign_id]
    if payload is not None:
        cmd.extend(["--payload", json.dumps(payload, separators=(",", ":"))])
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), check=False)
    stdout = result.stdout.strip()
    try:
        body = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CommandFailure(f"non_json_response: cmd={' '.join(cmd)} stdout={stdout[:300]}") from exc
    if expect_ok is True and not body.get("ok"):
        raise CommandFailure(
            f"command_failed: {' '.join(parts)}: {body.get('error')}:{json.dumps(body.get('details', {}), separators=(',', ':'))}"
        )
    if expect_ok is False and body.get("ok"):
        raise CommandFailure(f"unexpected_success: {' '.join(parts)}")
    return body


def pc_item_quantity(campaign_id: str, item_name: str) -> int:
    inventory = run_dmctl(
        campaign_id,
        "ooc",
        "inventory",
        payload={"owner_type": "pc", "owner_id": PLAYER_ID},
    )
    rows = inventory.get("data", {}).get("inventory", [])
    for row in rows:
        if str(row.get("item_name", "")) == item_name:
            return int(row.get("quantity", 0))
    return 0


def maybe_potion_consume(campaign_id: str, turn: int, actions: List[str], warnings: List[Dict[str, Any]]) -> None:
    quantity = pc_item_quantity(campaign_id, "Potion of Healing")
    if quantity <= 0:
        warnings.append(
            {
                "turn": turn,
                "command": "item consume",
                "warning": "Skipped potion consume because inventory is empty.",
            }
        )
        actions.append("potion_consume_skipped_empty_inventory")
        return
    run_dmctl(
        campaign_id,
        "item",
        "consume",
        payload={
            "owner_type": "pc",
            "owner_id": PLAYER_ID,
            "item_name": "Potion of Healing",
            "quantity": 1,
        },
    )
    actions.append("potion_consumed")


def append_command_warnings(
    target: List[Dict[str, Any]],
    turn: int,
    command: str,
    body: Dict[str, Any],
) -> None:
    warnings = body.get("warnings")
    if not isinstance(warnings, list):
        return
    for warning in warnings:
        target.append({"turn": turn, "command": command, "warning": str(warning)})


def run_turn_one(campaign_id: str, turn: int, turn_actions: List[str]) -> None:
    run_dmctl(
        campaign_id,
        "campaign",
        "seed",
        payload={
            "locations": [
                {"id": "loc_town", "name": "Oakcross", "region": "Greenmarch"},
                {"id": "loc_road", "name": "Raven Road", "region": "Greenmarch"},
                {"id": "loc_keep", "name": "Old Watch Keep", "region": "Greenmarch"},
                {"id": "loc_chapel", "name": "Ash Chapel Ruins", "region": "Greenmarch"},
            ],
            "player_characters": [
                {
                    "id": PLAYER_ID,
                    "name": "Arin Vale",
                    "class": "Rogue",
                    "level": 3,
                    "max_hp": 24,
                    "current_hp": 24,
                    "ac": 15,
                    "location_id": "loc_town",
                    "initiative_mod": 3,
                    "spell_slots": {"1": 2},
                }
            ],
            "npcs": [
                {"id": MAYOR_ID, "name": "Mayor Elira Thorn", "location_id": "loc_town", "max_hp": 12, "current_hp": 12, "ac": 12},
                {"id": "npc_sergeant", "name": "Sergeant Bram", "location_id": "loc_town", "max_hp": 14, "current_hp": 14, "ac": 13},
                {"id": "npc_scholar", "name": "Scholar Nyx", "location_id": "loc_town", "max_hp": 10, "current_hp": 10, "ac": 11},
            ],
            "world_state": {
                "world_date": "1 Ches 1492 DR",
                "world_time": "08:00",
                "weather": "mist",
                "region": "Greenmarch",
                "location_id": "loc_town",
                "active_arc": "Ashen Crown",
            },
            "hooks": ["Find who stole the Ashen Crown before the moon eclipse."],
        },
    )
    run_dmctl(
        campaign_id,
        "quest",
        "add",
        payload={
            "id": "quest_main_ashen",
            "title": "Recover the Ashen Crown",
            "description": "Track the relic through Oakcross before a cult activates it.",
            "is_main_arc": True,
            "auto_grant": True,
            "reward": {"grants": [{"recipient_type": "pc", "recipient_id": PLAYER_ID, "reward": {"xp": 180, "currency_cp": 140}}]},
            "objectives": [
                {"id": "obj_guard_ledgers", "description": "Inspect the guard ledgers for missing entries."},
                {"id": "obj_chapel_route", "description": "Scout the chapel route used by smugglers."},
            ],
        },
    )
    run_dmctl(
        campaign_id,
        "rumor",
        "add",
        payload={
            "id": "rumor_chapel_vault",
            "text": "A vault under Ash Chapel opens only during stormlight.",
            "source": "Old Mason",
            "truth_status": "true",
            "spread_level": 1,
            "decay": 0,
        },
    )
    run_dmctl(
        campaign_id,
        "secret",
        "add",
        payload={
            "id": "secret_mayor_cane_key",
            "text": "The chapel vault key is hidden in the mayor's cane cap.",
            "discovery_condition": "Gain the mayor's confidence and inspect the cane.",
            "associated_rumor_id": "rumor_chapel_vault",
        },
    )
    run_dmctl(
        campaign_id,
        "faction",
        "update",
        payload={
            "faction_id": "fac_ashen_crown",
            "name": "Ashen Crown Circle",
            "agenda": "Acquire relic sites quietly before public panic spreads.",
            "reputation": -1,
            "trust": -2,
            "fear": 1,
        },
    )
    run_dmctl(
        campaign_id,
        "agenda",
        "upsert",
        payload={
            "agenda_id": "agenda_ashen_pressure",
            "name": "Ashen Pressure",
            "effect_type": "clock_tick",
            "cadence_turns": 3,
            "payload": {"name": "Ashen Ritual Clock", "amount": 1, "max_segments": 10},
        },
    )
    run_dmctl(
        campaign_id,
        "item",
        "grant",
        payload={"owner_type": "pc", "owner_id": PLAYER_ID, "item_name": "Rations", "quantity": 8, "consumable": True, "stackable": True},
    )
    run_dmctl(
        campaign_id,
        "item",
        "grant",
        payload={"owner_type": "pc", "owner_id": PLAYER_ID, "item_name": "Potion of Healing", "quantity": 2, "consumable": True, "stackable": True},
    )
    run_dmctl(
        campaign_id,
        "relationship",
        "adjust",
        payload={
            "source_type": "pc",
            "source_id": PLAYER_ID,
            "target_type": "npc",
            "target_id": MAYOR_ID,
            "trust_delta": 1,
            "reputation_delta": 1,
        },
    )
    turn_actions.extend(
        [
            "session_zero_seed",
            "main_quest_added",
            "initial_rumor_secret_added",
            "faction_seeded",
            "agenda_seeded",
            "starter_inventory_granted",
            "initial_relationship_set",
        ]
    )


def run_regular_turn(
    campaign_id: str,
    turn: int,
    turn_actions: List[str],
    warnings: List[Dict[str, Any]],
    current_location: str,
) -> str:
    weather_cycle = ["clear", "mist", "drizzle", "windy", "overcast"]
    travel_cycle = ["loc_road", "loc_keep", "loc_chapel", "loc_town"]

    roll = run_dmctl(campaign_id, "dice", "roll", "--formula", "1d20+4", "--context", f"selfplay_turn_{turn}_check")
    append_command_warnings(warnings, turn, "dice roll", roll)
    turn_actions.append(f"skill_check_{roll['data']['total']}")

    run_dmctl(
        campaign_id,
        "state",
        "set",
        payload={
            "world_state": {"weather": weather_cycle[(turn - 1) % len(weather_cycle)]},
            "public_note": f"Turn {turn}: party pushes the Ashen Crown lead forward.",
            "hidden_note": f"GM note turn {turn}: cult scouts are tracking Arin's route.",
        },
    )
    pulse = run_dmctl(
        campaign_id,
        "world",
        "pulse",
        payload={
            "hours": (turn % 3) + 1,
            "clock_ticks": [{"name": "Town Anxiety", "amount": 1, "max_segments": 8}],
            "add_hooks": [f"Turn {turn} consequence: a witness changes their story."],
        },
    )
    append_command_warnings(warnings, turn, "world pulse", pulse)
    turn_actions.append("world_pulse")

    if turn % 4 == 0:
        current_location = travel_cycle[(turn // 4 - 1) % len(travel_cycle)]
        travel = run_dmctl(
            campaign_id,
            "travel",
            "resolve",
            payload={
                "to_location_id": current_location,
                "travel_hours": 2,
                "consume_rations": True,
                "ration_shortage_policy": "soft",
            },
        )
        append_command_warnings(warnings, turn, "travel resolve", travel)
        turn_actions.append(f"travel_{current_location}")

    if turn % 5 == 0:
        trust_delta = -1 if turn % 10 == 0 else 1
        run_dmctl(
            campaign_id,
            "relationship",
            "adjust",
            payload={
                "source_type": "pc",
                "source_id": PLAYER_ID,
                "target_type": "npc",
                "target_id": MAYOR_ID,
                "trust_delta": trust_delta,
                "reputation_delta": 1,
            },
        )
        turn_actions.append("relationship_adjusted")

    if turn % 6 == 0:
        run_dmctl(campaign_id, "faction", "update", payload={"faction_id": "fac_ashen_crown", "reputation_delta": -1, "fear_delta": 1})
        turn_actions.append("faction_pressure_shifted")

    if turn % 7 == 0:
        run_dmctl(
            campaign_id,
            "item",
            "grant",
            payload={"owner_type": "pc", "owner_id": PLAYER_ID, "item_name": "Arrow", "quantity": 3, "consumable": True, "stackable": True},
        )
        turn_actions.append("ammo_granted")

    if turn % 8 == 0:
        maybe_potion_consume(campaign_id, turn, turn_actions, warnings)

    if turn % 9 == 0:
        cast = run_dmctl(
            campaign_id,
            "spell",
            "cast",
            payload={"caster_type": "pc", "caster_id": PLAYER_ID, "spell_name": "Invisibility", "remaining_rounds": 10, "requires_concentration": True},
        )
        run_dmctl(campaign_id, "spell", "end", payload={"spell_id": cast["data"]["spell"]["id"]})
        turn_actions.append("spell_cycle_cast_end")

    if turn % 11 == 0:
        run_dmctl(
            campaign_id,
            "reward",
            "grant",
            payload={
                "source_type": "milestone",
                "source_id": f"turn_{turn}",
                "grants": [{"recipient_type": "pc", "recipient_id": PLAYER_ID, "reward": {"currency_cp": 20, "xp": 30}}],
            },
        )
        turn_actions.append("milestone_reward_granted")

    if turn % 13 == 0:
        rest_type = "long" if turn % 26 == 0 else "short"
        run_dmctl(campaign_id, "rest", "resolve", payload={"rest_type": rest_type})
        turn_actions.append(f"rest_{rest_type}")

    if turn in {12, 24, 36, 48}:
        enemy_id = f"npc_raider_{turn}"
        run_dmctl(
            campaign_id,
            "npc",
            "create",
            payload={"id": enemy_id, "name": f"Ash Raider {turn}", "location_id": current_location, "max_hp": 16, "current_hp": 16, "ac": 13, "initiative_mod": 1},
        )
        start = run_dmctl(
            campaign_id,
            "combat",
            "start",
            payload={"name": f"Skirmish Turn {turn}", "location_id": current_location, "participants": [{"type": "pc", "id": PLAYER_ID}, {"type": "npc", "id": enemy_id}]},
        )
        combatants = start["data"]["combatants"]
        actor = combatants[0]
        target = next(row for row in combatants if row["id"] != actor["id"])
        run_dmctl(
            campaign_id,
            "combat",
            "resolve",
            payload={
                "mode": "attack",
                "encounter_id": start["data"]["encounter_id"],
                "combatant_id": actor["id"],
                "target_id": target["id"],
                "attack_bonus": 9,
                "damage_formula": "1d8+3",
                "use_action": True,
                "end_turn": True,
                "action": f"{actor['name']} lunges in the dust and steel.",
            },
        )
        run_dmctl(campaign_id, "combat", "end", payload={"encounter_id": start["data"]["encounter_id"], "notes": f"Skirmish resolved on turn {turn}."})
        turn_actions.append("combat_resolved")

    if turn == 8:
        run_dmctl(
            campaign_id,
            "quest",
            "add",
            payload={
                "id": "quest_side_smugglers",
                "title": "Break the Smuggler Chain",
                "description": "Disrupt the route feeding contraband into Oakcross.",
                "status": "open",
                "objectives": [
                    {"id": "obj_smuggle_route", "description": "Map the hidden river trail."},
                    {"id": "obj_smuggle_cache", "description": "Seize the warehouse cache."},
                ],
            },
        )
        turn_actions.append("side_quest_added")

    if turn == 14:
        run_dmctl(
            campaign_id,
            "quest",
            "update",
            payload={"quest_id": "quest_side_smugglers", "status": "in_progress", "objective_updates": [{"id": "obj_smuggle_route", "status": "completed"}]},
        )
        turn_actions.append("side_quest_progressed")

    if turn == 20:
        run_dmctl(
            campaign_id,
            "quest",
            "update",
            payload={"quest_id": "quest_side_smugglers", "status": "completed", "objective_updates": [{"id": "obj_smuggle_cache", "status": "completed"}]},
        )
        turn_actions.append("side_quest_completed")

    if turn == 45:
        run_dmctl(
            campaign_id,
            "quest",
            "update",
            payload={
                "quest_id": "quest_main_ashen",
                "status": "completed",
                "objective_updates": [{"id": "obj_guard_ledgers", "status": "completed"}, {"id": "obj_chapel_route", "status": "completed"}],
            },
        )
        turn_actions.append("main_quest_completed")

    if turn == 10:
        run_dmctl(campaign_id, "rumor", "reveal", payload={"rumor_id": "rumor_chapel_vault"})
        turn_actions.append("rumor_revealed_1")

    if turn == 18:
        run_dmctl(campaign_id, "secret", "reveal", payload={"secret_id": "secret_mayor_cane_key"})
        turn_actions.append("secret_revealed_1")

    if turn == 22:
        run_dmctl(
            campaign_id,
            "rumor",
            "add",
            payload={
                "id": "rumor_raven_pass",
                "text": "A courier uses Raven Road at dawn with coded ledgers.",
                "source": "Stable scout",
                "truth_status": "true",
                "spread_level": 0,
                "decay": 0,
            },
        )
        run_dmctl(
            campaign_id,
            "secret",
            "add",
            payload={
                "id": "secret_ledgers_cipher",
                "text": "The ledger cipher key is hidden in the chapel bell frame.",
                "discovery_condition": "Interrogate courier or inspect chapel tower.",
                "associated_rumor_id": "rumor_raven_pass",
            },
        )
        turn_actions.append("rumor_secret_pair_2_added")

    if turn == 34:
        run_dmctl(campaign_id, "rumor", "reveal", payload={"rumor_id": "rumor_raven_pass"})
        turn_actions.append("rumor_revealed_2")

    if turn == 42:
        run_dmctl(campaign_id, "secret", "reveal", payload={"secret_id": "secret_ledgers_cipher"})
        turn_actions.append("secret_revealed_2")

    if turn == 25:
        refresh = run_dmctl(campaign_id, "ooc", "refresh", payload={"mode": "auto", "trigger": "resume"})
        append_command_warnings(warnings, turn, "ooc refresh", refresh)
        turn_actions.append("ooc_refresh_resume_probe")

    if turn == 30:
        dashboard = run_dmctl(campaign_id, "ooc", "dashboard")
        append_command_warnings(warnings, turn, "ooc dashboard", dashboard)
        turn_actions.append("ooc_dashboard_probe")

    return current_location


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic self-play campaign workload.")
    parser.add_argument("--campaign", help="Campaign id to create (default: selfplay50_<timestamp>)")
    parser.add_argument("--turns", type=int, default=50, help="Number of turns to commit (default: 50)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.turns <= 0:
        raise SystemExit("--turns must be positive")

    campaign_id = args.campaign or f"selfplay50_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    campaign_dir = CAMPAIGNS_ROOT / campaign_id

    run_log: Dict[str, Any] = {
        "campaign_id": campaign_id,
        "started_at": utc_now(),
        "turns": [],
        "warnings": [],
        "failures": [],
        "post_checks": {},
    }

    run_dmctl(campaign_id, "campaign", "create", "--name", "Selfplay 50 Turn QA")
    current_location = "loc_town"

    for turn in range(1, args.turns + 1):
        turn_actions: List[str] = []
        turn_entry: Dict[str, Any] = {"turn": turn, "actions": turn_actions, "summary": "", "recovered": False}
        run_dmctl(campaign_id, "turn", "begin")
        try:
            if turn == 1:
                run_turn_one(campaign_id, turn, turn_actions)
                turn_entry["summary"] = "Session zero completed: the Ashen Crown investigation begins in Oakcross."
            else:
                current_location = run_regular_turn(campaign_id, turn, turn_actions, run_log["warnings"], current_location)
                turn_entry["summary"] = f"Turn {turn}: {', '.join(turn_actions) if turn_actions else 'investigation advances'}."
            run_dmctl(campaign_id, "turn", "commit", "--summary", turn_entry["summary"])
        except Exception as exc:
            run_log["failures"].append({"turn": turn, "error": str(exc)})
            try:
                run_dmctl(campaign_id, "turn", "rollback", payload={"reason": f"selfplay recovery turn {turn}"}, expect_ok=None)
            except Exception as rollback_exc:
                run_log["warnings"].append(
                    {
                        "turn": turn,
                        "command": "turn rollback",
                        "warning": f"rollback_failed: {rollback_exc}",
                    }
                )

            # Recovery turn to preserve target committed-turn count.
            run_dmctl(campaign_id, "turn", "begin")
            run_dmctl(campaign_id, "dice", "roll", "--formula", "1d20+2", "--context", f"recovery_turn_{turn}")
            run_dmctl(campaign_id, "world", "pulse", payload={"hours": 1, "add_hooks": [f"Recovery path executed on turn {turn}."]})
            run_dmctl(campaign_id, "turn", "commit", "--summary", f"Turn {turn} recovery commit after command failure.")
            turn_entry["recovered"] = True
            turn_actions.append("recovery_commit")
            turn_entry["summary"] = f"Turn {turn} recovered after command failure."

        run_log["turns"].append(turn_entry)

    load = run_dmctl(campaign_id, "campaign", "load")
    validate = run_dmctl(campaign_id, "validate", expect_ok=None)
    recap = run_dmctl(campaign_id, "recap", "generate")
    dashboard = run_dmctl(campaign_id, "ooc", "dashboard")

    run_log["post_checks"] = {
        "latest_turn_number": load.get("data", {}).get("latest_turn", {}).get("turn_number"),
        "latest_turn_status": load.get("data", {}).get("latest_turn", {}).get("status"),
        "latest_turn_any_number": load.get("data", {}).get("latest_turn_any", {}).get("turn_number"),
        "latest_turn_any_status": load.get("data", {}).get("latest_turn_any", {}).get("status"),
        "pc_count": load.get("data", {}).get("counts", {}).get("pc_count"),
        "npc_count": load.get("data", {}).get("counts", {}).get("npc_count"),
        "validate_ok": bool(validate.get("ok")),
        "validate_error": None if validate.get("ok") else validate.get("error"),
        "recap_keys": sorted((recap.get("data") or {}).keys()),
        "dashboard_keys": sorted((dashboard.get("data") or {}).keys()),
    }
    run_log["completed_at"] = utc_now()

    campaign_dir.mkdir(parents=True, exist_ok=True)
    run_log_path = campaign_dir / "selfplay_run.json"
    run_log_path.write_text(json.dumps(run_log, indent=2) + "\n", encoding="utf-8")

    failure_count = len(run_log["failures"])
    validate_ok = bool(run_log["post_checks"]["validate_ok"])
    success = failure_count == 0 and validate_ok

    output = {
        "ok": success,
        "campaign_id": campaign_id,
        "run_log": str(run_log_path),
        "failure_count": failure_count,
        "validate_ok": validate_ok,
        "latest_turn_number": run_log["post_checks"]["latest_turn_number"],
        "latest_turn_status": run_log["post_checks"]["latest_turn_status"],
    }
    print(json.dumps(output, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
