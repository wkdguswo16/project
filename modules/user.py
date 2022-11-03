from abc import *
from flask_login import UserMixin
from modules.token import gen_uuid
from modules.db import get_db, commit
import json
# from modules.token import genToken


class RDMS(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self):
        pass

    @staticmethod
    def get_one_raw(param_name, identifier, destination) -> list:
        db = get_db()
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
        # values = db.fetchone()
        values = db.fetchall()
        return values

    @abstractmethod
    def get(identifier):
        pass

    @staticmethod
    def delete(param_name, identifier, destination):
        db = get_db()
        db.execute(
            f"DELETE FROM `{destination}` WHERE `{param_name}` = %s",
            (identifier),
        )
        db.commit()


class User(UserMixin, RDMS):
    DBNAME = 'student_info'

    def __init__(self, id_, dep_id, name, email, profile_pic, noti_token=None):
        self.id = id_
        self.dep_id = int(dep_id)
        self.name = name
        self.email = email
        self.profile_pic = profile_pic
        self.noti_token = noti_token

    def __repr__(self):
        return f"User_{self.id}({self.name}:{self.dep_id}, email={self.email}, pic={self.profile_pic}, noti_token={self.noti_token})"

    def set_noti_token(self, token):
        db = get_db()
        db.execute(
            f"UPDATE `{User.DBNAME}` SET `noti_token` = %s WHERE `stu_id` = %s", (token, self.id))
        commit()
        self.noti_token = token

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

    def get_lock_usage(self):
        return LockUsage.get_by_stu_id(self.id)

    def get_lock_logs(self):
        usage = self.get_lock_usage()
        if usage:
            return usage.get_logs()
        return None


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
        lock_region = LockRegion.get_one_raw('id', reg_id, LockRegion.DBNAME)

        if not lock_region:
            return None

        return LockRegion(*lock_region)

    @staticmethod
    def get_by_departure(dep_id):
        regions = LockRegion.get_all_raw('dep_id', dep_id, LockRegion.DBNAME)
        if not regions:
            return []
        return [LockRegion(*region) for region in regions]


    @staticmethod
    def create(id_, dep_id, name):
        db = get_db()
        db.execute(
            f"INSERT INTO `{LockRegion.DBNAME}` (reg_id, dep_id, name) VALUES (%s, %s, %s)",
            (id_, dep_id, name),
        )
        commit()
 
    def get_lockers(self):
        db = get_db()
        lockers = LockInfo.get_all_raw('reg_id', self.reg_id, LockInfo.DBNAME)
        if not lockers:
            return []
        return [LockInfo(*locker) for locker in lockers]

class LockInfo(RDMS):
    DBNAME = 'locker_info'
    NOT_USING = 0
    USING = 1
    def __init__(self, own_id, reg_id, pos, use):
        self.own_id = int(own_id)
        self.reg_id = int(reg_id)
        self.pos = str(pos)
        self.use = int(use)

    def __repr__(self):
        return f"LockInfo_{self.own_id}({self.reg_id} pos={self.pos}, use={self.use})"

    def send_open_signal(self, redis_server):
        res = json.dumps({"target": self.own_id, "action": "open"})
        redis_server.publish(self.reg_id, res)

    @staticmethod
    def get(own_id):
        locker_info = LockInfo.get_one_raw(
            'own_id', own_id, LockInfo.DBNAME
        )
        if not locker_info:
            return None
        return LockInfo(*locker_info)
    @staticmethod
    def get_pos_by_token(token):
        pos = LockInfo.get_one_raw(
            'token', token, LockInfo.DBNAME
        )
        if not pos:
            return None
        result = LockInfo(*pos)
        return result.pos

    @staticmethod
    def get_use_by_token(token):
        own_id = LockUsage.get_own_id_by_token(token)
        use = LockInfo.get_one_raw(
            'own_id', own_id, LockInfo.DBNAME
        )
        if not use:
            return None
        result = LockInfo(*use)
        return result.use

    @staticmethod
    def get_own_id_by_reg_id(reg_id):
        own_id = LockInfo.get_one_raw(
            'reg_id', reg_id, LockInfo.DBNAME
        )
        if not own_id:
            return None
        result = LockInfo(*own_id)
        return result.own_id

    @staticmethod
    def create(own_id, reg_id, pos, use):
        db = get_db()
        db.execute(
            f"INSERT INTO `{LockInfo.DBNAME}` (own_id, reg_id, pos, use) VALUES(%s, %s, %s, %s)",
            (own_id, reg_id, pos, use),
        )
        commit()

    @staticmethod
    def delete_by_token(token):
        LockInfo.delete('token', token, LockInfo.DBNAME)

    # @staticmethod
    # def update_use_by_own_id(own_id, use):
    #     db = get_db()
    #     db.execute(
    #         f"UPDATE `{LockInfo.DBNAME}` SET `use` = %s WHERE `own_id` = %s",
    #         (use, own_id),
    #     )
        commit()
    def update_use(self, use):
        db = get_db()
        db.execute(
            f"UPDATE `{LockInfo.DBNAME}` SET `use` = %s WHERE `own_id` = %s",
            (use, self.own_id),
        )
        commit()
        
    def get_region(self):
        return LockRegion.get(self.reg_id)

    def get_pos_str(self):
        region = self.get_region()
        return f"{region.name} {self.pos}번"


class LockUsage(RDMS):
    DBNAME = 'locker_usage'
    UNUSE = 0
    USE = 1

    def __init__(self, token, own_id, id_, state, exp_date, uuid):
        self.token = int(token)
        self.own_id = int(own_id)
        self.stu_id = id_
        self.state = int(state)
        self.exp_date = exp_date
        self.uuid = uuid

    def __repr__(self):
        return f"LockUsage_{self.token}(own_id={self.own_id}, stu_id={self.stu_id}, state={self.state}, self.exp_date={self.exp_date})"

    @staticmethod
    def get(token):
        usage = LockUsage.get_one_raw(
            'token', token, LockUsage.DBNAME
        )
        if not usage:
            return None
        return LockUsage(*usage)

    @staticmethod
    def get_by_stu_id(stu_id):
        db = get_db()
        db.execute(
            f"SELECT * FROM `{LockUsage.DBNAME}` WHERE stu_id = %s AND state = %s LIMIT 1", (
                stu_id, 1)
        )
        token = db.fetchone()
        if not token:
            return None
        result = LockUsage(*token)
        return result
    
    @staticmethod
    def get_by_own_id(own_id):
        db = get_db()
        db.execute(
            f"SELECT * FROM `{LockUsage.DBNAME}` WHERE own_id = %s LIMIT 1", (
                own_id,)
        )
        token = db.fetchone()
        if not token:
            return None
        result = LockUsage(*token)
        return result

    @staticmethod
    def get_stu_id_by_token(token):
        stu_id = LockUsage.get_one_raw(
            'token', token, LockUsage.DBNAME
        )
        if not stu_id:
            return None
        result = LockUsage(*stu_id)
        return result.stu_id

    @staticmethod
    def get_own_id_by_token(token):
        own_id = LockUsage.get_one_raw(
            'token', token, LockUsage.DBNAME
        )
        if not own_id:
            return None
        result = LockUsage(*own_id)
        return result.own_id

    @staticmethod
    def create(token, locker:LockInfo, user:User):
        uuid = gen_uuid()
        db = get_db()
        db.execute(
            f"INSERT INTO `{LockUsage.DBNAME}` (token, own_id, stu_id, state, exp_date, uuid) VALUES (%s, %s, %s, 1, DATE_ADD(NOW(), INTERVAL 3 MONTH), %s)",
            (token, locker.own_id, user.id, uuid),
        )
        commit()
        locker.update_use(LockUsage.USE)
        # LockInfo.update_use_by_own_id(locker.own_id, LockUsage.USE)

    def disable(self):
        locker = LockInfo.get(self.own_id)
        locker.update_use(LockUsage.UNUSE)
        db = get_db()
        db.execute(f"UPDATE {LockUsage.DBNAME} SET state = %s WHERE token = %s", (0, self.token))
        commit()

    @staticmethod
    def update_by_token(token):
        state = LockUsage.get_one_raw(
            'token', token, LockUsage.DBNAME
        )
        if not state:
            return None
        if (state[3] == 1):
            state = 0
        else:
            state = 1
        db = get_db()
        db.execute(
            f"UPDATE `{LockUsage.DBNAME}` SET `state` = %s WHERE `token` = %s",
            (state, token),
        )
        commit()

    def get_logs(self) -> list:
        v = LockLog.get_by_token(self.token)
        if (not v):
            return []
        return v[::-1]

    def get_locker_info(self):
        return LockInfo.get(self.own_id)


class LockLog(RDMS):
    DBNAME = 'locker_log'
    OPENED = 1
    CLOSED = 2
    INVALID_OPEN = 3

    def __init__(self, id_, token, create_time, is_open):
        self.id = int(id_)
        self.token = int(token)
        self.create_time = create_time
        self.is_open = int(is_open)

    def __repr__(self):
        return f"LockLog_{self.id}(token={self.token}, create_time={self.create_time}, is_open={self.is_open})"

    @staticmethod
    def get(id_):
        log = LockLog.get_one_raw(
            'id', id_, LockLog.DBNAME
        )
        if not log:
            return None
        return LockLog(*log)

    @staticmethod
    def get_by_token(token):
        locker_logs = LockLog.get_all_raw('token', token, LockLog.DBNAME)

        if not locker_logs:
            return None

        return [LockLog(*log) for log in locker_logs]

    @staticmethod
    def create_by_token(token, val):
        if val == "opened":
            state = True
        else:
            state = False
        db = get_db()
        db.execute(
            f"INSERT INTO `{LockLog.DBNAME}` (token, create_time, is_open) VALUES (%s, NOW(), %s)",
            (token, state),
        )
        commit()

    @staticmethod
    def delete_by_token(token):
        LockLog.delete('token', token, LockLog.DBNAME)


# class activateFunc(User, Department, LockRegion, LockInfo, LockLog, LockUsage):

#     @staticmethod
#     def checkToken():
#         try:
#             flag = True
#             while (flag):
#                 checkData = LockUsage.get_one_raw(
#                     'token', token, LockUsage.DBNAME)
#                 if (checkData == None):
#                     flag = False
#         except:
#             return None
#         else:
#             return token

#     @staticmethod
#     def activateDoor(token):
#         LockUsage.update_by_token(token)
#         LockLog.create_by_token(token)

#     @staticmethod
#     def applyLocker(stu_id):
#         db = get_db()
#         dep_id = User.get(stu_id).dep_id
#         reg_id = LockRegion.get_by_departure(dep_id)[0].reg_id
#         own_id = LockInfo.get_own_id_by_reg_id(reg_id)
#         token = activateFunc.checkToken()
#         if (token == None or own_id == None):
#             return None
#         LockInfo.update_use_by_own_id(own_id)
#         LockUsage.create(token, own_id, stu_id)
#         commit()

#     @staticmethod
#     def cancelLocker(stu_id):
#         db = get_db()
#         token = LockUsage.get_token_by_stu_id(stu_id)
#         LockLog.delete_by_token(token)
#         own_id = LockUsage.get_own_id_by_token(token)
#         LockInfo.update_use_by_own_id(own_id)
#         LockUsage.delete_by_token(token)
#         commit()
