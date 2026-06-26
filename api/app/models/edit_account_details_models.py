from pydantic import BaseModel


class Details(BaseModel):
    account_name: str | None = None
    can_short: bool | None = None
