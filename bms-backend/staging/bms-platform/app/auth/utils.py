from pwdlib import PasswordHash

# The below method is used to implement argon2 algorithm for password hashing
hasher = PasswordHash.recommended()

def password_hash(password: str) -> str:
    """Hashes a plain-text password using argon2."""
    return hasher.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """Verifies a plain-text password against a hashed password."""
    return hasher.verify(password, hashed_password)
