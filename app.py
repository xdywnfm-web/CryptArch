from __future__ import annotations

from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from engine import EXTENSIONS, Job, QUALITY


BG = "#101621"
PANEL = "#192334"
TEXT = "#eaf0fa"
MUTED = "#a9b9ce"
ACCENT = "#68d9c0"


class CryptArch(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CryptArch — сжатие видео")
        icon_base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        icon_path = icon_base / "assets" / "CryptArch.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except tk.TclError:
                pass
        self.geometry("840x780")
        self.minsize(700, 700)
        self.configure(bg=BG)
        self.events = queue.Queue()
        self.job = None
        self.running = False
        self.paused = False
        self.source = tk.StringVar()
        self.output = tk.StringVar()
        self.quality = tk.StringVar(value="Сбалансированное")
        self.codec = tk.StringVar(value="H.265")
        self.device = tk.StringVar(value="CPU")
        self.workers = tk.StringVar(value="2")
        self.last_workers = "2"
        self.status = tk.StringVar(value="Выберите видеофайл или папку с видео")
        self.progress_text = tk.StringVar(value="0%  ·  0 из 0")
        self.eta = tk.StringVar(value="Оставшееся время: —")
        self._build()
        self._event_timer = self.after(150, self._events)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", padding=7, fieldbackground="#25344a", background="#25344a",
                        foreground=TEXT, arrowcolor=TEXT, borderwidth=0)
        style.map("TCombobox", fieldbackground=[("readonly", "#25344a")],
                  foreground=[("readonly", TEXT)])
        self.option_add("*TCombobox*Listbox.background", "#25344a")
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        style.configure("Crypt.Horizontal.TProgressbar", troughcolor="#26364b", background=ACCENT,
                        borderwidth=0, thickness=12)
        self.main = tk.Frame(self, bg=BG, padx=30, pady=20)
        self.main.pack(fill="both", expand=True)
        head = tk.Frame(self.main, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="CRYPT", fg=TEXT, bg=BG, font=("Segoe UI", 23, "bold")).pack(side="left")
        tk.Label(head, text="ARCH", fg=ACCENT, bg=BG, font=("Segoe UI", 23, "bold")).pack(side="left")
        tk.Label(self.main, text="Понятное и безопасное сжатие видео", fg=MUTED, bg=BG,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 17))
        card = tk.Frame(self.main, bg=PANEL, padx=20, pady=16)
        card.pack(fill="x")
        self.label(card, "ИСТОЧНИК", small=True).pack(anchor="w")
        self.entry(card, self.source).pack(fill="x", pady=(6, 7))
        buttons = tk.Frame(card, bg=PANEL)
        buttons.pack(fill="x")
        self.controls = []
        self.button(buttons, "Выбрать файл", self.choose_file).pack(side="left", padx=(0, 8))
        self.button(buttons, "Выбрать папку", self.choose_folder).pack(side="left")
        self.label(card, "ПАПКА ДЛЯ РЕЗУЛЬТАТА", small=True).pack(anchor="w", pady=(15, 0))
        row = tk.Frame(card, bg=PANEL)
        row.pack(fill="x", pady=(6, 0))
        self.entry(row, self.output).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.button(row, "Обзор", self.choose_output).pack(side="left")
        tk.Label(card, text="Оригиналы не изменяются. Все аудиодорожки объединяются в одну; формат — MP4.",
                 fg=MUTED, bg=PANEL, font=("Segoe UI", 9)).pack(anchor="w", pady=(9, 0))
        options = tk.Frame(self.main, bg=PANEL, padx=20, pady=16)
        options.pack(fill="x", pady=(12, 0))
        for col in range(2):
            options.columnconfigure(col, weight=1, uniform="options")
        self.combo(options, "КАЧЕСТВО", self.quality, list(QUALITY), 0, 0)
        self.combo(options, "КОДЕК", self.codec, ["H.264", "H.265"], 0, 1)
        self.combo(options, "УСТРОЙСТВО", self.device, ["CPU", "GPU"], 1, 0)
        worker_combo = self.combo(options, "ПАРАЛЛЕЛЬНЫХ ВИДЕО", self.workers, ["2", "4", "8"], 1, 1)
        worker_combo.bind("<<ComboboxSelected>>", self.worker_changed)
        tk.Label(options, text="GPU ускоряет сжатие при поддержке NVIDIA, AMD или Intel. "
                 "H.264 совместимее; H.265 обычно сжимает лучше.",
                 fg=MUTED, bg=PANEL, font=("Segoe UI", 9), wraplength=700, justify="left").grid(
                     row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        bottom = tk.Frame(self.main, bg=BG)
        bottom.pack(fill="x", pady=(16, 0))
        self.start_btn = tk.Button(bottom, text="НАЧАТЬ СЖАТИЕ", command=self.start, bg=ACCENT,
                                   fg="#092019", activebackground="#9ae9d8", relief="flat",
                                   font=("Segoe UI", 10, "bold"), padx=20, pady=10, cursor="hand2")
        self.start_btn.pack(side="left")
        self.pause_btn = self.button(bottom, "Пауза", self.pause, track=False)
        self.pause_btn.pack(side="left", padx=(10, 0))
        self.cancel_btn = self.button(bottom, "Отменить", self.cancel, track=False)
        self.cancel_btn.pack(side="left", padx=(8, 0))
        self.pause_btn.config(state="disabled")
        self.cancel_btn.config(state="disabled")
        self.bar = ttk.Progressbar(self.main, style="Crypt.Horizontal.TProgressbar", maximum=100)
        self.bar.pack(fill="x", pady=(20, 6))
        info = tk.Frame(self.main, bg=BG)
        info.pack(fill="x")
        tk.Label(info, textvariable=self.progress_text, bg=BG, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(info, textvariable=self.eta, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="right")
        tk.Label(self.main, textvariable=self.status, bg=BG, fg=MUTED, anchor="w",
                 font=("Segoe UI", 9)).pack(fill="x", pady=(8, 0))

    def label(self, parent, text, small=False):
        return tk.Label(parent, text=text, bg=PANEL, fg=MUTED,
                        font=("Segoe UI", 8 if small else 10, "bold"))

    def entry(self, parent, variable):
        entry = tk.Entry(parent, textvariable=variable, bg="#25344a", fg=TEXT, insertbackground=TEXT,
                         relief="flat", font=("Segoe UI", 10), readonlybackground="#25344a")
        entry.configure(state="readonly")
        return entry

    def button(self, parent, text, command, track=True):
        b = tk.Button(parent, text=text, command=command, bg="#304259", fg=TEXT,
                      activebackground="#405775", activeforeground=TEXT, disabledforeground="#78879a",
                      relief="flat", font=("Segoe UI", 9), padx=12, pady=6, cursor="hand2")
        if track:
            self.controls.append(b)
        return b

    def combo(self, parent, label, variable, values, row, col):
        frame = tk.Frame(parent, bg=PANEL)
        frame.grid(row=row * 2, column=col, sticky="ew", padx=(0, 12) if col == 0 else (0, 0),
                   pady=(0, 10))
        self.label(frame, label, small=True).pack(anchor="w", pady=(0, 5))
        box = ttk.Combobox(frame, textvariable=variable, values=values, state="readonly",
                           font=("Segoe UI", 10))
        box.pack(fill="x")
        self.controls.append(box)
        return box

    def choose_file(self):
        p = filedialog.askopenfilename(title="Выберите видео", filetypes=[
            ("Видеофайлы", " ".join("*" + x for x in sorted(EXTENSIONS))), ("Все файлы", "*.*")])
        if p:
            self.source.set(p)
            self.output.set(str(Path(p).parent / "compressed"))

    def choose_folder(self):
        p = filedialog.askdirectory(title="Выберите папку с видео", mustexist=True)
        if p:
            self.source.set(p)
            self.output.set(str(Path(p) / "compressed"))

    def choose_output(self):
        p = filedialog.askdirectory(title="Выберите папку для результатов", mustexist=True)
        if p:
            self.output.set(p)

    def worker_changed(self, _event=None):
        if self.workers.get() == "8" and self.last_workers != "8":
            messagebox.showwarning("Высокая нагрузка",
                                   "8 параллельных задач создают высокую нагрузку. "
                                   "На слабых системах возможны зависания, лаги или сбои системы.",
                                   parent=self)
        self.last_workers = self.workers.get()

    def set_controls(self, running):
        self.running = running
        for c in self.controls:
            if isinstance(c, ttk.Combobox):
                c.configure(state="disabled" if running else "readonly")
            else:
                c.configure(state="disabled" if running else "normal")
        self.start_btn.configure(state="disabled" if running else "normal")
        self.pause_btn.configure(state="normal" if running else "disabled", text="Пауза")
        self.cancel_btn.configure(state="normal" if running else "disabled")

    def start(self):
        if not self.source.get() or not self.output.get():
            messagebox.showerror("CryptArch", "Выберите источник и папку для результата.", parent=self)
            return
        self.bar["value"] = 0
        self.progress_text.set("0%  ·  подготовка")
        self.eta.set("Оставшееся время: —")
        self.paused = False
        self.set_controls(True)
        self.job = Job(self.source.get(), self.output.get(), self.quality.get(), self.codec.get(),
                       self.device.get(), int(self.workers.get()),
                       lambda kind, data: self.events.put((kind, data)))
        threading.Thread(target=self.job.run, daemon=True).start()

    def pause(self):
        if self.job:
            self.paused = not self.paused
            self.job.set_pause(self.paused)
            self.pause_btn.configure(text="Продолжить" if self.paused else "Пауза")
            self.status.set("Пауза" if self.paused else "Сжатие видео…")

    def cancel(self):
        if self.job and messagebox.askyesno("Отмена", "Остановить сжатие? Готовые файлы сохранятся.",
                                            parent=self):
            self.job.cancel()
            self.status.set("Останавливаем задачи…")
            self.pause_btn.configure(state="disabled")
            self.cancel_btn.configure(state="disabled")

    def close(self):
        if self.running:
            if not messagebox.askyesno("Выход", "Остановить сжатие и закрыть приложение?", parent=self):
                return
            self.job.cancel()
            self.withdraw()
            # Wait for workers to clean their temporary outputs before exiting.
            self.after(150, self._close_when_done)
        else:
            self.destroy()

    def destroy(self):
        if self._event_timer is not None:
            try:
                self.after_cancel(self._event_timer)
            except tk.TclError:
                pass
            self._event_timer = None
        super().destroy()

    def _close_when_done(self):
        if self.running:
            self.after(150, self._close_when_done)
        else:
            self.destroy()

    def _events(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "status":
                    self.status.set(data)
                elif kind == "started":
                    self.status.set("Сжатие видео…")
                elif kind == "progress":
                    pct = data["fraction"] * 100
                    self.bar["value"] = pct
                    self.progress_text.set(f"{pct:.0f}%  ·  {data['done']} из {data['total']}")
                    eta = data["eta"]
                    estimate = "Осталось: —" if eta is None else f"Осталось примерно: {max(1, round(eta / 60))} мин."
                    speed = data["speed"]
                    self.eta.set(f"{estimate}  ·  Скорость: {speed:.1f}x" if speed > 0 else estimate)
                elif kind == "fatal":
                    self.set_controls(False)
                    self.status.set("Не удалось начать сжатие")
                    messagebox.showerror("CryptArch", data, parent=self)
                elif kind == "finished":
                    self.set_controls(False)
                    self.show_result(data)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self._event_timer = self.after(150, self._events)

    def show_result(self, data):
        results = data["results"]
        ok = [r for r in results if r["status"] == "ok"]
        errors = [r for r in results if r["status"] in ("error", "skipped")]
        larger = [r for r in ok if r["compressed"] > r["original"]]
        original, compressed = data["original"], data["compressed"]
        pct = (1 - compressed / original) * 100 if original else None
        if pct is None:
            comparison = "Нет завершённых файлов для сравнения."
        elif pct >= 0:
            comparison = f"Результат на {pct:.1f}% меньше оригиналов."
        else:
            comparison = f"Результат на {-pct:.1f}% больше оригиналов."
        state = "Остановлено" if data["cancelled"] else "Готово"
        self.status.set(f"{state}: обработано {len(ok)} из {data['total']}. {comparison}")
        lines = [f"Обработано файлов: {len(ok)} из {data['total']}", comparison,
                 "Оригиналы не изменены."]
        if errors:
            lines.append(f"\nОшибки или пропуски: {len(errors)}")
            lines.extend(f"• {r['source']}: {r['message']}" for r in errors)
        if larger:
            lines.append("\nСжатые файлы оказались больше оригинала:")
            lines.extend("• " + r["source"] for r in larger)
        self.result_window(state, "\n".join(lines), warning=bool(errors or larger))

    def result_window(self, title, text, warning=False):
        # Native Windows message boxes do not scroll. Paginate long reports so
        # every error and oversized file remains visible.
        pages, current = [], []
        for line in text.splitlines():
            if current and (len(current) >= 10 or sum(len(s) for s in current) + len(line) > 1100):
                pages.append("\n".join(current))
                current = []
            current.append(line)
        if current:
            pages.append("\n".join(current))
        dialog = messagebox.showwarning if warning else messagebox.showinfo
        for i, page in enumerate(pages, 1):
            suffix = f" ({i}/{len(pages)})" if len(pages) > 1 else ""
            dialog("CryptArch — " + title + suffix, page, parent=self)


if __name__ == "__main__":
    CryptArch().mainloop()
