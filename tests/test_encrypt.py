import os
import importlib


def test_encrypt_decrypt_roundtrip(tmp_path, monkeypatch):
    # Ensure env for keys
    monkeypatch.setenv('MASTER_KEY', 'test_master_key_123')
    monkeypatch.setenv('IV_KEY', 'test_iv_key_123')
    monkeypatch.setenv('OWNER_ID', '123456')

    # reload module to pick up env
    import utils.encrypt as enc
    importlib.reload(enc)

    original = 'hello world 这是一些中文'
    ciphertext = enc.encrypt_str(original)
    assert isinstance(ciphertext, str) and ciphertext
    plaintext = enc.decrypt_str(ciphertext)
    assert plaintext == original
