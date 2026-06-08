"""UserService — registration / login layer.

Known-good for trimmed usernames; current bug: registration accepts a
username with surrounding whitespace and stores it verbatim, but login
strips whitespace before lookup → user can never log in again.
"""


class UserAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UserService:
    def __init__(self, repo):
        self._repo = repo

    def register(self, username: str, password: str) -> str:
        # BUG: username is not normalized here.
        if self._repo.find_by_username(username) is not None:
            raise UserAlreadyExistsError(username)
        user_id = self._repo.insert(username=username, password_hash=hash_password(password))
        return user_id

    def login(self, username: str, password: str) -> str:
        normalized = username.strip()  # asymmetric with register()
        user = self._repo.find_by_username(normalized)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        return user.id


def hash_password(p: str) -> str:
    return f"hash::{p}"


def verify_password(p: str, h: str) -> bool:
    return hash_password(p) == h
