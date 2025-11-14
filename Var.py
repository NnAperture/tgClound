from .List import List
from .Int import Int
from .String import Str
from .Null import Null
from .Bytes import Bytes
from .id_class import Id
from .config import getbot_id
import time

_UNSET = object()  # внутренний маркер для "аргумент не передан"


class Var:
    """Универсальный контейнер для Str, Int, List, Null и т.п."""

    def __init__(self, value=_UNSET, id=None):
        self._obj = None

        # --- Если передан id ---
        if id is not None:
            id = Id(id)

            if value is _UNSET:
                # Загружаем существующий объект
                text = getbot_id(id).forward(id).text or ""
                text = text.strip()

                if text.startswith("i"):
                    self._obj = Int(id=id)
                elif text.startswith("ss") or text.startswith("sl"):
                    self._obj = Str(id=id)
                elif text.startswith("L"):
                    self._obj = List(id=id)
                elif text.startswith("b"):
                    self._obj = Bytes(id=id)
                elif text.startswith("n") or text == "":
                    self._obj = Null(id=id)
                else:
                    # fallback — неизвестный тип → строка
                    self._obj = Str(id=id)
                return

            else:
                wrapped = self._wrap_value(value)
                wrapped._id = id
                wrapped.upload()
                self._obj = wrapped
                return

        # --- Если id нет ---
        if value is _UNSET:
            # Ничего не передано → создаём Null
            self._obj = Null()
        else:
            # Обычное значение
            self._obj = self._wrap_value(value)

    # --- Internal helper ---
    def _wrap_value(self, value):
        """Преобразует Python-объект в Str, Int, List, Null или Bytes."""
        if isinstance(value, (Str, Int, List, Null, Bytes)):
            return value
        elif isinstance(value, bytes):
            return Bytes(value)
        elif isinstance(value, str):
            return Str(value)
        elif isinstance(value, int):
            return Int(value)
        elif isinstance(value, (list, tuple)):
            return List(value)
        elif value is None:
            return Null()
        else:
            return Str(str(value))

    # --- Public API ---
    def set(self, value):
        new_obj = self._wrap_value(value)
        new_obj._id = getattr(self._obj, "_id", None)
        new_obj.upload()
        self._obj = new_obj

    def get(self):
        """Возвращает чистое значение (str/int/list/etc)."""
        if hasattr(self._obj, "get"):
            return self._obj.get()
        return self._obj

    # --- Proxy methods ---
    def __getattr__(self, name):
        return getattr(self._obj, name)

    def __setattr__(self, name, value):
        if name == "_obj":
            super().__setattr__(name, value)
        else:
            setattr(self._obj, name, value)

    # --- Item access ---
    def __getitem__(self, key):
        if hasattr(self._obj, "__getitem__"):
            return self._obj[key]
        raise TypeError(f"{type(self._obj).__name__} does not support indexing")

    def __setitem__(self, key, value):
        if hasattr(self._obj, "__setitem__"):
            self._obj[key] = value
            return
        raise TypeError(f"{type(self._obj).__name__} does not support item assignment")

    # --- Arithmetic / concat ---
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

    # --- Type conversions ---
    def __int__(self):
        if hasattr(self._obj, "__int__"):
            return int(self._obj)
        raise TypeError("Cannot convert Var to int")

    def __len__(self):
        if hasattr(self._obj, "__len__"):
            return len(self._obj)
        raise TypeError("Object has no length")

    # --- Representation ---
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

    # --- ID property ---
    @property
    def id(self):
        """Возвращает Id объекта (ждёт, если не готов)."""
        _id = getattr(self._obj, "id", None)
        while _id is None:
            time.sleep(0.05)
            _id = getattr(self._obj, "id", None)
        return _id

    @id.setter
    def id(self, value):
        """Присваивает Id и перезаписывает объект."""
        self._obj._id = Id(value)
        if hasattr(self._obj, "upload"):
            self._obj.upload()
