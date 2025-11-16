from .id_class import Id
from .config import getbot, getbot_id
import threading

MANIFEST_PAGE_LIMIT = 4000

class Chain:
    def __init__(self, string=None, id=None, *, separator="$"):
        self.separator = separator
        self.lock = threading.RLock()
        self.headers = []
        self.value = ""
        if id is None:
            if string is None:
                string = ""
            self.set(string)
        else:
            self.id = id
            self.download()

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

    def _id_to_str(self, x):
        if isinstance(x, Id):
            try:
                return x.to_str()
            except Exception:
                return str(x)
        if x is None:
            return ""
        return str(x)

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

            for part in parts:
                last_id_str = self._id_to_str(last_id)
                content = f"{last_id_str}{self.separator}{part}"
                last_raw = next(gen)(content)
                last_id = self._normalize_returned_id(last_raw)
                new_headers.append(last_id)

            self.id = last_id
            self.headers = new_headers[::-1]

    def download(self):
        with self.lock:
            full = []
            current = self.id
            self.headers = [current]

            while True:
                text = getbot_id(current).forward(current).text
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
