"""Password hashing with Argon2id.

Passwords are never stored or logged. Only the salted hash is kept, and the
parameters travel inside the hash string, so they can be raised later without
a migration (see needs_rehash).
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True only if the password matches. A malformed hash is a failure, not an error."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True if the hash was made with weaker parameters than the current defaults."""
    return _hasher.check_needs_rehash(password_hash)
