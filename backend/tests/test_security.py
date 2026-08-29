import uuid

from app.security import decode_token, hash_password, token_pair, verify_password


def test_password_hash_round_trip():
    encoded = hash_password("a-very-secure-password")
    assert verify_password("a-very-secure-password", encoded)
    assert not verify_password("incorrect", encoded)


def test_access_token_round_trip():
    user_id = uuid.uuid4()
    access, _ = token_pair(user_id)
    assert decode_token(access, "access") == user_id

