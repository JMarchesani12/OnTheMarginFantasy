from typing import Any, Dict, Optional

from sqlalchemy.engine import Engine

from .contracts import ALLOWED_USER_FIELDS, ProfileNotFound, ProfileUpdateRejected, ProfileCreationRejected
from .service import UserService

class UserModel:
    def __init__(self, db: Engine):
        self.db = db
        self._user_service = UserService(db)

    def get_user_by_id(self, user_id: int) -> Dict[str, Any]:
        try:
            return self._user_service.get_profile_for_job(user_id)
        except ProfileNotFound as exc:
            raise ValueError(str(exc)) from exc
    
    def get_user_by_uuid(self, uuid: str) -> Dict[str, Any]:
        try:
            return self._user_service.get_profile_by_uuid_for_job(uuid)
        except ProfileNotFound as exc:
            raise ValueError(str(exc)) from exc


    def create_user(
        self,
        email: str,
        display_name: Optional[str] = None,
        uuid: str = None,
    ) -> Dict[str, Any]:
        try:
            return self._user_service.create_profile_for_job(email, display_name, uuid)
        except ProfileCreationRejected as exc:
            raise ValueError(str(exc)) from exc
        
    def update_user(self, user_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._user_service.update_profile_for_job(user_id, updates)
        except (ProfileNotFound, ProfileUpdateRejected) as exc:
            raise ValueError(str(exc)) from exc
