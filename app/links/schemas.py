from pydantic import BaseModel, ConfigDict


class LinkResponse(BaseModel):
    id: int
    link_title: str
    link_url: str

    model_config = ConfigDict(from_attributes=True)


class LinkCreate(BaseModel):
    link_title: str
    link_url: str
