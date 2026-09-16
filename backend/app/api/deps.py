from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_session
from app.modules.auth.service import current_user

DbSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]
