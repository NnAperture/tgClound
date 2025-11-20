from .id_class import Id
from .config import getbot, getbot_id, Bot
from .bytes_string import *
import threading
from .Bytes import Bytes
import pickle

class UndefinedVar:
    def __init__(self, value=None, id=None):
        self._obj = Bytes(pickle.dumps(value), id=id, init_symbol="u")
    
    def get(self):
        return pickle.loads(bytes(self._obj))

    def set(self, value):
        self._obj.set(pickle.dumps(value))
