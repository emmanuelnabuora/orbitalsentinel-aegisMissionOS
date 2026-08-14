import pytest

from aegis_api.core import security


def test_password_hash_roundtrip():
    hashed = security.hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert security.verify_password("correct horse battery staple", hashed)
    assert not security.verify_password("wrong", hashed)


def test_access_token_roundtrip_carries_subject_and_roles():
    token = security.create_access_token("user-42", roles=["operator"])
    claims = security.decode_access_token(token)
    assert claims["sub"] == "user-42"
    assert claims["roles"] == ["operator"]
    assert claims["iss"] == "aegis-missionos"
    assert claims["jti"]


def test_tampered_token_is_rejected():
    token = security.create_access_token("user-42")
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(security.TokenError):
        security.decode_access_token(tampered)


def test_token_with_wrong_issuer_is_rejected():
    import jwt as pyjwt

    from aegis_api.core.config import get_settings

    s = get_settings()
    forged = pyjwt.encode(
        {"sub": "x", "iss": "someone-else", "iat": 0, "exp": 2**31},
        s.secret_key,
        algorithm="HS256",
    )
    with pytest.raises(security.TokenError):
        security.decode_access_token(forged)
