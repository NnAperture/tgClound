from .bytes_string import *
import threading

class Id:
    def __init__(self, bot=None, group=None, id=None, *, func=None):
        self.set(bot, group, id, func=func)
        self.event = threading.Event()
        self.event.set()
    
    def lock(self):
        self.event.clear()
        return self
    
    def unlock(self):
        self.event.set()
        return self
    
    def wait_for_unlock(self):
        self.event.wait()
        return self
    
    def set(self, bot=None, group=None, id=None, *, func=None):
        if(func != None):
            if(hasattr(self, 'func')):
                def f(self=self):
                    self.func.join()
                    func(self)
                self.func = threading.Thread(target=f)
                self.func.start()
            else:
                self._bot, self._group, self._id = [None] * 3
                self.func = threading.Thread(target=func, args=(self, ))
                self.func.start()
            return self
        if(type(bot) == Id):
            self._bot = bot.bot
            self._group = bot.group
            self._id = bot.id
            if(hasattr(bot, 'func')):
                if(hasattr(self, 'func')):
                    def f(self=self, bot=bot):
                        self.func.join()
                        self.set(*bot)
                    self.func = threading.Thread(target=f)
                    self.func.start()
                else:
                    self.func = threading.Thread(target=lambda self, bot=bot: self.set(*bot), args=(self, ))
                    self.func.start()
            return self
        if(type(bot) == tuple):
            self._bot, self._group, self._id = bot
            return self
        if(type(bot) == str and bot.count("|") == 2):
            self.from_str(bot)
            return
        self._bot = bot
        self._group = group
        self._id = id

        return self
    
    @property
    def bot(self):
        self.wait_for_unlock()
        if(hasattr(self, "func")):
            try:
                self.func.join()
                del self.func
            except AttributeError:
                pass
        return self._bot

    @property
    def group(self):
        self.wait_for_unlock()
        if(hasattr(self, "func")):
            try:
                self.func.join()
                del self.func
            except AttributeError:
                pass
        return self._group
    
    @property
    def id(self):
        self.wait_for_unlock()
        if(hasattr(self, "func")):
            try:
                self.func.join()
                del self.func
            except AttributeError:
                pass
        return self._id
    
    def __repr__(self):
        return f"Id({self.bot}, {self.group}, {self.id})"

    def __str__(self):
        return self.to_str()
    
    def to_str(self):
        return f"{self.bot}|{self.group}|{self.id}"
    
    def from_str(self, string):
        self.set(*tuple(map(int, string.split('|'))))
        return self
    
    def __iter__(self):
        yield self.bot
        yield self.group
        yield self.id
    
    def __eq__(self, other):
        try:
            return tuple(self) == tuple(other)
        except:
            return False
    
    def __hash__(self):
        return hash(str(self))