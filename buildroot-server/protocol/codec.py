import json
import logging
from typing import Tuple, Optional, Dict, Any
from pydantic import BaseModel, ValidationError

from protocol.constants import MessageType
from protocol.models import (
    BaseMessage,
    RegisterRequest,
    RegisterResult,
    Heartbeat,
    SystemStatus,
    LogUpload,
    ScriptRecv,
    ScriptResult,
    PtyCreate,
    PtyData,
    PtyResize,
    PtyClose,
    FileRequest,
    FileData,
    FileListRequest,
    FileListResponse,
    FileUploadStart,
    FileUploadData,
    FileUploadAck,
    FileUploadComplete,
    FileDownloadRequest,
    FileDownloadData,
    DownloadPackage,
    CmdRequest,
    CmdResponse,
    DeviceList,
    UpdateCheck,
    UpdateInfo,
    UpdateDownload,
    UpdateApprove,
    UpdateProgress,
    UpdateComplete,
    UpdateError,
    UpdateRollback,
)

logger = logging.getLogger(__name__)


class MessageCodec:
    """消息编解码器"""

    MESSAGE_MODEL_MAP: Dict[int, type[BaseModel]] = {
        MessageType.REGISTER: RegisterRequest,
        MessageType.REGISTER_RESULT: RegisterResult,
        MessageType.HEARTBEAT: Heartbeat,
        MessageType.SYSTEM_STATUS: SystemStatus,
        MessageType.LOG_UPLOAD: LogUpload,
        MessageType.SCRIPT_RECV: ScriptRecv,
        MessageType.SCRIPT_RESULT: ScriptResult,
        MessageType.PTY_CREATE: PtyCreate,
        MessageType.PTY_DATA: PtyData,
        MessageType.PTY_RESIZE: PtyResize,
        MessageType.PTY_CLOSE: PtyClose,
        MessageType.FILE_REQUEST: FileRequest,
        MessageType.FILE_DATA: FileData,
        MessageType.FILE_LIST_REQUEST: FileListRequest,
        MessageType.FILE_LIST_RESPONSE: FileListResponse,
        MessageType.FILE_UPLOAD_START: FileUploadStart,
        MessageType.FILE_UPLOAD_DATA: FileUploadData,
        MessageType.FILE_UPLOAD_ACK: FileUploadAck,
        MessageType.FILE_UPLOAD_COMPLETE: FileUploadComplete,
        MessageType.FILE_DOWNLOAD_REQUEST: FileDownloadRequest,
        MessageType.FILE_DOWNLOAD_DATA: FileDownloadData,
        MessageType.DOWNLOAD_PACKAGE: DownloadPackage,
        MessageType.CMD_REQUEST: CmdRequest,
        MessageType.CMD_RESPONSE: CmdResponse,
        MessageType.DEVICE_LIST: DeviceList,
        MessageType.UPDATE_CHECK: UpdateCheck,
        MessageType.UPDATE_INFO: UpdateInfo,
        MessageType.UPDATE_DOWNLOAD: UpdateDownload,
        MessageType.UPDATE_APPROVE: UpdateApprove,
        MessageType.UPDATE_PROGRESS: UpdateProgress,
        MessageType.UPDATE_COMPLETE: UpdateComplete,
        MessageType.UPDATE_ERROR: UpdateError,
        MessageType.UPDATE_ROLLBACK: UpdateRollback,
    }

    @classmethod
    def encode(cls, msg_type: int, data: dict | BaseModel) -> bytes:
        """编码消息"""
        if isinstance(data, BaseModel):
            json_data = data.model_dump(exclude_none=True)
        else:
            json_data = data

        json_bytes = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
        json_len = len(json_bytes)

        msg = bytes([msg_type]) + json_len.to_bytes(2, "big") + json_bytes

        logger.debug(
            f"[CREATE_MSG] type=0x{msg_type:02X}, len={json_len}, hex={msg.hex()[:50]}...{msg.hex()[-30:] if len(msg.hex()) > 80 else ''}"
        )
        return msg

    @classmethod
    def decode(cls, raw_data: bytes) -> Tuple[Optional[int], Optional[dict]]:
        """解码消息"""
        if len(raw_data) < 3:
            return None, None

        msg_type = raw_data[0]
        length_bytes = raw_data[1:3]
        json_len = (length_bytes[0] << 8) | length_bytes[1]

        if len(raw_data) < 3 + json_len:
            logger.warning(
                f"消息不完整: 期望{3 + json_len}字节, 实际{len(raw_data)}字节"
            )
            return msg_type, {}

        json_data_bytes = raw_data[3 : 3 + json_len]

        try:
            json_str = json_data_bytes.decode("utf-8")
            if not json_str.strip():
                return msg_type, {}

            model_class = cls.MESSAGE_MODEL_MAP.get(msg_type, BaseMessage)
            model = model_class.model_validate_json(json_str)
            return msg_type, model.model_dump()

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"消息JSON解析失败: {e}")
            return msg_type, {}
        except ValidationError as e:
            logger.warning(f"消息数据验证失败: {e}")
            return msg_type, {}
