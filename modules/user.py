from flask_login import UserMixin

from modules.db import get_db


class User(UserMixin):

    def __init__(self, id_, name, region, email, profile_pic):
        self.id = id_
        self.name = name
        self.region = region
        self.email = email
        self.profile_pic = profile_pic

    def __repr__(self):
        return f"User_{self.id}({self.name}:{self.region}, email={self.email}, pic={self.profile_pic})"

    @staticmethod
    def get(user_id):
        db = get_db()
        user = db.execute(
            "SELECT * FROM user WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return None

        user = User(
            id_=user[0], name=user[1], region=user[2], email=user[3], profile_pic=user[4]
        )
        return user

    @staticmethod
    def create(id_, name, region, email, profile_pic):
        db = get_db()
        db.execute(
            "INSERT INTO user (id, name, region, email, profile_pic)"
            " VALUES (?, ?, ?, ?, ?)",
            (id_, name, region, email, profile_pic),
        )
        db.commit()
