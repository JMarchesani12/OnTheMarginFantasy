import logging
from sqlite3 import IntegrityError
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine


class UserModel:
    def __init__(self, db: Engine):
        self.db = db

    def create_user(
        self,
        email: str,
        display_name: Optional[str] = None,
        uuid: str = None,
    ) -> Dict[str, Any]:
        """
        Inserts into public."User" (email, displayName, uuid).

        - email is required + unique
        - displayName optional
        - uuid must exist in auth.users(id) due to FK
        """

        if not email or not email.strip():
            raise ValueError("email is required")

        email = email.strip()
        display_name = (display_name or "").strip()

        try:
            with self.db.begin() as conn:
                row = conn.execute(
                    text("""
                        INSERT INTO "User" (email, "displayName", uuid)
                        VALUES (:email, :displayName, :uuid)
                        RETURNING
                          id,
                          "createdAt",
                          email,
                          "displayName",
                          uuid
                    """),
                    {
                        "email": email,
                        "displayName": display_name,
                        "uuid": uuid,
                    },
                ).fetchone()

                if not row:
                    raise RuntimeError("Failed to insert User")

                user = dict(row._mapping)

            logging.debug("Created user: %s", user)
            return user

        except IntegrityError as e:
            # Could be: unique(email) violation OR FK(uuid->auth.users) violation
            msg = str(getattr(e, "orig", e))
            raise ValueError(f"User creation failed: {msg}")