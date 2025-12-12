from pydantic import BaseModel, Field
from datetime import datetime, date
from ..users.schemas import UserResponse


class SeriesCreate(BaseModel):
    project_id: int
    title: str
    start_date: date
    first_deadline: date
    second_deadline: date
    exp_publish_date: date
    raw_url: str
    srt: str
    ass: str
    result_url: str
    curator: UserResponse
    sound_engineer: UserResponse
    sound_engineer_minus: UserResponse
    timer: UserResponse
    translator: UserResponse
