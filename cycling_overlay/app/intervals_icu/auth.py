from pydantic import BaseModel


class AthleteProfile(BaseModel):
    id: str = ""
    name: str = ""
    weight_kg: float | None = None
    ftp: int | None = None