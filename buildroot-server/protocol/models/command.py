from pydantic import BaseModel
from typing import List


class CmdRequest(BaseModel):
    cmd: str = ""
    request_id: str = ""


class CmdResponse(BaseModel):
    request_id: str = ""
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""


class DeviceList(BaseModel):
    devices: List[dict] = []
    count: int = 0
