from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.postback.models import PostbackCredential
from app.modules.postback.repository import PostbackRepository
from app.modules.postback.token import hash_postback_token
from app.modules.postback.validator import PostbackValidator, unauthorized


class PostbackAuthenticationService:
    def __init__(self, db: AsyncSession):
        self.repository = PostbackRepository(db)
        self.validator = PostbackValidator()

    async def authenticate(self, authorization: str | None) -> PostbackCredential:
        token = self.validator.parse_bearer(authorization)
        credential = await self.repository.get_active_by_hash(hash_postback_token(token))
        if not credential:
            raise unauthorized()
        return credential
