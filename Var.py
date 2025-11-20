from .List import List
from .Int import Int
from .String import Str
from .Null import Null
from .Bytes import Bytes
from .id_class import Id
from .Undefined import UndefinedVar
from .config import getbot_id
import threading

_UNSET = object()  # внутренний маркер для "аргумент не передан"


class Var:
    def __init__(self, value=_UNSET, id=None):
        self.lock = threading.RLock()
        self._obj = None
        evt = threading.Event()
        def th(self=self, value=value, id=id):
            with self.lock:
                evt.set()
                if id is not None:
                    id = Id(id)

                    if value is _UNSET:
                        text = getbot_id(id).forward(id).text or ""
                        text = text.strip()

                        if text.startswith("i"):
                            self._obj = Int(id=id)
                        elif text.startswith("s"):
                            self._obj = Str(id=id)
                        elif text.startswith("L"):
                            self._obj = List(id=id)
                        elif text.startswith("b"):
                            self._obj = Bytes(id=id)
                        elif text.startswith("n"):
                            self._obj = Null(id=id)
                        else:
                            self._obj = UndefinedVar(id=id)
                        return

                    else:
                        wrapped = self._wrap_value(value, id)
                        wrapped._id = id
                        self._obj = wrapped
                        return

                if value is _UNSET:
                    self._obj = Null()
                else:
                    self._obj = self._wrap_value(value)
        threading.Thread(target=th).start()
        evt.wait()

    def _wrap_value(self, value, id):
        if isinstance(value, (Str, Int, List, Null, Bytes)):
            return value
        elif isinstance(value, bytes):
            return Bytes(value, id)
        elif isinstance(value, str):
            return Str(value, id)
        elif isinstance(value, int):
            return Int(value, id)
        elif isinstance(value, (list, tuple)):
            return List(value, id)
        elif value is None:
            return Null()
        else:
            return UndefinedVar(value, id)

    def set(self, value):
        new_obj = self._wrap_value(value)
        new_obj._id = getattr(self._obj, "_id", None)
        new_obj.upload()
        self._obj = new_obj

    def get(self):
        if hasattr(self._obj, "get"):
            return self._obj.get()
        return self._obj

    def __getattr__(self, name):
        return getattr(self._obj, name)

    def __setattr__(self, name, value):
        if name == "_obj":
            super().__setattr__(name, value)
        else:
            setattr(self._obj, name, value)

    def __getitem__(self, key):
        if hasattr(self._obj, "__getitem__"):
            return self._obj[key]
        raise TypeError(f"{type(self._obj).__name__} does not support indexing")

    def __setitem__(self, key, value):
        if hasattr(self._obj, "__setitem__"):
            self._obj[key] = value
            return
        raise TypeError(f"{type(self._obj).__name__} does not support item assignment")

    def __add__(self, other):
        if hasattr(self._obj, "__add__"):
            return Var(self._obj + (other._obj if isinstance(other, Var) else other))
        raise TypeError(f"{type(self._obj).__name__} does not support addition")

    def __iadd__(self, other):
        if hasattr(self._obj, "__iadd__"):
            self._obj += (other._obj if isinstance(other, Var) else other)
            return self
        raise TypeError(f"{type(self._obj).__name__} does not support addition")

    def __sub__(self, other):
        if hasattr(self._obj, "__sub__"):
            return Var(self._obj - (other._obj if isinstance(other, Var) else other))
        raise TypeError(f"{type(self._obj).__name__} does not support subtraction")

    def __isub__(self, other):
        if hasattr(self._obj, "__isub__"):
            self._obj -= (other._obj if isinstance(other, Var) else other)
            return self
        raise TypeError(f"{type(self._obj).__name__} does not support subtraction")

    def __int__(self):
        if hasattr(self._obj, "__int__"):
            return int(self._obj)
        raise TypeError("Cannot convert Var to int")

    def __len__(self):
        if hasattr(self._obj, "__len__"):
            return len(self._obj)
        raise TypeError("Object has no length")

    def __repr__(self):
        return f"<Var {repr(self._obj)}>"

    def __str__(self):
        return str(self._obj)

    def __int__(self):
        return int(self._obj)
    
    def __bytes__(self):
        return bytes(self._obj)

    def __iter__(self):
        for el in self._obj:
            yield el

    @property
    def id(self):
        return self._obj.id

    @id.setter
    def id(self, value):
        self._obj._id = Id(value)
        self._obj.download()
