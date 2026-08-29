import secrets

SHORT_CODE_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
SHORT_CODE_LENGTH = 7
SHORT_CODE_PATTERN = rf"^[{SHORT_CODE_ALPHABET}]{{{SHORT_CODE_LENGTH}}}$"


def generate_short_code() -> str:
    return "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(SHORT_CODE_LENGTH))


def is_valid_short_code(value: str) -> bool:
    return len(value) == SHORT_CODE_LENGTH and all(ch in SHORT_CODE_ALPHABET for ch in value)
