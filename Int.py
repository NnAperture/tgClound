from .id_class import Id
from .config import getbot, getbot_id
from .config import Bot
from .bytes_string import *
import threading
import time
import queue

class Int:
    def __init__(self, value=None, id=None):
        self.uploading = queue.Queue()
        self.downloading = queue.Queue()
        if(value == None):
            self.value = None
            try:
                self._id = Id(id)
                self.download()
            except:
                self._id = None
                self.download()
        else:
            if(type(value) == int):
                self.value = value
            else:
                self.value = int(value)

            if(id != None):
                self._id = Id(id)
            else:
                self._id = None
            self.upload()
    
    def set(self, value):
        self.value = value
        self.upload()
    
    def download(self):
        self.value = None
        if(self.downloading.empty()):
            threading.Thread(target=self.tdownload).start()
        else:
            self.downloading.put(1)

    def tdownload(self):
        if(self._id == None):
            return
        text = getbot_id(self._id).forward(self._id).text
        if(text[0] == 'i'):
            self.value = bytes_int(to_bytes(text[1:]))
        else:
            raise Exception(f"Error: {self._id} is not a number!")
        if(not self.downloading.empty()):
            while not self.downloading.empty():
                self.downloading.get()
            threading.Thread(target=self.tdownload).start()

    def upload(self):
        if(self.uploading.empty()):
            t = threading.Thread(target=self.tupload, args=(self._id, ))
            self._id = None
            t.start()
        else:
            self.uploading.put(1)

    def tupload(self, id):
        if(isinstance(id, Id)):
            getbot_id(id).edit_message(id, 'i' + to_str(int_bytes(self.value)))
        else:
            bot = getbot()
            id = Id(bot.bot_index, bot.group_index, bot.send_message('i' + to_str(int_bytes(self.value))))
        if(not self.uploading.empty()):
            while not self.uploading.empty():
                self.uploading.get()
            threading.Thread(target=self.tupload, args=(self._id, )).start()
        else:
            self._id = id
    
    @property
    def id(self):
        while(self._id == None):
            time.sleep(0.2)
        return self._id
    
    @id.setter
    def id(self, value):
        self._id = Id(value)
        self.download()
    
    def __iadd__(self, other):
        if(type(other) == int):
            self.value += other
            self.upload()
            return self
        elif(type(other) == Int):
            self.value += other.value
            self.upload()
            return self
        else:
            raise Exception("Not an int!")
    
    def __add__(self, other):
        if(type(other) == int):
            return Int(self.value + other)
        elif(type(other) == Int):
            return Int(self.value + other.value)
        else:
            raise Exception("Not an int!")
        
    def __isub__(self, other):
        if(type(other) == int):
            self.value -= other
            self.upload()
            return self
        elif(type(other) == Int):
            self.value -= other.value
            self.upload()
            return self
        else:
            raise Exception("Not an int!")
    
    def __sub__(self, other):
        if(type(other) == int):
            return Int(self.value - other)
        elif(type(other) == Int):
            return Int(self.value - other.value)
        else:
            raise Exception("Not an int!")
        
    def __imul__(self, other):
        if(type(other) == int):
            self.value *= other
            self.upload()
            return self
        elif(type(other) == Int):
            self.value *= other.value
            self.upload()
            return self
        else:
            raise Exception("Not an int!")
    
    def __mul__(self, other):
        if(type(other) == int):
            return Int(self.value * other)
        elif(type(other) == Int):
            return Int(self.value * other.value)
        else:
            raise Exception("Not an int!")
        
    def __ifloordiv__(self, other):
        if(type(other) == int):
            self.value //= other
            self.upload()
            return self
        elif(type(other) == Int):
            self.value //= other.value
            self.upload()
            return self
        else:
            raise Exception("Not an int!")
    
    def __floordiv__(self, other):
        if(type(other) == int):
            return Int(self.value // other)
        elif(type(other) == Int):
            return Int(self.value // other.value)
        else:
            raise Exception("Not an int!")
    
    def __imod__(self, other):
        if(type(other) == int):
            self.value %= other
            self.upload()
            return self
        elif(type(other) == Int):
            self.value %= other.value
            self.upload()
            return self
        else:
            raise Exception("Not an int!")
    
    def __mod__(self, other):
        if(type(other) == int):
            return Int(self.value % other)
        elif(type(other) == Int):
            return Int(self.value % other.value)
        else:
            raise Exception("Not an int!")

    def __str__(self):
        while(self.value == None):
            time.sleep(0.05)
        return str(self.value)

    def __repr__(self):
        while(self.value == None):
            time.sleep(0.05)
        return 'i' + str(self.value)
    
    def __int__(self):
        while(self.value == None):
            time.sleep(0.05)
        return int(self.value)


def int_bytes_g(a):
    while a > 0:
        yield a % 256
        a //= 256

def int_bytes(a:int) -> bytes:
    return bytes(int_bytes_g(a))

def bytes_int(a:bytes) -> int:
    c = 1
    o = 0
    for num in a:
        o += num * c
        c *= 256
    return o