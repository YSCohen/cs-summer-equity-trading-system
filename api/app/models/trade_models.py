from pydantic import BaseModel


class Trade(BaseModel):
    account_id: str
    direction: str
    ticker: str
    quantity: int
    price: float
    other_account: str | None = None
