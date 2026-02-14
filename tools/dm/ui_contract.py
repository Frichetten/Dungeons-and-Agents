"""Shared UI contract helpers for player-facing game output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

UI_CONTRACT_VERSION = "1.0"
DEFAULT_PROMPT = "What do you do?"
DEFAULT_FREEFORM_HINT = ""
DEFAULT_CHOICE_COUNT = 0

CANONICAL_ENVELOPE_KEYS = (
    "ui_contract_version",
    "template_id",
    "title",
    "sections",
    "choices",
    "freeform_hint",
    "prompt",
)


class UIContractError(Exception):
    """Raised when the UI contract is violated."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


@dataclass(frozen=True)
class SectionSpec:
    section_id: str
    label: str


@dataclass(frozen=True)
class TemplateSpec:
    template_id: str
    required_sections: Tuple[SectionSpec, ...]
    actionable: bool
    choice_count: int


def _sec(section_id: str, label: str) -> SectionSpec:
    return SectionSpec(section_id=section_id, label=label)


TEMPLATE_REGISTRY: Dict[str, TemplateSpec] = {
    "scene_turn": TemplateSpec(
        template_id="scene_turn",
        required_sections=(
            _sec("rolls", "Rolls"),
            _sec("scene", "Scene"),
            _sec("outcome", "Outcome"),
        ),
        actionable=True,
        choice_count=DEFAULT_CHOICE_COUNT,
    ),
    "dialogue_turn": TemplateSpec(
        template_id="dialogue_turn",
        required_sections=(
            _sec("rolls", "Rolls"),
            _sec("scene", "Scene"),
            _sec("outcome", "Outcome"),
        ),
        actionable=True,
        choice_count=DEFAULT_CHOICE_COUNT,
    ),
    "combat_turn": TemplateSpec(
        template_id="combat_turn",
        required_sections=(
            _sec("rolls", "Rolls"),
            _sec("scene", "Scene"),
            _sec("outcome", "Outcome"),
        ),
        actionable=True,
        choice_count=DEFAULT_CHOICE_COUNT,
    ),
    "exploration_turn": TemplateSpec(
        template_id="exploration_turn",
        required_sections=(
            _sec("rolls", "Rolls"),
            _sec("scene", "Scene"),
            _sec("outcome", "Outcome"),
        ),
        actionable=True,
        choice_count=DEFAULT_CHOICE_COUNT,
    ),
    "skill_check_turn": TemplateSpec(
        template_id="skill_check_turn",
        required_sections=(
            _sec("rolls", "Rolls"),
            _sec("scene", "Scene"),
            _sec("outcome", "Outcome"),
        ),
        actionable=True,
        choice_count=DEFAULT_CHOICE_COUNT,
    ),
    "ooc_panel": TemplateSpec(
        template_id="ooc_panel",
        required_sections=(
            _sec("overview", "Overview"),
            _sec("resources", "Resources"),
            _sec("objectives", "Objectives"),
            _sec("world", "World"),
        ),
        actionable=False,
        choice_count=0,
    ),
    "system_error": TemplateSpec(
        template_id="system_error",
        required_sections=(
            _sec("error", "Error"),
            _sec("rollback", "Rollback"),
            _sec("recovery", "Recovery"),
        ),
        actionable=True,
        choice_count=DEFAULT_CHOICE_COUNT,
    ),
}

TEMPLATE_IDS = tuple(TEMPLATE_REGISTRY.keys())


def get_template_spec(template_id: str) -> TemplateSpec:
    spec = TEMPLATE_REGISTRY.get(template_id)
    if spec is None:
        raise UIContractError("unknown_template_id", {"template_id": template_id, "allowed": list(TEMPLATE_IDS)})
    return spec


def required_sections(template_id: str) -> List[Dict[str, str]]:
    spec = get_template_spec(template_id)
    return [{"id": item.section_id, "label": item.label} for item in spec.required_sections]


def resolve_template_id(state: Mapping[str, Any]) -> str:
    if state.get("error"):
        return "system_error"
    if state.get("ooc_action"):
        return "ooc_panel"
    if state.get("combat"):
        return "combat_turn"
    if state.get("dialogue"):
        return "dialogue_turn"
    if state.get("skill_check"):
        return "skill_check_turn"
    if state.get("exploration"):
        return "exploration_turn"
    return "scene_turn"


def default_choices(template_id: str) -> List[Dict[str, str]]:
    _ = template_id
    return []


def _coerce_sections(spec: TemplateSpec, section_content: Mapping[str, Any]) -> List[Dict[str, str]]:
    sections: List[Dict[str, str]] = []
    for item in spec.required_sections:
        content = section_content.get(item.section_id, "No update.")
        sections.append({"id": item.section_id, "label": item.label, "content": str(content)})
    return sections


def build_envelope(
    template_id: str,
    title: str,
    *,
    sections: Optional[List[Dict[str, Any]]] = None,
    section_content: Optional[Mapping[str, Any]] = None,
    choices: Optional[List[Dict[str, Any]]] = None,
    freeform_hint: Optional[str] = None,
    prompt: Optional[str] = None,
) -> Dict[str, Any]:
    spec = get_template_spec(template_id)

    if not isinstance(title, str) or not title.strip():
        raise UIContractError("invalid_title", {"title": title})

    if sections is None:
        sections = _coerce_sections(spec, section_content or {})
    if choices is None:
        choices = default_choices(template_id)

    if freeform_hint is None:
        freeform_hint = DEFAULT_FREEFORM_HINT
    if prompt is None:
        prompt = DEFAULT_PROMPT if spec.actionable else ""

    envelope = {
        "ui_contract_version": UI_CONTRACT_VERSION,
        "template_id": template_id,
        "title": title.strip(),
        "sections": sections,
        "choices": choices,
        "freeform_hint": freeform_hint,
        "prompt": prompt,
    }
    validate_envelope_or_raise(envelope)
    return envelope


def validate_envelope(envelope: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(envelope, Mapping):
        return ["Envelope must be an object."]

    actual_keys = list(envelope.keys())
    if actual_keys != list(CANONICAL_ENVELOPE_KEYS):
        errors.append(
            f"Envelope keys must match canonical order {list(CANONICAL_ENVELOPE_KEYS)}; got {actual_keys}."
        )

    version = envelope.get("ui_contract_version")
    if version != UI_CONTRACT_VERSION:
        errors.append(f"ui_contract_version must be {UI_CONTRACT_VERSION}.")

    template_id = envelope.get("template_id")
    if not isinstance(template_id, str) or template_id not in TEMPLATE_REGISTRY:
        errors.append(f"template_id must be one of {list(TEMPLATE_IDS)}.")
        return errors

    spec = TEMPLATE_REGISTRY[template_id]

    title = envelope.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("title must be a non-empty string.")

    sections = envelope.get("sections")
    if not isinstance(sections, list):
        errors.append("sections must be a list.")
    else:
        expected = spec.required_sections
        if len(sections) != len(expected):
            errors.append(f"sections must contain exactly {len(expected)} entries for {template_id}.")
        for idx, expected_section in enumerate(expected):
            if idx >= len(sections):
                break
            section = sections[idx]
            if not isinstance(section, Mapping):
                errors.append(f"sections[{idx}] must be an object.")
                continue
            section_id = section.get("id")
            section_label = section.get("label")
            if section_id != expected_section.section_id:
                errors.append(
                    f"sections[{idx}].id must be '{expected_section.section_id}', got '{section_id}'."
                )
            if section_label != expected_section.label:
                errors.append(
                    f"sections[{idx}].label must be '{expected_section.label}', got '{section_label}'."
                )
            content = section.get("content")
            if not isinstance(content, str) or not content.strip():
                errors.append(f"sections[{idx}].content must be a non-empty string.")

    choices = envelope.get("choices")
    if not isinstance(choices, list):
        errors.append("choices must be a list.")
        choices = []

    if spec.actionable:
        if len(choices) != spec.choice_count:
            errors.append(f"choices must be empty for actionable template {template_id}.")
        if envelope.get("freeform_hint") != "":
            errors.append(f"freeform_hint must be empty for actionable template {template_id}.")
        prompt = envelope.get("prompt")
        if prompt != DEFAULT_PROMPT:
            errors.append(f"prompt must exactly match '{DEFAULT_PROMPT}' for actionable templates.")
    else:
        if len(choices) != 0:
            errors.append(f"choices must be empty for non-actionable template {template_id}.")
        if envelope.get("freeform_hint") != "":
            errors.append(f"freeform_hint must be empty for non-actionable template {template_id}.")
        if envelope.get("prompt") != "":
            errors.append(f"prompt must be empty for non-actionable template {template_id}.")

    return errors


def validate_envelope_or_raise(envelope: Mapping[str, Any]) -> None:
    errors = validate_envelope(envelope)
    if errors:
        raise UIContractError("invalid_ui_envelope", {"errors": errors})


def parse_choice_input(user_input: str, envelope_or_choices: Any) -> Dict[str, Any]:
    if isinstance(envelope_or_choices, Mapping):
        choices = envelope_or_choices.get("choices", [])
    else:
        choices = envelope_or_choices

    if not isinstance(choices, Sequence):
        raise UIContractError("invalid_choices", {"choices": choices})

    text = str(user_input or "").strip()
    if not text:
        raise UIContractError("invalid_choice_input", {"reason": "empty"})

    if text.isdigit():
        index = int(text) - 1
        if 0 <= index < len(choices):
            choice = choices[index]
            if isinstance(choice, Mapping):
                return {"kind": "preset", "choice_id": str(choice.get("id", text)), "choice": dict(choice)}

    for choice in choices:
        if isinstance(choice, Mapping) and text == str(choice.get("label", "")):
            return {"kind": "preset", "choice_id": str(choice.get("id", "")), "choice": dict(choice)}

    return {"kind": "freeform", "text": text}


def render_numbered_choices(choices: Sequence[Mapping[str, Any]]) -> List[str]:
    lines: List[str] = []
    for index, choice in enumerate(choices, start=1):
        label = str(choice.get("label", "")).strip()
        intent = str(choice.get("intent", "")).strip()
        risk = str(choice.get("risk", "")).strip()
        tone = str(choice.get("tone", "")).strip()
        details = [part for part in [f"Intent: {intent}" if intent else "", f"Risk: {risk}" if risk else ""] if part]
        if tone:
            details.append(f"Tone: {tone}")
        if details:
            lines.append(f"{index}. {label} ({'; '.join(details)})")
        else:
            lines.append(f"{index}. {label}")
    return lines


def render_markdown(envelope: Mapping[str, Any]) -> str:
    validate_envelope_or_raise(envelope)
    lines: List[str] = [f"### {envelope['title']}"]
    for section in envelope["sections"]:
        lines.append(f"{section['label']}:")
        lines.append(str(section["content"]))
    choices = envelope["choices"]
    if choices:
        lines.append("Choices:")
        lines.extend(render_numbered_choices(choices))
        lines.append(str(envelope["freeform_hint"]))
    prompt = str(envelope["prompt"])
    if prompt:
        lines.append(prompt)
    return "\n".join(lines)
