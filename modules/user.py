from abc import *
from flask_login import UserMixin

from modules.db import get_db, commit


class RDMS(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self):
        pass

    @staticmethod
    def get_one_raw(param_name, identifier, destination) -> list:
        db = get_db()
        query = r"%s"
        db.execute(
            f"SELECT * FROM `{destination}` WHERE {param_name} = %s LIMIT 1", (
                identifier, )
        )
        value = db.fetchone()
        return value

    @staticmethod
    def get_all_raw(param_name, identifier, destination) -> list[list]:
        db = get_db()

        db.execute(
            f"SELECT * FROM `{destination}` WHERE {param_name} = %s", (
                identifier, )
        )
        values = db.fetchone()
        return values

    @abstractmethod
    def get(identifier):
        pass

    @abstractmethod
    def create(self):
        pass


class User(UserMixin, RDMS):
    DBNAME = 'student_info'

    def __init__(self, id_, dep_id, name, email, profile_pic):
        self.id = id_
        self.dep_id = int(dep_id)
        self.name = name
        self.email = email
        self.profile_pic = profile_pic

    def __repr__(self):
        return f"User_{self.id}({self.name}:{self.dep_id}, email={self.email}, pic={self.profile_pic})"

    @staticmethod
    def get(user_id):
        user = User.get_one_raw('stu_id', user_id, User.DBNAME)
        if not user:
            return None

        return User(*user)

    @staticmethod
    def get_by_departure(dep_id):
        users = User.get_all_raw('dep_id', dep_id, User.DBNAME)
        if not users:
            return None
        return [User(*user) for user in users]

    def get_departure_name(self) -> str:
        return Department.get(self.dep_id).name

    @staticmethod
    def create(id_, dep_id, name, email, profile_pic):
        db = get_db()
        db.execute(
            f"INSERT INTO `{User.DBNAME}` (stu_id, dep_id, name, email, profile_pic) VALUES (%s, %s, %s, %s, %s)",
            (id_, dep_id, name, email, profile_pic),
        )
        commit()


class Department(RDMS):
    DBNAME = 'department_info'

    def __init__(self, id_, name):
        self.dep_id = int(id_)
        self.name = name

    def __repr__(self):
        return f"Department_{self.dep_id}(name={self.name})"

    @staticmethod
    def get(dep_id):
        department_info = Department.get_one_raw(
            'dep_id', dep_id, Department.DBNAME)
        if not department_info:
            return None
        return Department(*department_info)

    @staticmethod
    def get_id_by_name(name):
        department = Department.get_one_raw('name', name, Department.DBNAME)
        if not department:
            return None
        result = Department(*department)
        return result.dep_id

    @staticmethod
    def create(dep_id, name):
        db = get_db()
        db.execute(
            f"INSERT INTO `{Department.DBNAME}` (dep_id, name) VALUES (%s, %s)",
            (dep_id, name),
        )
        commit()


class LockRegion(RDMS):
    DBNAME = 'locker_region'

    def __init__(self, id_, dep_id, name):
        self.reg_id = int(id_)
        self.dep_id = int(dep_id)
        self.name = name

    def __repr__(self):
        return f"LockRegion_{self.reg_id}({self.dep_id}:{self.region})"

    @staticmethod
    def get(reg_id):
        lock_region = LockRegion.get_raw('reg_id', reg_id, LockRegion.DBNAME)

        if not lock_region:
            return None

        return LockRegion(*lock_region)

    @staticmethod
    def get_by_departure(dep_id):
        regions = LockRegion.get_all_raw('dep_id', dep_id, LockRegion.DBNAME)
        if not regions:
            return None
        return [LockRegion(*region) for region in regions]

    @staticmethod
    def create(id_, dep_id, name):
        db = get_db()
        db.execute(
            f"INSERT INTO `{LockRegion.DBNAME}` (reg_id, dep_id, name) VALUES (%s, %s, %s)",
            (id_, dep_id, name),
        )
        commit()
