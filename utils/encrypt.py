"""
utils.encrypt
简洁的 AES-256-GCM 加密/解密工具。
注意：MASTER_KEY 与 IV_KEY 应由环境变量提供（见 `.env`）。
"""
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import base64
import os
from config import MASTER_KEY as MASTER_KEY_ENV, IV_KEY as IV_KEY_ENV


def derive_key(password: str = MASTER_KEY_ENV, salt: str = IV_KEY_ENV, length: int = 32, iterations: int = 300000) -> bytes:
    """Derive a symmetric key from password+salt using PBKDF2-HMAC-SHA256."""
    pw = password.encode()
    sl = salt.encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=sl,
        iterations=iterations,
    )
    return kdf.derive(pw)


def encrypt_str(plain_text: str) -> str:
    """Encrypt a UTF-8 string and return base64(nonce + tag + ciphertext)."""
    key = derive_key()
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce))
    encryptor = cipher.encryptor()
    pt = plain_text.encode()
    ct = encryptor.update(pt) + encryptor.finalize()
    tag = encryptor.tag
    return base64.b64encode(nonce + tag + ct).decode()


def decrypt_str(enc_b64: str) -> str:
    """Decrypt base64(nonce + tag + ciphertext) and return UTF-8 string."""
    key = derive_key()
    data = base64.b64decode(enc_b64.encode())
    nonce = data[:12]
    tag = data[12:28]
    ct = data[28:]
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag))
    decryptor = cipher.decryptor()
    pt = decryptor.update(ct) + decryptor.finalize()
    return pt.decode()

# Backwards compatibility aliases (old short names)
dyk = derive_key
ecs = encrypt_str
dcs = decrypt_str
