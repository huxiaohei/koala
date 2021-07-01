import dataclasses
from koala.typing import *


JsonVar = TypeVar("JsonVar", bound='SimpleMessage')
__json_mapper: Dict[str, Any] = dict()


def register_model(cls):
    global __json_mapper
    __json_mapper[cls.__qualname__] = cls


def find_model(name: str) -> Optional[Type['JsonMessage']]:
    if name in __json_mapper:
        return __json_mapper[name]
    return None


class JsonMeta(type):
    def __new__(mcs, class_name, class_parents, class_attr):
        cls = type.__new__(mcs, class_name, class_parents, class_attr)
        register_model(cls)
        return cls


def to_dict(obj):
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    elif hasattr(obj, "_ast"):
        return to_dict(obj._ast())
    elif not isinstance(obj, str) and hasattr(obj, "__iter__"):
        return [to_dict(v) for v in obj]
    elif hasattr(obj, "__dict__"):
        return {
            k: to_dict(v)
            for k, v in obj.__dict__.items()
            if not callable(v) and not k.startswith('_')
        }
    else:
        return obj


@dataclasses.dataclass
class JsonMessage(metaclass=JsonMeta):
    @classmethod
    def from_dict(cls, kwargs: dict):
        return cls(**kwargs)

    def to_dict(self) -> dict:
        return to_dict(self)
