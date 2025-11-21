from .id_class import Id
from .config import getbot, getbot_id
import threading

MANIFEST_PAGE_LIMIT = 4000

class Chain:
    def __init__(self, string=None, id=None, *, separator="$", init=""):
        self.init = init
        self.separator = separator
        self.lock = threading.RLock()
        self.headers = []
        self.value = ""
        self._id = Id().lock()
        if id is None:
            if string is None:
                string = ""
            self.set(string)
        else:
            self._id = id
            threading.Thread(target=self.download).start()

    def _id_generator(self, headers_snapshot):
        for hdr in headers_snapshot:
            def make_editer(h=hdr):
                def edit_fn(value):
                    res = getbot_id(h).edit_message(h, value)
                    return res
                return edit_fn
            yield make_editer()
        while True:
            def sender(value):
                return getbot().send_message_id(value)
            yield sender

    def _normalize_returned_id(self, raw):
        if isinstance(raw, Id):
            return raw
        if isinstance(raw, str):
            return Id().from_str(raw)
        try:
            return Id().from_str(str(raw))
        except Exception:
            return Id().from_str(str(raw))

    def set(self, string):
        def th(self=self, string=string):
            with self.lock:
                self.value = string
                parts = []
                s = string
                while len(s) > MANIFEST_PAGE_LIMIT:
                    parts.append(s[:MANIFEST_PAGE_LIMIT])
                    s = s[MANIFEST_PAGE_LIMIT:]
                parts.append(s)

                headers_snapshot = list(self.headers)
                gen = self._id_generator(headers_snapshot)
                new_headers = []
                last_id = None

                num = 0
                for part in parts:
                    num += 1
                    last_id_str = (str(last_id) if last_id != None else "")
                    content = f"{self.init if num == len(parts) else ""}{last_id_str}{self.separator}{part}"
                    last_raw = next(gen)(content)
                    last_id = self._normalize_returned_id(last_raw)
                    new_headers.append(last_id)

                self._id = last_id
                self.headers = new_headers[::-1]
        threading.Thread(target=th).start()

    def download(self):
        with self.lock:
            full = []
            current = self._id
            self.headers = [current]

            init = True
            while True:
                text = getbot_id(current).get_text(current)
                if(init):
                    text = text[len(self.init):]
                    init = False
                sep = text.find(self.separator)
                if sep <= 0:
                    full.append(text.lstrip(self.separator))
                    break
                prev_raw = text[:sep]
                content = text[sep + 1:]
                full.append(content)
                prev_id = Id().from_str(prev_raw)
                self.headers.append(prev_id)
                current = prev_id

            self.value = "".join(reversed(full))

    def __str__(self):
        with self.lock:
            return self.value

    def get(self):
        return str(self)

    @property
    def id(self):
        with self.lock:
            return self._id