from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - field default, not a secret
    expires_in: int


class LoginResponse(BaseModel):
    """Either full tokens (no MFA) or an MFA challenge."""

    mfa_required: bool = False
    mfa_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    token_type: str = "bearer"  # noqa: S105 - OAuth2 token type, not a credential


class MFAVerifyRequest(BaseModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=32)


class MFASetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_svg: str


class MFAActivateRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class MFAActivateResponse(BaseModel):
    recovery_codes: list[str]
    message: str = "Store these codes securely; each works once and they are never shown again."


class MFADisableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)
