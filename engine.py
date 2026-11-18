"""Video compression engine. Originals are never modified."""
from __future__ import annotations

import concurrent.futures
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import uuid

EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpeg", ".mpg", ".wmv", ".ts", ".mts"}
QUALITY = {"Высокое качество": 20, "Сбалансированное": 24, "Максимальное сжатие": 28}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def binary(name: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidate = base / "bin" / (name + ".exe")
    if candidate.exists():
        return str(candidate)
    import shutil
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"{name} не найден. Переустановите приложение.")
    return found


def contained(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(path.resolve()), str(root.resolve())]) == str(root.resolve())
    except ValueError:
        return False


def collect(source: Path, output: Path) -> list[tuple[Path, Path]]:
    source, output = source.resolve(), output.resolve()
    if source.is_file():
        if source.suffix.lower() not in EXTENSIONS:
            raise ValueError("Формат выбранного файла не поддерживается.")
        return [(source, output / (source.stem + ".mp4"))]
    if not source.is_dir():
        raise ValueError("Выберите существующий файл или папку.")
    if source == output:
        raise ValueError("Папка результата не должна совпадать с исходной папкой.")
    # Do not follow directory links: they can point outside the selected folder or form cycles.
    items = []
    for current, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = [d for d in dirs if not contained(Path(current) / d, output)
                   and not (Path(current) / d).is_symlink()
                   and not os.path.isjunction(Path(current) / d)]
        for name in files:
            path = Path(current) / name
            if path.suffix.lower() in EXTENSIONS and not path.is_symlink():
                relative = path.relative_to(source).with_suffix(".mp4")
                items.append((path, output / relative))
    return sorted(items, key=lambda x: str(x[0]).lower())


def probe_details(path: Path) -> tuple[float, list[dict]]:
    result = subprocess.run(
        [binary("ffprobe"), "-v", "error",
         "-show_entries", "stream=index,codec_type:stream_tags=handler_name,title:stream_disposition=default:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    if result.returncode:
        raise RuntimeError("Не удалось прочитать видео: " + result.stderr.strip()[-350:])
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not any(s.get("codec_type") == "video" for s in streams):
        raise RuntimeError("В файле не найдена видеодорожка.")
    return max(float(data.get("format", {}).get("duration") or 0), 0), [
        s for s in streams if s.get("codec_type") == "audio"
    ]


def probe(path: Path) -> float:
    return probe_details(path)[0]


def audio_mapping(streams: list[dict]) -> list[str]:
    """Mix all audio tracks into one track to avoid player track selection."""
    if not streams:
        return ["-map", "0:v:0"]
    if len(streams) == 1:
        return ["-map", "0:v:0", "-map", f"0:{int(streams[0]['index'])}",
                "-disposition:a:0", "default"]
    inputs = "".join(f"[0:{int(s['index'])}]" for s in streams)
    graph = (f"{inputs}amix=inputs={len(streams)}:duration=longest:"
             "dropout_transition=0:normalize=1,alimiter=limit=0.95:level=0[cryptarch_mix]")
    return ["-filter_complex", graph, "-map", "0:v:0", "-map", "[cryptarch_mix]",
            "-disposition:a:0", "default", "-metadata:s:a:0", "title=CryptArch mix"]


def gpu_encoder(codec: str) -> tuple[str, str]:
    """Test actual encoder initialization, not just whether it is compiled in."""
    prefix = "h264" if codec == "H.264" else "hevc"
    failures = []
    for suffix, label in (("nvenc", "NVIDIA"), ("amf", "AMD"), ("qsv", "Intel")):
        encoder = prefix + "_" + suffix
        command = [binary("ffmpeg"), "-hide_banner", "-v", "error", "-f", "lavfi",
                   "-i", "color=size=640x360:rate=30", "-frames:v", "1", "-c:v", encoder,
                   "-f", "null", "-"]
        try:
            result = subprocess.run(command, capture_output=True, creationflags=NO_WINDOW, timeout=20)
            if result.returncode == 0:
                return encoder, label
            failures.append(label)
        except subprocess.TimeoutExpired:
            failures.append(label)
    raise RuntimeError("Подходящий GPU-кодировщик не найден или недоступен. Выберите CPU. Проверены NVIDIA, AMD и Intel.")


def encoder_args(codec: str, device: str, quality: str, encoder: str | None) -> list[str]:
    q = QUALITY[quality]
    if device == "CPU":
        return ["-c:v", "libx264" if codec == "H.264" else "libx265", "-preset", "medium", "-crf", str(q)]
    assert encoder
    if encoder.endswith("_nvenc"):
        args = ["-c:v", encoder, "-preset", "p5", "-rc", "vbr", "-cq", str(q), "-b:v", "0"]
    elif encoder.endswith("_qsv"):
        args = ["-c:v", encoder, "-global_quality", str(q)]
    else:
        args = ["-c:v", encoder, "-quality", "quality", "-rc", "cqp",
                "-qp_i", str(q), "-qp_p", str(q)]
    return args


def suspend_process(pid: int, suspend: bool) -> None:
    if os.name != "nt":
        raise OSError("Пауза поддерживается только в Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x0800, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), "Не удалось изменить состояние процесса")
    try:
        function = ntdll.NtSuspendProcess if suspend else ntdll.NtResumeProcess
        function.argtypes = [ctypes.c_void_p]
        function.restype = ctypes.c_long
        if function(handle) != 0:
            raise OSError("Не удалось изменить состояние процесса")
    finally:
        kernel.CloseHandle(handle)


class Job:
    def __init__(self, source, output, quality, codec, device, workers, emit):
        self.source, self.output = Path(source), Path(output)
        self.quality, self.codec, self.device, self.workers = quality, codec, device, workers
        self.emit = emit
        self.cancelled = threading.Event()
        self.pause_gate = threading.Event()
        self.pause_gate.set()
        self.lock = threading.RLock()
        self.processes: dict[int, subprocess.Popen] = {}
        self.paused_pids: set[int] = set()
        self.progress: dict[str, float] = {}
        self.speeds: dict[str, float] = {}
        self.finished = 0
        self.results = []
        self.started = 0.0
        self.pause_started = None
        self.paused_seconds = 0.0

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            for pid, proc in list(self.processes.items()):
                try:
                    if pid in self.paused_pids:
                        suspend_process(pid, False)
                    proc.terminate()
                except (OSError, ProcessLookupError):
                    pass
            self.paused_pids.clear()
            self.pause_gate.set()

    def set_pause(self, paused: bool):
        with self.lock:
            if paused:
                self.pause_gate.clear()
                if self.pause_started is None:
                    self.pause_started = time.monotonic()
                for pid in list(self.processes):
                    try:
                        suspend_process(pid, True)
                        self.paused_pids.add(pid)
                    except OSError:
                        pass
            else:
                for pid in list(self.paused_pids):
                    try:
                        suspend_process(pid, False)
                    except OSError:
                        pass
                self.paused_pids.clear()
                if self.pause_started is not None:
                    self.paused_seconds += time.monotonic() - self.pause_started
                    self.pause_started = None
                self.pause_gate.set()

    def update(self, total):
        with self.lock:
            value = min(sum(self.progress.values()) / total if total else 0, 1)
            elapsed = time.monotonic() - self.started - self.paused_seconds
            if self.pause_started is not None:
                elapsed -= time.monotonic() - self.pause_started
            eta = elapsed * (1 - value) / value if value > .01 else None
            self.emit("progress", {"fraction": value, "done": self.finished, "total": total,
                                   "eta": eta, "speed": sum(self.speeds.values())})

    def run(self):
        try:
            self.emit("status", "Поиск видео…")
            items = collect(self.source, self.output)
            if not items:
                raise ValueError("В выбранной папке не найдено поддерживаемых видео.")
            targets = [os.path.normcase(str(dst)) for _, dst in items]
            if len(targets) != len(set(targets)):
                raise ValueError("Несколько файлов имеют одинаковые имена после преобразования в MP4. Переименуйте их.")
            if any(os.path.normcase(str(src)) == os.path.normcase(str(dst.resolve())) for src, dst in items):
                raise ValueError("Файл результата совпадает с оригиналом. Выберите другую папку.")
            if self.device == "GPU":
                self.emit("status", "Проверка видеокарты…")
                encoder, gpu = gpu_encoder(self.codec)
                self.emit("status", f"Используется {gpu}")
            else:
                encoder = None
            self.started = time.monotonic()
            self.progress = {str(src): 0.0 for src, _ in items}
            self.emit("started", len(items))
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
                futures = [pool.submit(self.process_one, src, dst, encoder, len(items)) for src, dst in items]
                for future in concurrent.futures.as_completed(futures):
                    self.results.append(future.result())
            successful = [r for r in self.results if r["status"] == "ok"]
            original = sum(r["original"] for r in successful)
            compressed = sum(r["compressed"] for r in successful)
            self.emit("finished", {"results": self.results, "total": len(items), "original": original,
                                   "compressed": compressed, "cancelled": self.cancelled.is_set()})
        except Exception as exc:
            self.emit("fatal", str(exc))

    def process_one(self, src, dest, encoder, total):
        result = {"source": str(src), "output": str(dest), "status": "error", "message": ""}
        temp = None
        error_file = None
        proc = None
        try:
            self.pause_gate.wait()
            if self.cancelled.is_set():
                result.update(status="cancelled", message="Отменено")
                return result
            if dest.exists():
                result.update(status="skipped", message="Результат уже существует, не перезаписан")
                return result
            duration, audio_streams = probe_details(src)
            original_size = src.stat().st_size
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp = dest.parent / f".cryptarch-{uuid.uuid4().hex}.partial.mp4"
            command = [binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                       "-i", str(src), *audio_mapping(audio_streams), "-map_metadata", "0",
                       *encoder_args(self.codec, self.device, self.quality, encoder),
                       "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]
            if self.codec == "H.265":
                command += ["-tag:v", "hvc1"]
            command += ["-progress", "pipe:1", "-nostats", str(temp)]
            error_file = tempfile.TemporaryFile()
            with self.lock:
                if self.cancelled.is_set():
                    result.update(status="cancelled", message="Отменено")
                    return result
                proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_file,
                                        text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
                self.processes[proc.pid] = proc
                if not self.pause_gate.is_set():
                    try:
                        suspend_process(proc.pid, True)
                        self.paused_pids.add(proc.pid)
                    except OSError:
                        pass
            for line in proc.stdout:
                if line.startswith("out_time_us=") and duration > 0:
                    try:
                        with self.lock:
                            self.progress[str(src)] = min(float(line.split("=", 1)[1]) / 1_000_000 / duration, .99)
                        self.update(total)
                    except ValueError:
                        pass
                elif line.startswith("speed="):
                    try:
                        with self.lock:
                            self.speeds[str(src)] = float(line.split("=", 1)[1].strip().rstrip("x"))
                    except ValueError:
                        pass
            proc.stdout.close()
            code = proc.wait()
            error_file.seek(0)
            error_text = error_file.read().decode("utf-8", errors="replace").strip()[-700:]
            error_file.close()
            with self.lock:
                self.processes.pop(proc.pid, None)
                self.paused_pids.discard(proc.pid)
            if self.cancelled.is_set():
                result.update(status="cancelled", message="Отменено")
                return result
            if code != 0 or not temp.exists() or temp.stat().st_size == 0:
                raise RuntimeError(f"Ошибка FFmpeg (код {code}). {error_text}")
            # Windows rename refuses to overwrite an existing file.
            if dest.exists():
                result.update(status="skipped", message="Результат появился во время обработки; не перезаписан")
                return result
            os.rename(temp, dest)
            result.update(status="ok", original=original_size, compressed=dest.stat().st_size)
            return result
        except Exception as exc:
            result["message"] = str(exc)
            return result
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    if proc.pid in self.paused_pids:
                        suspend_process(proc.pid, False)
                    proc.terminate()
                    proc.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if proc is not None:
                with self.lock:
                    self.processes.pop(proc.pid, None)
                    self.paused_pids.discard(proc.pid)
            if error_file is not None and not error_file.closed:
                error_file.close()
            if temp is not None and temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass
            with self.lock:
                self.finished += 1
                self.progress[str(src)] = 1.0
                self.speeds.pop(str(src), None)
            self.update(total)
