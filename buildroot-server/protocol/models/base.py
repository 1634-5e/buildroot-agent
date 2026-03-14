from pydantic import BaseModel, ConfigDict


class BaseMessage(BaseModel):
    """基础消息模型"""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)
