import tempfile
import threading
import time
import unittest
from pathlib import Path
import subprocess
from unittest.mock import patch

import engine
from app import CryptArch


class GuiTests(unittest.TestCase):
    def test_window_can_compress_and_show_report(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "clip.mp4"
            out = Path(temp) / "compressed"
            subprocess.run([engine.binary("ffmpeg"), "-v", "error", "-f", "lavfi",
                            "-i", "testsrc2=size=320x240:rate=10", "-t", "1",
                            "-c:v", "libx264", str(src)], check=True, creationflags=engine.NO_WINDOW)
            app = CryptArch()
            reports = []
            app.result_window = lambda title, text, warning=False: reports.append((title, text))
            app.source.set(str(src))
            app.output.set(str(out))
            app.codec.set("H.264")
            app.start()
            deadline = time.monotonic() + 40
            try:
                while app.running and time.monotonic() < deadline:
                    app.update()
                    time.sleep(.02)
                app.update()
                self.assertFalse(app.running, "GUI task did not finish")
                self.assertEqual(len(reports), 1)
                self.assertIn("1 из 1", reports[0][1])
                self.assertTrue((out / "clip.mp4").exists())
                self.assertTrue(src.exists())
            finally:
                if app.running:
                    app.job.cancel()
                app.destroy()

    def test_result_uses_native_dialog_and_preserves_all_warnings(self):
        app = CryptArch()
        results = [{"source": f"video_{i}.mp4", "status": "ok",
                    "original": 100, "compressed": 110} for i in range(15)]
        try:
            with patch("app.messagebox.showwarning") as warning, patch("app.messagebox.showinfo") as info:
                app.show_result({"results": results, "original": 1500, "compressed": 1650,
                                 "cancelled": False, "total": len(results)})
                self.assertGreater(warning.call_count, 1)
                info.assert_not_called()
                pages = "\n".join(call.args[1] for call in warning.call_args_list)
                for i in range(15):
                    self.assertIn(f"video_{i}.mp4", pages)
            with patch("app.messagebox.showwarning") as warning, patch("app.messagebox.showinfo") as info:
                app.show_result({"results": [], "original": 0, "compressed": 0,
                                 "cancelled": False, "total": 0})
                info.assert_called_once()
                warning.assert_not_called()
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
