from typing import Protocol

from app.modules.email.dto import EmailMessage


class EmailProvider(Protocol):
    async def send(self, message: EmailMessage) -> None: ...
