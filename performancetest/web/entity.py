# _*_ coding: utf-8 _*_

from builtins import *

from pydantic import BaseModel


class TaskEntity(BaseModel):
    serialno: str
    port: int
    package: str
    platform: str  # android | ios | pc


class DeviceEntity(BaseModel):
    serialno: str
    platform: str  # android | ios | pc


class PackageEntity(BaseModel):
    serialno: str
    package: str
    platform: str  # android | ios | pc
