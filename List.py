from .id_class import Id
from .config import getbot, getbot_id
import threading
import time

MAX_PAGE_LENGTH = 3900  # лимит длины сообщения Telegram


class List:
    """Асинхронный Telegram List с авто-синхронизацией Var, безопасным ожиданием загрузки и лимитом кеша страниц."""

    def __init__(self, value=None, id=None, cache_pages=0):
        self._id = None
        self.pages = []
        self.page_data = {}
        self.items = []
        self.lock = threading.RLock()

        # Upload control
        self._uploading = False
        self._reschedule_upload = False
        self._upload_thread = None

        # Настройки кеша
        self.cache_pages = cache_pages
        self._page_access = {}  # для LRU

        if id is not None:
            self._id = Id(id)
            threading.Thread(target=self.download, daemon=True).start()
        elif value is not None:
            self._add_iterable(value)
            self.schedule_upload()
        else:
            self.schedule_upload()

    # ==== Helpers ====

    def _wait_loaded(self):
        """Ожидает, пока self.items реально загружены (нет None)."""
        while True:
            with self.lock:
                # Считаем загруженным, если пустой или без None
                ready = bool(self.items) and all(v is not None for v in self.items)
                empty_new = not self.pages and not self.page_data
                if ready or empty_new:
                    return
            time.sleep(0.05)

    def _wait_var_ready(self, v):
        """Ожидает, пока Var.id не станет готов."""
        while v.id is None:
            time.sleep(0.05)

    def _add_iterable(self, iterable):
        """Добавляет элементы из iterable, распаковывая вложенные списки/кортежи."""
        for v in iterable:
            if isinstance(v, (list, tuple)):
                self._add_iterable(v)
            else:
                self.items.append(self._wrap(v))

    def _wrap(self, v):
        from .Var import Var
        """Оборачивает значение в Var и ставит ссылку на родителя."""
        if isinstance(v, Var):
            v._parent = self
            return v
        newv = Var(v)
        newv._parent = self
        return newv

    def _split_pages(self):
        """Разделяет список на страницы с учётом лимита Telegram."""
        pages, current = [], []
        length = 2
        for v in self.items:
            self._wait_var_ready(v)
            line = v.id.to_str() + "\n"
            if length + len(line) > MAX_PAGE_LENGTH:
                pages.append(current)
                current = []
                length = 2
            current.append(v)
            length += len(line)
        if current:
            pages.append(current)
        return pages

    # ==== Upload control ====

    def schedule_upload(self):
        """Планирует отложенный асинхронный upload."""
        with self.lock:
            if self._uploading:
                self._reschedule_upload = True
                return
            self._uploading = True
            self._reschedule_upload = False
            threading.Thread(target=self._upload_worker, daemon=True).start()

    def _upload_worker(self):
        try:
            self.upload()
        finally:
            with self.lock:
                if self._reschedule_upload:
                    self._reschedule_upload = False
                    threading.Thread(target=self._upload_worker, daemon=True).start()
                else:
                    self._uploading = False

    def upload(self):
        """Синхронная выгрузка структуры списка (без содержимого Var)."""
        self._wait_loaded()
        with self.lock:
            bot = getbot()
            pages = self._split_pages()
            new_page_ids = []

            for pg in pages:
                text = "P\n" + "".join(v.id.to_str() + "\n" for v in pg)
                if len(self.pages) > len(new_page_ids):
                    pid = self.pages[len(new_page_ids)]
                    getbot_id(pid).edit_message(pid, text)
                else:
                    msg_id = bot.send_message(text)
                    pid = Id(bot.bot_index, bot.group_index, msg_id)
                new_page_ids.append(pid)
            self.pages = new_page_ids

            # Обновляем главную страницу
            meta = "L" + str(len(self.items)) + "\n" + "\n".join(p.to_str() for p in self.pages)
            if self._id is None:
                msg_id = bot.send_message(meta)
                self._id = Id(bot.bot_index, bot.group_index, msg_id)
            else:
                getbot_id(self._id).edit_message(self._id, meta)

    # ==== Download ====

    def download(self):
        """Загружает главную страницу и страницы."""
        if self._id is None:
            return

        # Попытка получить мета-текст
        text = ""
        for _ in range(50):  # до 5 секунд
            try:
                text = getbot_id(self._id).forward(self._id).text
                if text and text.strip():
                    break
            except Exception:
                pass
            time.sleep(0.1)

        if not text or not text.startswith("L"):
            print(f"[WARN] Invalid or missing list meta for {self._id}")
            return

        lines = text.strip().splitlines()
        self.pages = [Id().from_str(x) for x in lines[1:]]
        self.items = [None] * int(lines[0][1:])

        threads = []
        for page_id in self.pages:
            t = threading.Thread(target=self._download_page, args=(page_id,), daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    def _download_page(self, page_id: Id):
        from .Var import Var
        """Загружает одну страницу Var (с учётом лимита кеша)."""
        with self.lock:
            if page_id in self.page_data:
                self._page_access[page_id] = time.time()
                return

        text = getbot_id(page_id).forward(page_id).text
        lines = text.strip().splitlines()
        if not lines or lines[0] != "P":
            return

        vars_ = []
        for x in lines[1:]:
            if x.strip():
                v = Var(id=Id().from_str(x.strip()))
                v._parent = self
                vars_.append(v)

        with self.lock:
            # добавляем страницу в кеш
            self.page_data[page_id] = vars_
            self._page_access[page_id] = time.time()

            # очищаем лишние страницы
            self._enforce_cache_limit_locked()

            # пересобираем общий список
            flat = []
            for pid in self.pages:
                if pid in self.page_data:
                    flat.extend(self.page_data[pid])
                else:
                    flat.extend([None] * len(vars_))  # placeholder
            self.items = flat[:len(self.items)]

    def _enforce_cache_limit_locked(self):
        """Удаляет старые страницы, если кеш превышает лимит."""
        if self.cache_pages <= 0:
            return
        if len(self.page_data) <= self.cache_pages:
            return

        # Сортируем по времени последнего доступа
        sorted_pages = sorted(self._page_access.items(), key=lambda x: x[1])
        while len(self.page_data) > self.cache_pages:
            old_pid, _ = sorted_pages.pop(0)
            if old_pid in self.page_data:
                del self.page_data[old_pid]
            if old_pid in self._page_access:
                del self._page_access[old_pid]
            print(f"[CACHE] Removed page {old_pid.to_str()} from cache")

    # ==== List API ====

    def append(self, value):
        """Добавление с безопасным ожиданием загрузки."""
        self._wait_loaded()
        with self.lock:
            self.items.append(self._wrap(value))
        self.schedule_upload()

    def extend(self, iterable):
        self._wait_loaded()
        with self.lock:
            for v in iterable:
                self.items.append(self._wrap(v))
        self.schedule_upload()

    def insert(self, index, value):
        self._wait_loaded()
        with self.lock:
            self.items.insert(index, self._wrap(value))
        self.schedule_upload()

    def pop(self, index=-1):
        self._wait_loaded()
        with self.lock:
            val = self.items.pop(index)
        self.schedule_upload()
        return val

    def reverse(self):
        self._wait_loaded()
        with self.lock:
            self.items.reverse()
        self.schedule_upload()

    def _wait_page(self, index):
        """Ожидает подгрузку нужной страницы (с кешом)."""
        if not self.pages:
            return
        page_size = max(1, len(self.items) // max(1, len(self.pages)))
        page_index = min(index // page_size, len(self.pages) - 1)
        pid = self.pages[page_index]

        # Если страницы нет в кеше — загружаем заново
        if pid not in self.page_data:
            threading.Thread(target=self._download_page, args=(pid,), daemon=True).start()
            while pid not in self.page_data:
                time.sleep(0.05)
        else:
            # Обновляем "время последнего доступа"
            with self.lock:
                self._page_access[pid] = time.time()

    def __getitem__(self, key):
        self._wait_loaded()
        if isinstance(key, slice):
            return [self[i] for i in range(*key.indices(len(self.items)))]
        self._wait_page(key)
        return self.items[key]

    def __setitem__(self, key, value):
        self._wait_loaded()
        with self.lock:
            if isinstance(key, slice):
                self.items[key] = [self._wrap(v) for v in value]
            else:
                self.items[key] = self._wrap(value)
        self.schedule_upload()

    def __len__(self):
        self._wait_loaded()
        return len(self.items)

    def __iter__(self):
        self._wait_loaded()
        for i in range(len(self.items)):
            yield self[i]

    def __repr__(self):
        return f"<List {self.items}>"

    def __str__(self):
        self._wait_loaded()
        return "[" + ", ".join(x.__repr__() for x in self.items if x is not None) + "]"
    
    def getreal(self):
        """Возвращает список с подставленными значениями Var.get()."""
        self._wait_loaded()
        result = []
        for item in self.items:
            self._wait_var_ready(item)
            result.append(item.get())
        return result

    @property
    def id(self):
        while self._id is None:
            time.sleep(0.05)
        return self._id
