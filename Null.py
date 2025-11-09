from .id_class import Id
from .config import getbot, getbot_id
from .config import Bot
from .bytes_string import *
import threading
import time
import queue

class Null:
    def __init__(self, id=None):
        self.uploading = queue.Queue()
        if(id != None):
            self.id = Id(id)
            def f(selfi, self=self):
                selfi.set(self)
                getbot_id(id).edit_message(id, 'null')
            self.id.set(func=f)
        else:
            self.id = Id(func=lambda selfi: selfi.set(getbot().send_message_id('null')))
        self.upload()

    def get(self):
        return

    def __repr__(self):
        return "nNone"
    