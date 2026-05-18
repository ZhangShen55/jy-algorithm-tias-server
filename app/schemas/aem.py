# app/schemas/aem.py
from __future__ import annotations
from pydantic import BaseModel
from pydantic_settings import BaseSettings
# from pydantic import BaseModel, Field, BaseSettings
from typing import List, Optional

class AEMSettings(BaseSettings):
    AppName: str
    InstanceId: str
    IpAddr: str
    Port: int
    MetaData: MetaData_schemas
    KeepaliveInterval: int = 40

    # class Config:
    #     env_file = None

    # pydantic 2.x 配置方式
    model_config = {"env_file": None}
        
class MetaData_schemas(BaseModel):
    AlgVersion: Optional[str]
    AlgVendor:  Optional[str]
    TaskType:   Optional[List[int]]
    AppType:    str
    RunAlways:  Optional[int]
    Resource:   Optional[int]

class Register(BaseModel):
    AppName:    str
    InstanceId: str
    IpAddr:     str
    Port: Optional[int] = None
    MetaData:   MetaData_schemas

class UnRegister(BaseModel):
    AppName:    str
    InstanceId: str

class Keepalive(BaseModel):
    AppName:    str
    InstanceId: str

class ResponseStatus(BaseModel):
    RequestURL: Optional[str]
    StatusCode: int
    StatusString: str
    Id: Optional[str]
    LocalTime: Optional[str]


class RegisterRequest(BaseModel):
    Register: Register

class RegisterResponse(BaseModel):
    ResponseStatusObject: ResponseStatus

class UnRegisterRequest(BaseModel):
    UnRegister: UnRegister

class UnRegisterResponse(BaseModel):
    ResponseStatusObject: ResponseStatus

class KeepaliveRequest(BaseModel):
    Keepalive: Keepalive

class KeepaliveResponse(BaseModel):
    ResponseStatusObject: ResponseStatus