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

def config(conf):
    global trashgroup
    global tokens
    global groups
    if("trashgroup" in conf):
        trashgroup = conf["trashgroup"]
    if("groups" in conf):
        groups = conf["groups"]
    if("tokens" in conf):
        tokens = conf["tokens"]
        rebots()

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
            bots.append(vbot)
            botlist.append(vbot)
        matrix.append(botlist)

class Bot:
    def __init__(self, bot, group, token):
        self.bot, self.group = bot, group
        self.bot_index, self.group_index = tokens.index(token), groups.index(group)
        self.time = time.time() - 5
    
    def send_message(self, text):
        while(time.time() - self.time < 3):
            time.sleep(0.2)
        self.time = time.time()
        return self.bot.send_message(self.group, text, timeout=1000, parse_mode=None).id
    
    def send_document(self, contain):
        while(time.time() - self.time < 3):
            time.sleep(0.2)
        self.time = time.time()
        return self.bot.send_document(self.group, contain, timeout=1000).id
    
    def edit_message(self, idd, text):
        try:
            return self.bot.edit_message_text(text, chat_id=self.group, message_id=idd.id, parse_mode=None, timeout=1000)
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise e

    def send_message_id(self, text):
        while(time.time() - self.time < 3):
            time.sleep(0.2)
        self.time = time.time()
        return Id(self.bot_index, self.group_index, self.bot.send_message(self.group, text, timeout=1000, parse_mode=None).id)
    
    def send_document_id(self, contain):
        while(time.time() - self.time < 3):
            time.sleep(0.2)
        self.time = time.time()
        return Id(self.bot_index, self.group_index, self.bot.send_document(self.group, contain, timeout=1000).id)

    def forward(self, idd):
        return self.bot.forward_message(trashgroup, groups[idd.group], idd.id)
    
    __str__ = lambda self: f"{self.bot}, {self.group}"

def getbot() -> Bot:
    global pointer
    pointer = (pointer + 1) % len(bots)
    return bots[pointer]

def getbot_id(id) -> Bot:
    id = Id(id)
    return matrix[id.bot][id.group]
