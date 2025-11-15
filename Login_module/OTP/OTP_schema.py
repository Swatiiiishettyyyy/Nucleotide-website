from pydantic import BaseModel, Field
from typing import Optional


# Request schemas
class SendOTPRequest(BaseModel):
    country_code: str = Field(..., example="+91")
    mobile: str = Field(..., example="9876543210")
    purpose: Optional[str] = Field("login", example="login")


class VerifyOTPRequest(BaseModel):
    country_code: str = Field(..., example="+91")
    mobile: str = Field(..., example="9876543210")
    otp: str = Field(..., example="123456")
    device_id: str = Field(..., example="device-uuid-or-imei")
    device_platform: Optional[str] = Field(..., example="web")  # web/mobile/ios
    device_details: Optional[str] = Field(None, example='{"browser":"Chrome", "version":"..."}')


# Response schemas
class OTPData(BaseModel):
    mobile: str
    otp: str
    expires_in: int
    purpose: Optional[str]


class SendOTPResponse(BaseModel):
    status: str = "success"
    message: str
    data: OTPData


class VerifiedData(BaseModel):
    user_id: int
    name: Optional[str]
    mobile: str
    email: Optional[str]
    access_token: str
    token_type: str
    expires_in: int


class VerifyOTPResponse(BaseModel):
    status: str = "success"
    message: str
    data: VerifiedData