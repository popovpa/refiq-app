import secrets

SCRIPT_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
SCRIPT_ID_LENGTH = 5
SCRIPT_ID_PATTERN = rf"^[{SCRIPT_ID_ALPHABET}]{{{SCRIPT_ID_LENGTH}}}$"


def generate_script_id() -> str:
    return "".join(secrets.choice(SCRIPT_ID_ALPHABET) for _ in range(SCRIPT_ID_LENGTH))


def is_valid_script_id(value: str) -> bool:
    return len(value) == SCRIPT_ID_LENGTH and all(ch in SCRIPT_ID_ALPHABET for ch in value)
