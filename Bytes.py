from .id_class import Id
from .config import getbot, getbot_id, Bot
from .bytes_string import *
import threading
import json
from queue import Queue

FILE_SIZE = 1000# 19500
MANIFEST_PAGE_LIMIT = 3950  # approx character limit per manifest page

class Chunk:
    def __init__(self):
        self.lock = threading.RLock()
        self.event = threading.Event()
        self.id:Id = Id().lock()
    
    def set(self, value=None, func=None, id=None, *, save=True):
        if(id == None):
            self.id = Id().lock()
            threading.Thread(target=self.upload, args=(value, func, save)).start()
        else:
            self.id = id
            if(save):
                self.cache()
        return self

    def clear(self):
        self.value = None
        return self
    
    def get(self):
        with self.lock:
            if(not self.event.is_set()):
                self.download()
            return self.value

    def cache(self):
        threading.Thread(target=self.download).start()

    def download(self):
        with self.lock:
            self.id.unlock()
            self.event.clear()

            file_id = getbot_id(self.id).forward(self.id).document.file_id
            file_info = getbot_id(self.id).bot.get_file(file_id)
            self.value = getbot_id(self.id).bot.download_file(file_info.file_path)

            self.event.set()
        return self

    def upload(self, value, func, save):
        with self.lock:
            self.id.lock()
            if(func != None):
                value = func()
            if(save):
                self.value = value
            self.id.set(Id(getbot().send_document_id(value)))
            self.id.unlock()
    
    def wait_for_unlock(self):
        self.event.wait()
    
    def __repr__(self):
        return f"Chunk({self.id})"

class LinkedBytes:
    def __init__(self, value=None, url=None, id=None, *, init_symbol="b", cache_limit=-1):
        self.headers_lock = threading.Event() 
        self.lock = threading.RLock()
        self.init_symbol = init_symbol
        self.cache_limit = cache_limit
        self._id:Id = Id().lock()
        self.chuncs = []
        self.manipages = []
        if(cache_limit != -1):
            self.cache_queue = Queue()

        if(id == None):
            self.set(value, url)
        else:
            self._id.set(id)
            self._id.unlock()
            def f(self:LinkedBytes, value, url):
                with self.lock:
                    self.header_download()
                    if(value != None or url != None):
                        self.set(value, url)
            threading.Thread(target=f, args=(self, value, url)).start()

    def set(self, value=None, url=None, *, additional=False):
        self._id.lock()
        with self.lock:
            if(additional):
                pass
            else:
                if(url != None):
                    self.chuncs = [Chunk().set(url, save=False)]
                    if(self.cache_limit != -1):
                        self.cache_queue.put(self.chuncs[-1])
                else:
                    self.chuncs = []
                    if(self.cache_limit != -1):
                        ci = 0
                        cn = 0
                    for i in range(0, len(value), FILE_SIZE):
                        if(cn != self.cache_limit):
                            val = value[i:i + FILE_SIZE]
                            self.chuncs.append(Chunk().set(val))
                            cn += 1
                        else:
                            def fun(chunc:Chunk=self.chuncs[ci], data=value[i:i + FILE_SIZE]):
                                chunc.id.wait_for_unlock()
                                chunc.clear()
                                return data
                            self.chuncs.append(Chunk().set(func=fun))
                            ci += 1
                        if(self.cache_limit != -1):
                            self.cache_queue.put(self.chuncs[-1])
        threading.Thread(target=self.header_upload).start()

    def header_upload(self):
        header = 1
        def get_header(self=self):
            nonlocal header
            if(header != len(self.manipages)):
                header += 1
                return self.manipages[header - 1]
            else:
                header += 1
                self.manipages.append(Id(func=lambda self:self.set(getbot().send_message_id("tmp"))))
                return self.manipages[-1]

        with self.lock:
            self._id.lock()

            if(self.manipages == []):
                main_id = Id(func=lambda self:self.set(getbot().send_message_id("tmp")))
                self.manipages.append(main_id)
            else:
                main_id = self.manipages[0]

            init = self.init_symbol
            text = ""
            last = None
            e = True
            for c in self.chuncs:
                lenlast = (len(last) if last != None else 0)
                if(lenlast + len(text) + len(str(c.id)) < MANIFEST_PAGE_LIMIT):
                    text += " " + str(c.id)
                else:
                    text = str(last if last != None else "") + text
                    last = get_header()
                    getbot_id(last).edit_message(last, "c" + (("e") if e else "") + text)
                    e = False
                    last = str(last)
                    text = " " + str(c.id)

            last = (last if last != None else "")
            self._id.set(main_id)
            getbot_id(main_id).edit_message(main_id, init + "l" + ("e" if e else "") + str(last) + text)
            self._id.unlock()
            self.headers_lock.set()

    def header_download(self):
        with self.lock:
            self.headers_lock.clear()
            self.manipages = [self._id]
            text:str = getbot_id(self._id).forward(self._id).text
            if(not text.startswith("bl")):
                raise Exception(f"Message {self.id} is not a LinkedBytes!")
            text = text[2:]
            total = []
            while text[0] != "e":
                ids = list(map(Id, text.split()))
                next = ids[0]
                self.manipages.append(next)
                text = getbot_id(next).forward(next).text[1:]
                total = ids[1:] + total

            total = ids = list(map(Id, text[1:].split())) + total
            self.chuncs = [Chunk().set(id=id, save=(self.cache_limit == -1)) for id in ids]
            self.headers_lock.set()

    def get_chunk(self, chunk):
        with self.lock:
            return self.chuncs[chunk].get()

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        with self.lock:
            self._id = Id(value)
            threading.Thread(target=self.header_download).start()

    def __bytes__(self):
        self.headers_lock.wait()
        out = bytes()
        for c in self.chuncs:
            out += c.get()
        return out

    def __str__(self):
        return str(bytes(self))

    def __repr__(self):
        return f"TgC{str(self)}"

    def gc(self):
        if(self.cache_limit > -1):
            while(self.cache_queue._qsize() > self.cache_limit):
                self.cache_queue.get().clear()


class SimpleBytes:
    def __init__(self, value=None, url=None, id=None, init_symbol="c"):
        self._id = id
        self.value = value
        self._init_symbol = init_symbol
        if(value != None):
            self.upload(url=url)
        else:
            threading.Thread(target=self.download).start()
    
    def download(self):
        if(self.value != None):
            return self.value
        st = getbot_id(self.id).forward(self.id).text
        if(st[:2] != self._init_symbol + "s"):
            raise Exception(f"Message {self.id} is not a SimpleBytes!")
        self.value = to_bytes(st[2:])
        return self.value

    def upload(self, value=None, url=None):
        if(self.value != None):
            value = self.value
        if(url != None):
            import requests
            self.value = requests.get(url).content
        self.value = value
        if(self._id == None):
            self._id = Id(func=lambda self: self.set(getbot().send_message_id(self._init_symbol + "s" + to_str(value))))
        threading.Thread(target=lambda self=self:getbot_id(self._id).edit_message(self._init_symbol + self._id, "s" + to_str(value))).start()
        return self._id
    
    def get(self):
        if(self.value != None):
            return self.download()

    def set(self, value):
        self.upload(value)

    @property
    def id(self):
        if(self._id == None):
            self.upload(self.value)
        return self._id

    @id.setter
    def id(self, id):
        self._id = id
        self.value = None
    
    def __bytes__(self):
        return self.get()