import telebot
import time
from .id_class import Id
import time

trashgroup = 0
tokens = []
groups = []
bots = []
matrix = []
pointer = 0
cache_limit = 5

def config(conf):
    global trashgroup
    global tokens
    global groups
    global cache_limit
    if("trashgroup" in conf):
        trashgroup = conf["trashgroup"]
    if("groups" in conf):
        groups = conf["groups"]
    if("tokens" in conf):
        tokens = conf["tokens"]
        rebots()
    if("cache_size" in conf):
        cache_limit = conf["cache_size"]

def rebots():
    global bots
    global pointer
    global matrix
    pointer = 0
    for tok in tokens:
        bot = telebot.TeleBot(tok)
        botlist = []
        for group in groups:
            vbot = Bot(bot, group, tok)
            botlist.append(vbot)
        matrix.append(botlist)
    
    bots = [matrix[i][j] for i in range(len(matrix)) for j in range(len(matrix[0]))]

cache = {}
def gc():
    while(len(cache) > cache_limit):
        cache.pop(next(cache.__iter__()))

class Bot:
    def __init__(self, bot, group, token):
        self.bot, self.group = bot, group
        self.bot_index, self.group_index = tokens.index(token), groups.index(group)
        self.time = time.time() - 5
    
    def send_message(self, text):
        while(time.time() - self.time < 2):
            time.sleep(time.time() - self.time)
        self.time = time.time()
        id = self.bot.send_message(self.group, text, timeout=1000, parse_mode=None).id
        cache[Id(self.bot_index, self.group_index, id)] = text
        gc()
        return id
    
    def send_document(self, contain):
        while(time.time() - self.time < 2):
            time.sleep(time.time() - self.time)
        self.time = time.time()
        return self.bot.send_document(self.group, contain, timeout=1000).id

    def send_message_id(self, text):
        id = self.send_message(text)
        return Id(self.bot_index, self.group_index, id)
    
    def send_document_id(self, contain):
        while(time.time() - self.time < 3):
            time.sleep(0.2)
        self.time = time.time()
        return Id(self.bot_index, self.group_index, self.bot.send_document(self.group, contain, timeout=1000).id)

    def edit_message(self, idd, text):
        cache[idd] = text
        gc()
        try:
            return self.bot.edit_message_text(text, chat_id=self.group, message_id=idd.id, parse_mode=None, timeout=1000)
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise e

    def forward(self, idd):
        return self.bot.forward_message(trashgroup, groups[idd.group], idd.id)

    def get_text(self, idd):
        if(idd in cache):
            return cache[idd]
        cache[idd] = (text := self.forward(idd).text)
        gc()
        return text
    
    __str__ = lambda self: f"{self.bot}, {self.group}"

def getbot() -> Bot:
    global pointer
    pointer = (pointer + 1) % len(bots)
    return bots[pointer]

def getbot_id(id) -> Bot:
    id = Id(id)
    return matrix[id.bot][id.group]
