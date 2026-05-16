from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import pystray
import requests
from PIL import Image, ImageDraw
from pystray import Menu, MenuItem


CONFIG_PATH = Path.home() / ".jeson_worker_config.json"
STARTUP_DIR = Path(os.getenv("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
STARTUP_BAT = STARTUP_DIR / "jeson_worker_tray_startup.bat"


@dataclass
class WorkerConfig:
    server: str = "http://192.168.30.212:8000"
    host: str = "WK1021"
    blender_bin: str = "blender"
    interval: int = 5
    autostart: bool = False


class TrayApp:
    def __init__(self) -> None:
        self.cfg = self._load_config()
        self.running = False
        self.worker_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.icon = pystray.Icon(
            "jeson-worker",
            self._icon_image(running=False),
            "Jeson 渲染节点",
            menu=self._build_menu(),
        )

    def _load_config(self) -> WorkerConfig:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return WorkerConfig(**{**asdict(WorkerConfig()), **data})
        cfg = WorkerConfig()
        CONFIG_PATH.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
        return cfg

    def _save_config(self) -> None:
        CONFIG_PATH.write_text(json.dumps(asdict(self.cfg), ensure_ascii=False, indent=2), encoding="utf-8")

    def _icon_image(self, running: bool) -> Image.Image:
        img = Image.new("RGB", (64, 64), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        color = (0, 200, 0) if running else (200, 60, 60)
        draw.ellipse((14, 14, 50, 50), fill=color)
        return img

    def _build_menu(self) -> Menu:
        return Menu(
            MenuItem(lambda _: f"Host: {self.cfg.host}", lambda *_: None, enabled=False),
            MenuItem(lambda _: f"Server: {self.cfg.server}", lambda *_: None, enabled=False),
            MenuItem("启动渲染节点", self.start_worker),
            MenuItem("停止渲染节点", self.stop_worker),
            MenuItem("开机自启", self.toggle_autostart, checked=lambda _: self.cfg.autostart),
            MenuItem("打开配置文件", self.open_config_file),
            MenuItem("退出", self.exit_app),
        )

    def _popen_kwargs_for_hidden_blender(self) -> dict:
        if os.name == "nt":
            return {"creationflags": subprocess.CREATE_NO_WINDOW}
        return {}

    def _get_gpu_usage_percent(self) -> float:
        cmd = ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"]
        try:
            output = subprocess.check_output(cmd, text=True).strip().splitlines()
        except Exception:
            return 0.0
        vals = [float(x.strip()) for x in output if x.strip()]
        return max(vals) if vals else 0.0

    def _copy_rendered_files(self, output_pattern: str, copy_target_dir: str) -> tuple[bool, str]:
        if not copy_target_dir:
            return True, "no copy target"
        os.makedirs(copy_target_dir, exist_ok=True)
        prefix = output_pattern.replace("####", "")
        files = glob.glob(prefix + "*")
        if not files:
            return False, "no rendered files found for copy"
        for src in files:
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(copy_target_dir, os.path.basename(src)))
        return True, f"copied {len(files)} files"

    def _run_blender_render(self, job: dict) -> tuple[bool, str]:
        cmd = [
            self.cfg.blender_bin,
            "-b",
            job["blend_file"],
            "--factory-startup",
            "-noaudio",
            "-s",
            str(job["frame_start"]),
            "-e",
            str(job["frame_end"]),
            "-o",
            job["output_pattern"],
            "-a",
        ]
        try:
            subprocess.check_call(cmd, **self._popen_kwargs_for_hidden_blender())
            ok, copy_msg = self._copy_rendered_files(job["output_pattern"], job.get("copy_target_dir", ""))
            return (ok, f"render success; {copy_msg}" if ok else copy_msg)
        except subprocess.CalledProcessError as exc:
            return False, f"blender exit code={exc.returncode}"

    def _worker_loop(self) -> None:
        while not self.stop_event.is_set():
            gpu = self._get_gpu_usage_percent()
            if gpu > 70:
                self.stop_event.wait(self.cfg.interval)
                continue
            try:
                poll = requests.post(
                    f"{self.cfg.server.rstrip('/')}/workers/poll",
                    json={"host": self.cfg.host, "gpu_usage_percent": gpu},
                    timeout=15,
                )
                poll.raise_for_status()
                job = poll.json().get("job")
                if not job:
                    self.stop_event.wait(self.cfg.interval)
                    continue

                ok, msg = self._run_blender_render(job)
                result = requests.post(
                    f"{self.cfg.server.rstrip('/')}/workers/{self.cfg.host}/jobs/{job['job_id']}/result",
                    json={"status": "finished" if ok else "failed", "message": msg},
                    timeout=15,
                )
                result.raise_for_status()
            except Exception:
                self.stop_event.wait(self.cfg.interval)

    def start_worker(self, icon=None, item=None) -> None:
        del icon, item
        if self.running:
            return
        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        self.running = True
        self.icon.icon = self._icon_image(running=True)
        self.icon.title = f"Jeson 渲染节点（运行中）- {self.cfg.host}"

    def stop_worker(self, icon=None, item=None) -> None:
        del icon, item
        if not self.running:
            return
        self.stop_event.set()
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        self.worker_thread = None
        self.running = False
        self.icon.icon = self._icon_image(running=False)
        self.icon.title = f"Jeson 渲染节点（已停止）- {self.cfg.host}"

    def toggle_autostart(self, icon=None, item=None) -> None:
        del icon, item
        self.cfg.autostart = not self.cfg.autostart
        if self.cfg.autostart:
            STARTUP_DIR.mkdir(parents=True, exist_ok=True)
            startup_cmd = f'@echo off\ncd /d "{Path.cwd()}"\n"{sys.executable}" "agent/tray_worker.py"\n'
            STARTUP_BAT.write_text(startup_cmd, encoding="utf-8")
        else:
            if STARTUP_BAT.exists():
                STARTUP_BAT.unlink()
        self._save_config()

    def open_config_file(self, icon=None, item=None) -> None:
        del icon, item
        self._save_config()
        if os.name == "nt":
            os.startfile(str(CONFIG_PATH))

    def exit_app(self, icon=None, item=None) -> None:
        del item
        self.stop_worker()
        icon.stop()

    def run(self) -> None:
        self.start_worker()
        self.icon.run()


if __name__ == "__main__":
    TrayApp().run()
