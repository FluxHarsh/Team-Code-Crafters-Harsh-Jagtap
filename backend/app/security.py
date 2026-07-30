"""
Symmetric encryption for secrets we must store at rest — currently just
github_connections.access_token (architecture doc Section 3.1).

Not an auth system (there is none — Section 4). This only protects the
token value sitting in the database.
"""

from cryptography.fernet import Fernet

from app.config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    if not settings.github_token_encryption_key:
        raise RuntimeError(
            "GITHUB_TOKEN_ENCRYPTION_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return Fernet(settings.github_token_encryption_key.encode())


def encrypt_token(plaintext: str) -> str:
    """Returns ciphertext safe to store in github_connections.access_token."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Reverses encrypt_token(). Raises cryptography.fernet.InvalidToken
    if the key changed or the ciphertext was tampered with."""
    return _fernet().decrypt(ciphertext.encode()).decode()
