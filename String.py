from .id_class import Id
from .config import getbot, getbot_id, Bot
from .bytes_string import *
import threading
import time
import queue

# Constants
FILE_SIZE = 16000000
LINKED_STRING_PREFIX = 'sl'
SIMPLE_STRING_PREFIX = 'ss'
CONTINUATION_PREFIX = 'c'
TEXT_PREFIX = 't'
END_MARKER = 'e'
MAX_MESSAGE_LENGTH = 3900
SLEEP_INTERVAL = 0.05


class Str:
    """Wrapper around SimpleString and LinkedString with auto-switching."""

    MAX_SIMPLE = 3950
    MIN_LINKED = 3500

    def __init__(self, value=None, id=None, file=None, path=None):
        self._init_core(value=value, id=id, file=file, path=path)

    def set(self, value=None, id=None, file=None, path=None):
        """
        Replace the stored data with new content.
        You can pass:
          - value: str OR open file-like object
          - id: Telegram message ID
          - file: open file-like object
          - path: path to file
        """
        self._init_core(value=value, id=id, file=file, path=path)

    def _init_core(self, value=None, id=None, file=None, path=None):
        """Shared logic between __init__ and set()."""
        import io, os
        self._obj = None

        # --- 1️⃣ Telegram message ID ---
        if id is not None:
            text = getbot_id(id).get_text(id)
            if text.startswith(SIMPLE_STRING_PREFIX):
                self._obj = SimpleString(id=id)
            elif text.startswith(LINKED_STRING_PREFIX):
                self._obj = LinkedString(id=id)
            else:
                raise ValueError("Unknown string type prefix")
            return

        # --- 2️⃣ Если value — это file-like объект ---
        if hasattr(value, "read") and callable(value.read):
            file = value
            value = None

        # --- 3️⃣ Если передан path ---
        if path is not None:
            size = os.path.getsize(path)
            if size > self.MAX_SIMPLE:
                self._obj = LinkedString(path=path)
            else:
                self._obj = SimpleString(path=path)
            return

        # --- 4️⃣ Если передан открытый файл ---
        if file is not None:
            try:
                pos = file.tell()
                file.seek(0, 2)
                size = file.tell()
                file.seek(pos)
            except Exception:
                size = None

            if size is not None and size > self.MAX_SIMPLE:
                self._obj = LinkedString(file=file)
            else:
                self._obj = SimpleString(file=file)
            return

        # --- 5️⃣ Обычное значение (строка) ---
        value = value or ""
        if len(value) > self.MAX_SIMPLE:
            self._obj = LinkedString(value=value)
        else:
            self._obj = SimpleString(value=value)

    #
    # --- Core behavior ---
    #

    def _check_switch(self):
        """Switch between SimpleString and LinkedString if thresholds crossed."""
        value = str(self._obj)

        if isinstance(self._obj, SimpleString) and len(value) > self.MAX_SIMPLE:
            # Переносим в LinkedString
            old_id = self._obj.id
            self._obj = LinkedString(value=value)
            self._obj._prev_id = old_id

        elif isinstance(self._obj, LinkedString) and len(value) < self.MIN_LINKED:
            # Переносим обратно в SimpleString
            old_id = self._obj.id
            self._obj = SimpleString(value=value)
            self._obj._prev_id = old_id
    
    def save(self, target):
        """
        Save string (Linked or Simple) to file or file-like object.
        """
        self._obj.save(target)

    def get(self):
        """Get the current string value."""
        return str(self._obj)

    def __str__(self):
        return str(self._obj)

    def __repr__(self):
        return repr(self._obj)

    def __len__(self):
        return len(str(self._obj))

    def __getitem__(self, key):
        return str(self._obj)[key]

    def __setitem__(self, key, value):
        val = list(str(self._obj))
        if isinstance(key, slice):
            val[key] = list(value)
        else:
            val[key] = value
        new_value = "".join(val)
        self.set(new_value)

    def __add__(self, other):
        new_val = str(self._obj) + str(other)
        self.set(new_val)
        return self

    def __iadd__(self, other):
        new_val = str(self._obj) + str(other)
        self.set(new_val)
        return self

    def __mul__(self, other):
        if not isinstance(other, int):
            raise TypeError("Can only multiply by int")
        new_val = str(self._obj) * other
        self.set(new_val)
        return self

    def __imul__(self, other):
        return self.__mul__(other)

    @property
    def id(self):
        return self._obj.id

    @id.setter
    def id(self, value):
        text = getbot_id(value).get_text(value)
        if text.startswith(SIMPLE_STRING_PREFIX):
            self._obj = SimpleString(id=value)
        elif text.startswith(LINKED_STRING_PREFIX):
            self._obj = LinkedString(id=value)
        else:
            raise ValueError("Unknown string type prefix")

    def wait(self):
        self._obj.wait()
    
    def __inter__(self):
        self.wait()
        for s in self._obj:
            yield s
    
    def __contains__(self, value):
        for i in range(len(self) - len(value) + 1):
            if(self[i:i + len(value)] == value):
                return True
        return False



class LinkedString:
    """A string stored across multiple Telegram messages with document links.
    
    This class handles large strings by splitting them into chunks and storing
    each chunk as a document in Telegram. The links to these documents are
    stored across multiple messages if needed.
    """
    
    def __init__(self, value=None, id=None, file=None):
        """
        Initialize a LinkedString.

        Args:
            value: Initial string value (optional)
            id: Existing Telegram message ID to load from (optional)
            file: Open file-like object to upload directly (without caching in RAM)
        """
        self.uploading = queue.Queue()
        self.downloading = queue.Queue()
        self.linklock = threading.Lock()
        self.isdownlock = threading.Lock()
        self.isdownloading = False
        self.pages = []
        self._id = None
        self.links = []
        self.value = None

        if file is not None:
            self._upload_from_file(file)
        elif id is not None:
            if value is None:
                self.value = ""
                self.download()
            else:
                self.value = [value[i:i+FILE_SIZE] for i in range(0, len(value), FILE_SIZE)]
                self.upload()
        else:
            self.value = "" if value is None else [value[i:i+FILE_SIZE] for i in range(0, len(value), FILE_SIZE)]
            self.upload()
    
    def save(self, target):
        """
        Save linked string content directly to a file or file-like object
        without caching it into RAM.

        Args:
            target: Path to file (str or Path) OR open binary file object.
        """
        self.wait()
        # Определяем, путь ли это или уже открытый поток
        close_after = False
        if isinstance(target, (str, bytes, bytearray)):
            f = open(target, "wb")
            close_after = True
        else:
            f = target

        try:
            for link in self.links:
                msg = getbot_id(link).forward(link)
                file_id = msg.document.file_id
                bot = getbot_id(link).bot
                tg_file = bot.get_file(file_id)
                chunk = bot.download_file(tg_file.file_path)
                f.write(chunk)
        finally:
            if close_after:
                f.close()
    
    def _upload_from_file(self, file_obj):
        """
        Upload data from an already opened file-like object directly to Telegram.
        Does not keep data in RAM.
        """
        bot = getbot()
        self.links = []

        # читаем кусками и отправляем каждый как документ
        while True:
            chunk = file_obj.read(FILE_SIZE)
            if not chunk:
                break
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            doc_id = bot.send_document_id(chunk)
            self.links.append(doc_id)

        pages = self._split_links_into_pages(self.links)
        continuation_id = None
        self.pages = []

        for page in pages[:0:-1]:
            continuation_id = bot.send_message_id(
                TEXT_PREFIX + (f'{CONTINUATION_PREFIX} {continuation_id.to_str()} ' if continuation_id else '') + page
            )
            self.pages.append(continuation_id)

        main_content = LINKED_STRING_PREFIX + (f'{CONTINUATION_PREFIX} {continuation_id.to_str()} ' if continuation_id else '') + pages[0]
        main_id = bot.send_message_id(main_content)
        self.pages.append(main_id)
        self._id = main_id

    def set(self, value=None, file=None, path=None):
        """
        Set a new value for the LinkedString and upload it.
        Works with:
          - value: str
          - file: open file-like object
          - path: path to file (str or Path)
        """
        self.links = []
        self.pages = []
        if path is not None:
            with open(path, "rb") as f:
                self._upload_from_file(f)
            return
        if file is not None:
            self._upload_from_file(file)
            return
        if value is None:
            value = ""
        self.value = [value[i:i+FILE_SIZE] for i in range(0, len(value), FILE_SIZE)]
        self.upload()

    def download(self):
        """Queue a download operation to fetch the string from Telegram."""
        if self.downloading.empty():
            threading.Thread(target=self.tdownload, daemon=True).start()
        else:
            self.downloading.put(1)

    def tdownload(self):
        """Worker thread for downloading string data from Telegram."""
        with self.isdownlock:
            self.isdownloading = True
        
        if self._id is None:
            with self.isdownlock:
                self.isdownloading = False
            return
        
        text = getbot_id(self._id).get_text(self._id)
        self.pages = [self._id]
        
        if text[:2] == LINKED_STRING_PREFIX:
            text = text[2:]
            with self.linklock:
                self.links = []
                while text and text[0] == CONTINUATION_PREFIX:
                    next_id = None
                    for id_str in text[1:].split():
                        current_id = Id().from_str(id_str)
                        if next_id is None:
                            next_id = current_id
                            self.pages.append(current_id)
                        else:
                            self.links.append(current_id)
                    text = getbot_id(next_id).get_text(next_id)[1:]
                
                self.pages.reverse()
                for id_str in text.split():
                    self.links.append(Id().from_str(id_str))
                self.value = [None] * len(self.links)
        else:
            raise ValueError(f"Message {self._id} is not a linked string (expected prefix '{LINKED_STRING_PREFIX}')")
        
        if not self.downloading.empty():
            while not self.downloading.empty():
                self.downloading.get()
            threading.Thread(target=self.tdownload, daemon=True).start()
        else:
            with self.isdownlock:
                self.isdownloading = False

    def upload(self):
        """Queue an upload operation to save the string to Telegram."""
        if self.uploading.empty():
            thread = threading.Thread(target=self.tupload, args=(self._id,), daemon=True)
            self._id = None
            thread.start()
        else:
            self.uploading.put(1)

    def tupload(self, id):
        """Worker thread for uploading string data to Telegram.
        
        Args:
            id: Existing message ID to update, or None to create new
        """
        self.pages = []
        if not isinstance(id, Id):
            id = getbot().send_message_id("null")
        
        with self.linklock:
            self.links = [getbot().send_document_id(part.encode('utf-8')) for part in self.value]
            pages = self._split_links_into_pages(self.links)
        
        # Upload continuation pages in reverse order
        continuation_id = None
        for page in pages[:0:-1]:
            continuation_id = getbot().send_message_id(
                TEXT_PREFIX + (f'{CONTINUATION_PREFIX} {continuation_id.to_str()} ' if continuation_id else '') + page
            )
            self.pages.append(continuation_id)

        # Upload or update the main page
        main_content = LINKED_STRING_PREFIX + (f'{CONTINUATION_PREFIX} {continuation_id.to_str()} ' if continuation_id else '') + pages[0]
        
        if isinstance(id, Id):
            getbot_id(id).edit_message(id, main_content)
            self.pages.append(id)
        else:
            id = getbot_id(id).send_message_id(main_content)
            self.pages.append(id)
        
        if not self.uploading.empty():
            while not self.uploading.empty():
                self.uploading.get()
            threading.Thread(target=self.tupload, args=(id,), daemon=True).start()
        else:
            self._id = id
    
    def _split_links_into_pages(self, links):
        """Split links into pages that fit within message size limits.
        
        Args:
            links: List of Id objects to split into pages
            
        Returns:
            List of strings, each containing space-separated link IDs
        """
        pages = []
        current_page = ""
        
        for link in links:
            link_str = link.to_str()
            if len(current_page + link_str) > MAX_MESSAGE_LENGTH:
                if current_page:
                    pages.append(current_page.strip())
                current_page = link_str
            else:
                current_page += " " + link_str
        
        if current_page:
            pages.append(current_page.strip())
        
        return pages if pages else [""]

    def link_upload(self, id):
        """Upload only the link structure without re-uploading documents.
        
        Args:
            id: Existing message ID to update, or None to create new
        """
        self.pages = []
        if not isinstance(id, Id):
            id = getbot().send_message_id("null")
        
        with self.linklock:
            pages = self._split_links_into_pages(self.links)
        
        # Upload continuation pages in reverse order
        continuation_id = None
        for page in pages[:0:-1]:
            continuation_id = getbot().send_message_id(
                TEXT_PREFIX + (f'{CONTINUATION_PREFIX} {continuation_id.to_str()} ' if continuation_id else '') + page
            )
            self.pages.append(continuation_id)

        # Upload or update the main page
        main_content = LINKED_STRING_PREFIX + (f'{CONTINUATION_PREFIX} {continuation_id.to_str()} ' if continuation_id else '') + pages[0]
        
        if isinstance(id, Id):
            getbot_id(id).edit_message(id, main_content)
            self.pages.append(id)
        else:
            id = getbot_id(id).send_message_id(main_content)
            self.pages.append(id)
        
        if not self.uploading.empty():
            while not self.uploading.empty():
                self.uploading.get()
            threading.Thread(target=self.tupload, args=(id,), daemon=True).start()
        else:
            self._id = id

    @property
    def id(self):
        """Get the Telegram message ID (waits for upload if needed)."""
        while not self.uploading.empty() or self._id is None:
            time.sleep(SLEEP_INTERVAL)
        return self._id
    
    @id.setter
    def id(self, value):
        """Set the Telegram message ID and download the string."""
        self._id = Id(value)
        self.download()

    def cache(self, start=None, end=None, *, thread=True):
        """Download and cache string chunks from Telegram."""
        # wait for ongoing downloads
        while True:
            with self.isdownlock:
                if not self.isdownloading:
                    break
            time.sleep(SLEEP_INTERVAL)

        # Если self.value ещё None (например, после set(file=...)), инициализируем список
        if self.value is None:
            self.value = [None] * len(self.links)

        if start is None and end is None:
            # download all uncached chunks
            for i in range(len(self.links)):
                if self.value[i] is None:
                    self._download_chunk(i, thread)
        elif end is None:
            i = start // FILE_SIZE
            if self.value[i] is None:
                self._download_chunk(i, thread)
        else:
            for i in range(min(len(self.links) - 1, start // FILE_SIZE), min(len(self.links), end // FILE_SIZE + 1)):
                if self.value[i] is None:
                    self._download_chunk(i, thread)

    def __str__(self):
        """Convert to string by caching and joining all chunks."""
        # Если self.value ещё None (например, после set(file=...)), создаем пустой список
        if self.value is None:
            self.value = [None] * len(self.links)
        self.cache(thread=False)
        # Для любых None заменяем на пустую строку
        return "".join(chunk if chunk is not None else "" for chunk in self.value)

    
    def _download_chunk(self, index, use_thread=True):
        """Download a specific chunk from Telegram.
        
        Args:
            index: Chunk index to download
            use_thread: Whether to use a separate thread
        """
        def task():
            with self.linklock:
                msg = getbot_id(self.links[index]).forward(self.links[index])
                file_id = msg.document.file_id
                file = getbot_id(self.links[index]).bot.get_file(file_id)
                self.value[index] = getbot_id(self.links[index]).bot.download_file(file.file_path).decode("utf-8")
        
        if use_thread:
            threading.Thread(target=task, daemon=True).start()
        else:
            task()
    
    def wait(self):
        """Wait for the string to be fully initialized."""
        while self.value is None:
            time.sleep(SLEEP_INTERVAL)
        while self._id is None:
            time.sleep(SLEEP_INTERVAL)
        while len(self.links) == 0:
            time.sleep(SLEEP_INTERVAL)
    
    def get(self):
        """Get the complete string value."""
        return str(self)
    
    def __str__(self):
        """Convert to string by caching and joining all chunks."""
        self.cache(thread=False)
        return "".join(self.value)
    
    def __repr__(self):
        """Return a representation of the string."""
        return 's"' + "".join(self.value) + '"'
    
    def __getitem__(self, index):
        """Get character(s) at the specified index or slice."""
        self.wait()
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return "".join(self[i] for i in range(start, stop))
        else:
            return self.value[index // FILE_SIZE][index % FILE_SIZE]

    def __setitem__(self, index, value):
        """Set character(s) at the specified index or slice."""
        self.wait()
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if (stop - start) == len(value):
                # Replace exact slice
                for idx in range(start, stop):
                    self[idx] = value[idx - start]
                    
                    def update_chunk(chunk_idx=idx // FILE_SIZE):
                        with self.linklock:
                            self.links[chunk_idx] = getbot().send_document_id(
                                self.value[chunk_idx].encode('utf-8')
                            )
                    threading.Thread(target=update_chunk, daemon=True).start()
                
                threading.Thread(target=lambda: self.link_upload(self._id), daemon=True).start()
            else:
                # Replace with different length - rebuild entire string
                new = "".join(self.value[:start // FILE_SIZE])
                new += self.value[start // FILE_SIZE][:start % FILE_SIZE]
                new += value
                new += self.value[stop // FILE_SIZE][stop % FILE_SIZE:]
                new += "".join(self.value[stop // FILE_SIZE + 1:])
                self.set(new)
        else:
            # Replace single character
            self.value[index // FILE_SIZE] = (
                self.value[index // FILE_SIZE][:index % FILE_SIZE] + 
                value + 
                self.value[index // FILE_SIZE][index % FILE_SIZE + 1:]
            )
            
            def update_and_upload():
                with self.linklock:
                    self.links[index // FILE_SIZE] = getbot().send_document_id(
                        self.value[index // FILE_SIZE].encode('utf-8')
                    )
                self.link_upload(self._id)
            
            threading.Thread(target=update_and_upload, daemon=True).start()
    
    def __len__(self):
        """Return the total length of the string."""
        self.wait()
        return sum(map(len, self.value))
    
    def __iter__(self):
        """Iterate over characters in the string."""
        self.wait()
        self.cache(thread=False)
        for chunk in self.value:
            for char in chunk:
                yield char
    
    def __add__(self, other):
        """Concatenate with another string."""
        if isinstance(other, str):
            return LinkedString(str(self) + other)
        else:
            return LinkedString(str(self) + str(other))
    
    def __mul__(self, other):
        """Repeat the string."""
        if isinstance(other, int):
            return LinkedString(str(self) * other)
        else:
            raise TypeError("Cannot multiply string by non-integer")
    
    def __iadd__(self, other):
        """In-place concatenation."""
        if isinstance(other, str):
            self.set(str(self) + other)
        else:
            self.set(str(self) + str(other))
        return self

    def __imul__(self, other):
        """In-place repetition."""
        if isinstance(other, int):
            self.set(str(self) * other)
            return self
        else:
            raise TypeError("Cannot multiply string by non-integer")
    
    def __inter__(self):
        self.wait()
        for i in range(len(self)):
            yield self[i]


class SimpleString:
    """A simple string stored directly in a Telegram message.
    
    This class is optimized for smaller strings that fit within a single
    Telegram message.
    """
    
    def __init__(self, value=None, id=None, file=None, path=None):
        """Initialize a SimpleString.
        
        Args:
            value: Initial string value (optional)
            id: Existing Telegram message ID to load from (optional)
        """
        self.uploading = queue.Queue()
        self.downloading = queue.Queue()
        self.value = None
        self._id = None
        if file is not None or path is not None:
            if file is not None:
                f = file
                close_after = False
            else:
                f = open(path, "rb")
                close_after = True

            try:
                data = f.read()
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")
                if len(data) > 3950:
                    raise ValueError("File too large for SimpleString (use LinkedString instead).")

                self.value = data
                self.upload()
            finally:
                if close_after:
                    f.close()
            return

        if value is None:
            self.value = None
            try:
                self._id = Id(id)
                self.download()
            except:
                self._id = None
                self.download()
        else:
            self.value = value if isinstance(value, str) else str(value)
            self._id = Id(id) if id is not None else None
            self.upload()

    def save(self, target):
        """
        Save SimpleString content to a file or file-like object.

        Args:
            target: Path to file (str or Path) OR open binary file object.
        """
        self.wait()
        close_after = False
        if isinstance(target, (str, bytes, bytearray)):
            f = open(target, "wb")
            close_after = True
        else:
            f = target

        try:
            f.write(self.value.encode("utf-8"))
        finally:
            if close_after:
                f.close()

    def set(self, value=None, file=None, path=None):
        """
        Set a new value for the SimpleString and upload it.

        Works with:
          - value: str
          - file: open file-like object
          - path: path to file (str or Path)
        """
        if path is not None:
            with open(path, "rb") as f:
                data = f.read()
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            if len(data) > 3950:
                raise ValueError("File too large for SimpleString (use LinkedString instead).")
            self.value = data
            self.upload()
            return
        if file is not None:
            data = file.read()
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            if len(data) > 3950:
                raise ValueError("File too large for SimpleString (use LinkedString instead).")
            self.value = data
            self.upload()
            return
        if value is None:
            value = ""
        self.value = str(value)
        self.upload()


    def download(self):
        """Queue a download operation to fetch the string from Telegram."""
        if self.downloading.empty():
            threading.Thread(target=self.tdownload, daemon=True).start()
        else:
            self.downloading.put(1)

    def tdownload(self):
        """Worker thread for downloading string data from Telegram."""
        if self._id is None:
            return
        
        text = getbot_id(self._id).get_text(self._id)
        
        if text[:2] == SIMPLE_STRING_PREFIX:
            self.value = text[2:-1]
        else:
            raise ValueError(f"Message {self._id} is not a simple string (expected prefix '{SIMPLE_STRING_PREFIX}')")
        
        if not self.downloading.empty():
            while not self.downloading.empty():
                self.downloading.get()
            threading.Thread(target=self.tdownload, daemon=True).start()

    def upload(self):
        """Queue an upload operation to save the string to Telegram."""
        if self.uploading.empty():
            thread = threading.Thread(target=self.tupload, args=(self._id,), daemon=True)
            self._id = None
            thread.start()
        else:
            self.uploading.put(1)

    def tupload(self, id):
        """Worker thread for uploading string data to Telegram.
        
        Args:
            id: Existing message ID to update, or None to create new
        """
        if isinstance(id, Id):
            getbot_id(id).edit_message(id, SIMPLE_STRING_PREFIX + self.value + END_MARKER)
        else:
            bot = getbot()
            id = Id(bot.bot_index, bot.group_index, bot.send_message(SIMPLE_STRING_PREFIX + self.value + END_MARKER))

        if not self.uploading.empty():
            while not self.uploading.empty():
                self.uploading.get()
            threading.Thread(target=self.tupload, args=(id,), daemon=True).start()
        else:
            self._id = id
    
    @property
    def id(self):
        """Get the Telegram message ID (waits for upload if needed)."""
        while self._id is None:
            time.sleep(SLEEP_INTERVAL)
        return self._id
    
    @id.setter
    def id(self, value):
        """Set the Telegram message ID and download the string."""
        self._id = Id(value)
        self.download()
    
    def wait(self):
        """Wait for the string to be fully initialized."""
        while self.value is None:
            time.sleep(SLEEP_INTERVAL)
        while self._id is None:
            time.sleep(SLEEP_INTERVAL)
    
    def get(self):
        """Get the string value."""
        return str(self)

    def __repr__(self):
        """Return a representation of the string."""
        self.wait()
        return f'''s"{str(self)}"'''
    
    def __str__(self):
        self.wait()
        return self.value
    
    def __inter__(self):
        self.wait()
        for s in self.value:
            yield s