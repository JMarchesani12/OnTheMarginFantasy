"""Profile persistence on supplied connections; no engine or transaction owner."""
from sqlalchemy import text
from .contracts import ALLOWED_USER_FIELDS


class UserRepository:
    def profile_ids_for_subject(self, conn, subject):
        return conn.execute(text('SELECT id FROM "User" WHERE uuid = :subject LIMIT 2'),
                            {'subject': subject}).mappings().fetchmany(2)

    def get_by_uuid(self, conn, uuid):
        row = conn.execute(text('''
            SELECT id, uuid, email, "displayName", "createdAt"
            FROM "User" WHERE uuid = :uuid
        '''), {'uuid': uuid}).mappings().first()
        return dict(row) if row else None

    def insert(self, conn, email, display_name, uuid):
        row = conn.execute(text('''
            INSERT INTO "User" (email, "displayName", uuid)
            VALUES (:email, :displayName, :uuid)
            RETURNING id, "createdAt", email, "displayName", uuid
        '''), {'email': email, 'displayName': display_name, 'uuid': uuid}).fetchone()
        return dict(row._mapping) if row else None

    def get_by_id(self, conn, user_id):
        row = conn.execute(text('''
            SELECT id, uuid, email, "displayName", "createdAt"
            FROM "User" WHERE id = :userId
        '''), {'userId': user_id}).mappings().first()
        return dict(row) if row else None

    def update(self, conn, user_id, payload):
        # Column identifiers come solely from the fixed server-side allowlist.
        clauses = []
        params = {'userId': user_id}
        for i, (key, value) in enumerate(payload.items()):
            name = f'v{i}'
            clauses.append(f'{ALLOWED_USER_FIELDS[key]} = :{name}')
            params[name] = value
        row = conn.execute(text(f'''
            UPDATE "User" SET {", ".join(clauses)} WHERE id = :userId
            RETURNING id, uuid, email, "displayName", "createdAt"
        '''), params).mappings().first()
        return dict(row) if row else None
