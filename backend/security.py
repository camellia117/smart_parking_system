"""密码哈希与校验（bcrypt）；兼容历史明文以便平滑升级。"""
import secrets
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
BCRYPT_MAX_LEN = 72


def hash_password(plain: str) -> str:
    if not plain or not plain.strip():
        raise ValueError("密码不能为空")
    p = plain.strip()[:BCRYPT_MAX_LEN]
    return pwd_context.hash(p)


def verify_password(plain: str, stored_hash: str) -> bool:
    if not plain or not stored_hash:
        return False
    p = plain.strip()[:BCRYPT_MAX_LEN]
    if stored_hash.startswith("$2"):
        return pwd_context.verify(p, stored_hash)
    return secrets.compare_digest(stored_hash, plain.strip())


def needs_rehash(stored: str) -> bool:
    return bool(stored) and not stored.startswith("$2")
