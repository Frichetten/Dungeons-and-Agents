PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', '4');

CREATE TABLE IF NOT EXISTS applied_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    last_played_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 4,
    current_scene TEXT NOT NULL DEFAULT '',
    main_arc TEXT NOT NULL DEFAULT '',
    side_arcs_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    region TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(campaign_id, name)
);

CREATE TABLE IF NOT EXISTS location_discoveries (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    pc_id TEXT NOT NULL REFERENCES player_characters(id) ON DELETE CASCADE,
    location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    discovered_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    UNIQUE(campaign_id, pc_id, location_id)
);

CREATE TABLE IF NOT EXISTS travel_routes (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    from_location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    to_location_id TEXT NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    distance_miles REAL NOT NULL DEFAULT 0,
    travel_time_hours REAL NOT NULL DEFAULT 0,
    danger_level INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS world_state (
    campaign_id TEXT PRIMARY KEY REFERENCES campaigns(id) ON DELETE CASCADE,
    world_date TEXT NOT NULL DEFAULT '1 Hammer 1492 DR',
    world_day_index INTEGER NOT NULL DEFAULT 0,
    world_time TEXT NOT NULL DEFAULT '08:00',
    weather TEXT NOT NULL DEFAULT 'clear',
    region TEXT NOT NULL DEFAULT 'Unknown',
    location_id TEXT REFERENCES locations(id) ON DELETE SET NULL,
    legal_heat INTEGER NOT NULL DEFAULT 0,
    notoriety INTEGER NOT NULL DEFAULT 0,
    active_arc TEXT NOT NULL DEFAULT '',
    unresolved_hooks_json TEXT NOT NULL DEFAULT '[]',
    consequence_clocks_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('open', 'committed', 'rolled_back')),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    summary TEXT NOT NULL DEFAULT '',
    backup_path TEXT NOT NULL DEFAULT '',
    checkpoint_path TEXT NOT NULL DEFAULT '',
    checkpoint_checksum TEXT NOT NULL DEFAULT '',
    checkpoint_created_at TEXT,
    UNIQUE(campaign_id, turn_number)
);

CREATE TABLE IF NOT EXISTS player_characters (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    char_class TEXT NOT NULL DEFAULT '',
    level INTEGER NOT NULL DEFAULT 1 CHECK(level >= 1),
    max_hp INTEGER NOT NULL CHECK(max_hp > 0),
    current_hp INTEGER NOT NULL CHECK(current_hp >= 0 AND current_hp <= max_hp),
    ac INTEGER NOT NULL DEFAULT 10 CHECK(ac >= 0),
    conditions_json TEXT NOT NULL DEFAULT '[]',
    exhaustion INTEGER NOT NULL DEFAULT 0 CHECK(exhaustion >= 0 AND exhaustion <= 6),
    hit_dice_total INTEGER NOT NULL DEFAULT 1 CHECK(hit_dice_total >= 0),
    hit_dice_used INTEGER NOT NULL DEFAULT 0 CHECK(hit_dice_used >= 0 AND hit_dice_used <= hit_dice_total),
    death_saves_success INTEGER NOT NULL DEFAULT 0 CHECK(death_saves_success >= 0 AND death_saves_success <= 3),
    death_saves_fail INTEGER NOT NULL DEFAULT 0 CHECK(death_saves_fail >= 0 AND death_saves_fail <= 3),
    spell_slots_json TEXT NOT NULL DEFAULT '{}',
    prepared_spells_json TEXT NOT NULL DEFAULT '[]',
    concentration_spell TEXT NOT NULL DEFAULT '',
    consumables_json TEXT NOT NULL DEFAULT '{}',
    xp_total INTEGER NOT NULL DEFAULT 0 CHECK(xp_total >= 0),
    inspiration INTEGER NOT NULL DEFAULT 0 CHECK(inspiration IN (0, 1)),
    money_cp INTEGER NOT NULL DEFAULT 0 CHECK(money_cp >= 0),
    location_id TEXT REFERENCES locations(id) ON DELETE SET NULL,
    initiative_mod INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS factions (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    reputation INTEGER NOT NULL DEFAULT 0,
    trust INTEGER NOT NULL DEFAULT 0,
    fear INTEGER NOT NULL DEFAULT 0,
    debt INTEGER NOT NULL DEFAULT 0,
    agenda TEXT NOT NULL DEFAULT '',
    clock_id TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_id, name)
);

CREATE TABLE IF NOT EXISTS npcs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    faction_id TEXT REFERENCES factions(id) ON DELETE SET NULL,
    location_id TEXT REFERENCES locations(id) ON DELETE SET NULL,
    max_hp INTEGER NOT NULL DEFAULT 1 CHECK(max_hp > 0),
    current_hp INTEGER NOT NULL DEFAULT 1 CHECK(current_hp >= 0 AND current_hp <= max_hp),
    ac INTEGER NOT NULL DEFAULT 10 CHECK(ac >= 0),
    conditions_json TEXT NOT NULL DEFAULT '[]',
    trust INTEGER NOT NULL DEFAULT 0,
    fear INTEGER NOT NULL DEFAULT 0,
    debt INTEGER NOT NULL DEFAULT 0,
    reputation INTEGER NOT NULL DEFAULT 0,
    initiative_mod INTEGER NOT NULL DEFAULT 0,
    notes_public TEXT NOT NULL DEFAULT '',
    notes_hidden TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quests (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'in_progress', 'completed', 'failed')),
    is_main_arc INTEGER NOT NULL DEFAULT 0 CHECK(is_main_arc IN (0, 1)),
    source_npc_id TEXT REFERENCES npcs(id) ON DELETE SET NULL,
    reward_text TEXT NOT NULL DEFAULT '',
    reward_json TEXT NOT NULL DEFAULT '{}',
    auto_grant INTEGER NOT NULL DEFAULT 0 CHECK(auto_grant IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quest_objectives (
    id TEXT PRIMARY KEY,
    quest_id TEXT NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'complete', 'failed')),
    order_index INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    stackable INTEGER NOT NULL DEFAULT 1 CHECK(stackable IN (0, 1)),
    consumable INTEGER NOT NULL DEFAULT 0 CHECK(consumable IN (0, 1)),
    max_charges INTEGER NOT NULL DEFAULT 0 CHECK(max_charges >= 0),
    charges INTEGER NOT NULL DEFAULT 0 CHECK(charges >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_id, name)
);

CREATE TABLE IF NOT EXISTS inventories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    owner_type TEXT NOT NULL CHECK(owner_type IN ('pc', 'npc', 'party')),
    owner_id TEXT NOT NULL,
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK(quantity >= 0),
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_id, owner_type, owner_id, item_id)
);

CREATE TABLE IF NOT EXISTS rumors (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    truth_status TEXT NOT NULL DEFAULT 'unknown' CHECK(truth_status IN ('true', 'false', 'unknown')),
    spread_level INTEGER NOT NULL DEFAULT 0 CHECK(spread_level >= 0),
    decay INTEGER NOT NULL DEFAULT 0 CHECK(decay >= 0),
    revealed_to_player INTEGER NOT NULL DEFAULT 0 CHECK(revealed_to_player IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS secrets (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    discovery_condition TEXT NOT NULL DEFAULT '',
    reveal_status TEXT NOT NULL DEFAULT 'hidden' CHECK(reveal_status IN ('hidden', 'revealed')),
    associated_rumor_id TEXT REFERENCES rumors(id) ON DELETE SET NULL,
    revealed_to_player INTEGER NOT NULL DEFAULT 0 CHECK(revealed_to_player IN (0, 1)),
    revealed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rumor_links (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    rumor_id TEXT NOT NULL REFERENCES rumors(id) ON DELETE CASCADE,
    secret_id TEXT NOT NULL REFERENCES secrets(id) ON DELETE CASCADE,
    min_spread_level INTEGER NOT NULL DEFAULT 1 CHECK(min_spread_level >= 0),
    auto_reveal INTEGER NOT NULL DEFAULT 1 CHECK(auto_reveal IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_id, rumor_id, secret_id)
);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK(source_type IN ('pc', 'npc', 'faction', 'location')),
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK(target_type IN ('pc', 'npc', 'faction', 'location')),
    target_id TEXT NOT NULL,
    trust INTEGER NOT NULL DEFAULT 0,
    fear INTEGER NOT NULL DEFAULT 0,
    debt INTEGER NOT NULL DEFAULT 0,
    reputation INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_id, source_type, source_id, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS clocks (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    current_segments INTEGER NOT NULL DEFAULT 0 CHECK(current_segments >= 0),
    max_segments INTEGER NOT NULL DEFAULT 4 CHECK(max_segments > 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'complete', 'abandoned')),
    scope TEXT NOT NULL DEFAULT 'local',
    updated_at TEXT NOT NULL,
    UNIQUE(campaign_id, name)
);

CREATE TABLE IF NOT EXISTS encounters (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'ended')),
    round_number INTEGER NOT NULL DEFAULT 1 CHECK(round_number >= 1),
    current_turn_index INTEGER NOT NULL DEFAULT 0 CHECK(current_turn_index >= 0),
    location_id TEXT REFERENCES locations(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS combatants (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK(source_type IN ('pc', 'npc', 'summon', 'hazard')),
    source_id TEXT,
    name TEXT NOT NULL,
    initiative INTEGER NOT NULL,
    turn_order_index INTEGER NOT NULL CHECK(turn_order_index >= 0),
    max_hp INTEGER NOT NULL CHECK(max_hp > 0),
    current_hp INTEGER NOT NULL CHECK(current_hp >= 0 AND current_hp <= max_hp),
    ac INTEGER NOT NULL DEFAULT 10,
    conditions_json TEXT NOT NULL DEFAULT '[]',
    concentration_spell TEXT NOT NULL DEFAULT '',
    position TEXT NOT NULL DEFAULT '',
    cover TEXT NOT NULL DEFAULT 'none',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    action_used INTEGER NOT NULL DEFAULT 0 CHECK(action_used IN (0, 1)),
    bonus_action_used INTEGER NOT NULL DEFAULT 0 CHECK(bonus_action_used IN (0, 1)),
    reaction_used INTEGER NOT NULL DEFAULT 0 CHECK(reaction_used IN (0, 1)),
    movement_used_ft INTEGER NOT NULL DEFAULT 0 CHECK(movement_used_ft >= 0)
);

CREATE TABLE IF NOT EXISTS conditions (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL CHECK(target_type IN ('pc', 'npc', 'combatant')),
    target_id TEXT NOT NULL,
    name TEXT NOT NULL,
    duration_rounds INTEGER NOT NULL DEFAULT 0 CHECK(duration_rounds >= 0),
    source TEXT NOT NULL DEFAULT '',
    started_turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS spells_active (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    caster_type TEXT NOT NULL CHECK(caster_type IN ('pc', 'npc', 'combatant')),
    caster_id TEXT NOT NULL,
    spell_name TEXT NOT NULL,
    target_type TEXT NOT NULL DEFAULT '',
    target_id TEXT NOT NULL DEFAULT '',
    remaining_rounds INTEGER NOT NULL DEFAULT 0 CHECK(remaining_rounds >= 0),
    requires_concentration INTEGER NOT NULL DEFAULT 0 CHECK(requires_concentration IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_rulings (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    ruling TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS roll_log (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    formula TEXT NOT NULL,
    raw_dice_json TEXT NOT NULL,
    selected_dice_json TEXT NOT NULL,
    modifier INTEGER NOT NULL,
    total INTEGER NOT NULL,
    context TEXT NOT NULL DEFAULT '',
    advantage_state TEXT NOT NULL DEFAULT 'none' CHECK(advantage_state IN ('none', 'advantage', 'disadvantage')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes_public (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes_hidden (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    command TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'committed' CHECK(stage IN ('staged', 'committed', 'discarded')),
    flushed_to_log INTEGER NOT NULL DEFAULT 1 CHECK(flushed_to_log IN (0, 1)),
    discarded_at TEXT
);

CREATE TABLE IF NOT EXISTS turn_diffs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn_id INTEGER NOT NULL UNIQUE REFERENCES turns(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    diff_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agenda_rules (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    effect_type TEXT NOT NULL,
    target_type TEXT NOT NULL DEFAULT '',
    target_id TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    cadence_turns INTEGER NOT NULL DEFAULT 1 CHECK(cadence_turns > 0),
    last_applied_turn INTEGER,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_facts (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    owner_type TEXT NOT NULL CHECK(owner_type IN ('pc', 'npc', 'faction')),
    owner_id TEXT NOT NULL,
    fact TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'private' CHECK(visibility IN ('private', 'public', 'discovered')),
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reward_events (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    turn_id INTEGER REFERENCES turns(id) ON DELETE SET NULL,
    source_type TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL DEFAULT '',
    recipient_type TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    reward_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_turns_campaign_status ON turns(campaign_id, status);
CREATE INDEX IF NOT EXISTS idx_events_campaign_turn ON events(campaign_id, turn_id);
CREATE INDEX IF NOT EXISTS idx_events_campaign_stage ON events(campaign_id, stage);
CREATE INDEX IF NOT EXISTS idx_roll_log_campaign_turn ON roll_log(campaign_id, turn_id);
CREATE INDEX IF NOT EXISTS idx_inventories_owner ON inventories(campaign_id, owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_location_discoveries_pc_time ON location_discoveries(campaign_id, pc_id, discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_combatants_encounter_order ON combatants(encounter_id, turn_order_index);
CREATE INDEX IF NOT EXISTS idx_turn_diffs_campaign_turn ON turn_diffs(campaign_id, turn_id);
CREATE INDEX IF NOT EXISTS idx_rumor_links_campaign ON rumor_links(campaign_id, rumor_id, secret_id);
CREATE INDEX IF NOT EXISTS idx_spells_active_caster ON spells_active(campaign_id, caster_type, caster_id);
CREATE INDEX IF NOT EXISTS idx_conditions_target ON conditions(campaign_id, target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_reward_events_campaign_turn ON reward_events(campaign_id, turn_id);
CREATE INDEX IF NOT EXISTS idx_reward_events_campaign_created ON reward_events(campaign_id, created_at DESC);
