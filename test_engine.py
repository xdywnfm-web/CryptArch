import tempfile
import unittest
from pathlib import Path
import math
import struct
import subprocess

import engine


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "source"
        self.src.mkdir()
        self.out = self.src / "compressed"

    def tearDown(self):
        self.tmp.cleanup()

    def make_video(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([engine.binary("ffmpeg"), "-v", "error", "-f", "lavfi",
                        "-i", "testsrc2=size=640x360:rate=10", "-t", "1", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(path)], check=True, creationflags=engine.NO_WINDOW)

    def run_job(self, source, device="CPU", codec="H.264"):
        events = []
        job = engine.Job(source, self.out, "Сбалансированное", codec, device, 2,
                         lambda kind, data: events.append((kind, data)))
        job.run()
        return events

    def test_collect_excludes_output_and_preserves_structure(self):
        (self.src / "A").mkdir()
        (self.src / "A" / "one.mkv").touch()
        (self.out / "A").mkdir(parents=True)
        (self.out / "A" / "old.mp4").touch()
        self.assertEqual(engine.collect(self.src, self.out),
                         [(self.src / "A" / "one.mkv", self.out / "A" / "one.mp4")])

    def test_end_to_end_and_existing_copy_is_not_overwritten(self):
        video = self.src / "one.mp4"
        self.make_video(video)
        original = video.read_bytes()
        events = self.run_job(self.src)
        result = events[-1][1]
        self.assertEqual(result["results"][0]["status"], "ok")
        result_file = self.out / "one.mp4"
        self.assertTrue(result_file.exists())
        compressed = result_file.read_bytes()
        self.assertEqual(video.read_bytes(), original)
        self.assertGreater(engine.probe(result_file), 0)
        again = self.run_job(self.src)[-1][1]["results"][0]
        self.assertEqual(again["status"], "skipped")
        self.assertEqual(result_file.read_bytes(), compressed)

    def test_colliding_extensions_are_rejected(self):
        (self.src / "same.mp4").touch()
        (self.src / "same.mkv").touch()
        events = self.run_job(self.src)
        self.assertEqual(events[-1][0], "fatal")

    def test_bad_video_is_reported(self):
        (self.src / "broken.mp4").write_bytes(b"bad")
        events = self.run_job(self.src)
        self.assertEqual(events[-1][1]["results"][0]["status"], "error")
        self.assertTrue((self.src / "broken.mp4").exists())

    def test_parallel_folder_preserves_categories(self):
        first = self.src / "Games" / "clip1.mp4"
        second = self.src / "Desktop" / "clip2.mp4"
        self.make_video(first)
        self.make_video(second)
        events = self.run_job(self.src, codec="H.265")
        report = events[-1][1]
        self.assertEqual(sum(r["status"] == "ok" for r in report["results"]), 2)
        self.assertTrue((self.out / "Games" / "clip1.mp4").exists())
        self.assertTrue((self.out / "Desktop" / "clip2.mp4").exists())
        self.assertTrue(first.exists() and second.exists())

    def test_multitrack_audio_is_mixed_regardless_of_labels(self):
        streams = [
            {"index": 1, "tags": {"title": "English"}, "disposition": {"default": 0}},
            {"index": 2, "tags": {"title": "Russian"}, "disposition": {"default": 1}},
        ]
        args = engine.audio_mapping(streams)
        self.assertIn("-filter_complex", args)
        self.assertIn("[0:1][0:2]amix=inputs=2", " ".join(args))
        self.assertEqual(args.count("-map"), 2)

    def test_single_or_absent_audio_does_not_require_mixing(self):
        self.assertNotIn("-filter_complex", engine.audio_mapping([]))
        self.assertNotIn("-filter_complex", engine.audio_mapping([{"index": 1}]))

    def test_discord_mix_contains_application_and_voice(self):
        video = self.src / "discord.mp4"
        subprocess.run([
            engine.binary("ffmpeg"), "-v", "error",
            "-f", "lavfi", "-i", "color=size=320x240:rate=10",
            "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000",
            "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=8000",
            "-t", "2", "-map", "0:v", "-map", "1:a", "-map", "2:a", "-map", "3:a",
            "-c:v", "libx264", "-c:a", "aac",
            "-metadata:s:a:0", "handler_name=0:all",
            "-metadata:s:a:1", "handler_name=0:application",
            "-metadata:s:a:2", "handler_name=123:voice",
            str(video)], check=True, creationflags=engine.NO_WINDOW)
        before = video.read_bytes()
        events = self.run_job(video)
        result = events[-1][1]["results"][0]
        self.assertEqual(result["status"], "ok", result)
        output = self.out / "discord.mp4"
        _, streams = engine.probe_details(output)
        self.assertEqual(len(streams), 1)
        self.assertEqual([s["disposition"]["default"] for s in streams], [1])
        raw = subprocess.run([
            engine.binary("ffmpeg"), "-v", "error", "-i", str(output),
            "-map", "0:a:0", "-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"
        ], capture_output=True, check=True, creationflags=engine.NO_WINDOW).stdout
        samples = struct.unpack(f"<{len(raw) // 4}f", raw)
        # Both independent synthetic tones must be present in the default track.
        for frequency in (440, 880):
            cosine = sum(x * math.cos(2 * math.pi * frequency * i / 8000) for i, x in enumerate(samples))
            sine = sum(x * math.sin(2 * math.pi * frequency * i / 8000) for i, x in enumerate(samples))
            magnitude = 2 * math.hypot(cosine, sine) / len(samples)
            self.assertGreater(magnitude, 0.02, f"{frequency} Hz missing from mix")
        self.assertEqual(video.read_bytes(), before)

    def test_gpu_real_when_available(self):
        try:
            engine.gpu_encoder("H.265")
        except RuntimeError:
            self.skipTest("GPU HEVC encoder unavailable")
        video = self.src / "gpu.mp4"
        self.make_video(video)
        result = self.run_job(video, "GPU", "H.265")[-1]
        self.assertEqual(result[0], "finished", result)
        self.assertEqual(result[1]["results"][0]["status"], "ok", result)


if __name__ == "__main__":
    unittest.main()
