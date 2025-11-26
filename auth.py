from flask_login import UserMixin
from database import get_doctor


class User(UserMixin):
    def __init__(self, username, role):
        self.id = username
        self.role = role

    @staticmethod
    def get(username):
        data = get_doctor(username)
        if data:
            username, _, role = data
            return User(username, role)
        return None
