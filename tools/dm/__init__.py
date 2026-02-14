"""Local DM tooling package for Dungeons and Agents."""

from .ui_contract import (  # noqa: F401
    CANONICAL_ENVELOPE_KEYS,
    DEFAULT_FREEFORM_HINT,
    DEFAULT_PROMPT,
    TEMPLATE_IDS,
    UI_CONTRACT_VERSION,
    UIContractError,
    build_envelope,
    default_choices,
    parse_choice_input,
    render_markdown,
    render_numbered_choices,
    required_sections,
    resolve_template_id,
    validate_envelope,
    validate_envelope_or_raise,
)
