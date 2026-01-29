from pydantic import BaseModel, ConfigDict


class FileResponse(BaseModel):
    id: int
    filename: str
    file_url: str
    category: str

    model_config = ConfigDict(from_attributes=True)
