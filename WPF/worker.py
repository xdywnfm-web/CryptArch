"""One compression job over UTF-8 JSON lines; the engine is shared with Tk."""
import json
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import Job


def main():
    sys.stdin.reconfigure(encoding="utf-8-sig")
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    settings = json.loads(sys.stdin.readline())
    lock = threading.Lock()

    def emit(kind, data):
        if kind == "started":
            data = list(job.progress)
        with lock:
            print(json.dumps({"kind": kind, "data": data}, ensure_ascii=False))

    job = Job(**settings, emit=emit)
    thread = threading.Thread(target=job.run)
    thread.start()
    try:
        for command in sys.stdin:
            if command.strip() == "cancel":
                job.cancel()
            elif command.strip() in ("pause", "resume"):
                job.set_pause(command.strip() == "pause")
    finally:
        if thread.is_alive():
            job.cancel()
        thread.join()


if __name__ == "__main__":
    main()
