"""Prompt intent extraction for context optimization.

Maps natural-language keywords in user prompts to Home Assistant
domains and actions so the conversation handler can pre-filter
entities before injecting them as LLM context.
"""

from __future__ import annotations

from typing import Any

DOMAIN_KEYWORDS: dict[str, str] = {
    # Español
    "luces": "light",
    "luz": "light",
    "iluminaci": "light",
    "foco": "light",
    "focos": "light",
    "bombilla": "light",
    "termotato": "climate",
    "temperatura": "climate",
    "calefacci": "climate",
    "calor": "climate",
    "frio": "climate",
    "persiana": "cover",
    "persianas": "cover",
    "cortina": "cover",
    "cortinas": "cover",
    "ventilador": "fan",
    "ventiladores": "fan",
    "cerradura": "lock",
    "cerraduras": "lock",
    "puerta": "lock",
    "camara": "camera",
    "cámaras": "camera",
    "tv": "media_player",
    "televisi": "media_player",
    "altavoz": "media_player",
    "aspiradora": "vacuum",
    "robot": "vacuum",
    "alarma": "alarm_control_panel",
    "sensor": "sensor",
    "sensores": "sensor",
    "humo": "binary_sensor",
    "movimiento": "binary_sensor",
    "humedad": "sensor",
    "consumo": "sensor",
    "energia": "sensor",
    "persiana": "cover",
    "enchufe": "switch",
    "switch": "switch",
    "riego": "valve",
    "valvula": "valve",
    # English
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "thermostat": "climate",
    "temperature": "climate",
    "heating": "climate",
    "blinds": "cover",
    "curtain": "cover",
    "shade": "cover",
    "shades": "cover",
    "fan": "fan",
    "fans": "fan",
    "lock": "lock",
    "locks": "lock",
    "door": "lock",
    "doors": "lock",
    "camera": "camera",
    "cameras": "camera",
    "speaker": "media_player",
    "vacuum": "vacuum",
    "alarm": "alarm_control_panel",
    "sensor": "sensor",
    "sensors": "sensor",
    "motion": "binary_sensor",
    "smoke": "binary_sensor",
    "humidity": "sensor",
    "power": "sensor",
    "energy": "sensor",
    "switch": "switch",
    "plug": "switch",
    "valve": "valve",
    "sprinkler": "valve",
}

ACTION_KEYWORDS: dict[str, str] = {
    # Español
    "enciende": "turn_on",
    "prende": "turn_on",
    "activa": "turn_on",
    "encienda": "turn_on",
    "prenda": "turn_on",
    "apaga": "turn_off",
    "desactiva": "turn_off",
    "apague": "turn_off",
    "sube": "open_cover",
    "abre": "open_cover",
    "subir": "open_cover",
    "abrir": "open_cover",
    "baja": "close_cover",
    "cierra": "close_cover",
    "bajar": "close_cover",
    "cerrar": "close_cover",
    "pon": "turn_on",
    "saca": "turn_off",
    # English
    "turn on": "turn_on",
    "switch on": "turn_on",
    "enable": "turn_on",
    "activate": "turn_on",
    "turn off": "turn_off",
    "switch off": "turn_off",
    "disable": "turn_off",
    "deactivate": "turn_off",
    "open": "open_cover",
    "close": "close_cover",
    "raise": "open_cover",
    "lower": "close_cover",
}


def extract_prompt_intent(prompt: str) -> dict[str, Any]:
    """Extract domain_hint, action_hint from a natural-language prompt.

    Returns a dict with:
      - ``domain_hint``: matched domain (e.g. ``"light"``) or ``None``
      - ``action_hint``: matched action (e.g. ``"turn_on"``) or ``None``
    """
    lower = prompt.lower()

    domain_hint: str | None = None
    for keyword, domain in DOMAIN_KEYWORDS.items():
        if keyword in lower:
            domain_hint = domain
            break

    action_hint: str | None = None
    for keyword, action in ACTION_KEYWORDS.items():
        if keyword in lower:
            action_hint = action
            break

    return {
        "domain_hint": domain_hint,
        "action_hint": action_hint,
    }
