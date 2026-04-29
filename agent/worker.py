from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import time
from typing import Any

import requests


def get_gpu_usage_percent() -> float:
    cmd = ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"]
    try:
        output = subprocess.check_output(cmd, text=True).strip().splitlines()
    except Exception:
        return 0.0
    values = [float(x.strip()) for x in output if x.strip()]
    return max(values) if values else 0.0


def _popen_kwargs_for_hidden_blender() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def _prefix_from_pattern(output_pattern: str) -> str:
    return output_pattern.replace("####", "")


def _copy_rendered_files(output_pattern: str, copy_target_dir: str) -> tuple[bool, str]:
    if not copy_target_dir:
        return True, "no copy target"
    os.makedirs(copy_target_dir, exist_ok=True)
    prefix = _prefix_from_pattern(output_pattern)
    candidates = glob.glob(prefix + "*")
    if not candidates:
        return False, "no rendered files found for copy"
    for src in candidates:
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(copy_target_dir, os.path.basename(src)))
    return True, f"copied {len(candidates)} files"


def run_blender_render(blender_bin: str, job: dict[str, Any]) -> tuple[bool, str]:
    cmd = [
        blender_bin,
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
        subprocess.check_call(cmd, **_popen_kwargs_for_hidden_blender())
        ok, copy_msg = _copy_rendered_files(job["output_pattern"], job.get("copy_target_dir", ""))
        if not ok:
            return False, copy_msg
        return True, f"render success; {copy_msg}"
    except subprocess.CalledProcessError as exc:
        return False, f"blender exit code={exc.returncode}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--host", required=True, choices=["WK1021", "WK1042", "WK1043", "WJ410"])
    parser.add_argument("--blender-bin", default="blender")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()

    while True:
        gpu = get_gpu_usage_percent()
        if gpu > 70:
            time.sleep(args.interval)
            continue

        poll = requests.post(
            f"{args.server.rstrip('/')}/workers/poll",
            json={"host": args.host, "gpu_usage_percent": gpu},
            timeout=15,
        )
        poll.raise_for_status()
        job = poll.json().get("job")
        if not job:
            time.sleep(args.interval)
            continue

        ok, message = run_blender_render(args.blender_bin, job)
        result = requests.post(
            f"{args.server.rstrip('/')}/workers/{args.host}/jobs/{job['job_id']}/result",
            json={"status": "finished" if ok else "failed", "message": message},
            timeout=15,
        )
        result.raise_for_status()


if __name__ == "__main__":
    main()
