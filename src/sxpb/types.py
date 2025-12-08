from collections import UserDict, UserList


def _to_plain_type(v):
    if hasattr(v, "to_dict"):
        return v.to_dict()
    if hasattr(v, "to_list"):
        return v.to_list()
    return v


class SxpbDict(UserDict):
    def to_dict(self):
        return {k: _to_plain_type(v) for k, v in self.items()}


class SxpbList(UserList):
    def to_list(self):
        return [_to_plain_type(v) for v in self]


class SxpbLone(UserDict):
    def to_dict(self):
        return {k: _to_plain_type(v) for k, v in self.items()}


class SxpbMany(UserList):
    def to_list(self):
        return [_to_plain_type(v) for v in self]


class SxpbNest(SxpbDict):
    pass
