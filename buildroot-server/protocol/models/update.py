from pydantic import BaseModel
from typing import List


class UpdateCheck(BaseModel):
    current_version: str = ""
    channel: str = "stable"


class UpdateInfo(BaseModel):
    has_update: bool = False
    current_version: str = ""
    latest_version: str = ""
    channel: str = "stable"
    version_code: int = 0
    file_size: int = 0
    download_url: str = ""
    sha512_checksum: str = ""
    md5_checksum: str = ""
    sha256_checksum: str = ""
    release_notes: str = ""
    mandatory: bool = False
    release_date: str = ""
    changes: List[str] = []
    request_id: str = ""


class UpdateDownload(BaseModel):
    version: str = ""
    request_id: str = ""


class UpdateApprove(BaseModel):
    status: str = ""
    download_url: str = ""
    file_size: int = 0
    md5_checksum: str = ""
    sha256_checksum: str = ""
    request_id: str = ""
    version: str = ""
    mandatory: bool = False
    approval_time: str = ""


class UpdateProgress(BaseModel):
    progress: int = 0
    message: str = ""
    status: str = ""
    request_id: str = ""


class UpdateComplete(BaseModel):
    version: str = ""
    success: bool = True
    message: str = ""
    request_id: str = ""


class UpdateError(BaseModel):
    error: str = ""
    status: str = ""
    request_id: str = ""


class UpdateRollback(BaseModel):
    backup_version: str = ""
    reason: str = ""
    success: bool = True
