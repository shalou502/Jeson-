from __future__ import annotations

import json
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Deque
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    finished = "finished"
    failed = "failed"


class RenderHost(str, Enum):
    WK1021 = "WK1021"
    WK1042 = "WK1042"
    WK1043 = "WK1043"
    WJ410 = "WJ410"


class CreateJobRequest(BaseModel):
    blend_file: str
    frame_start: int
    frame_end: int
    output_dir: str = r"\\wj114\01 完全共享\联机渲染\渲染输出"
    copy_target_dir: str = ""
    filename_template: str = "{scene}_{job_id}_####"
    samples: int = 128
    scene_name: str = "scene"
    submitter_host: str = ""
    submitter_user: str = ""
    submitter_id: str = ""


class JobResultRequest(BaseModel):
    status: JobStatus
    message: str = ""


class PollJobRequest(BaseModel):
    host: RenderHost
    gpu_usage_percent: float = Field(ge=0, le=100)


@dataclass
class Job:
    id: str
    blend_file: str
    frame_start: int
    frame_end: int
    output_dir: str
    copy_target_dir: str
    filename_template: str
    samples: int
    scene_name: str
    submitter_host: str
    submitter_user: str
    submitter_id: str
    status: JobStatus = JobStatus.queued
    assigned_host: RenderHost | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""


class JobQueue:
    def __init__(self) -> None:
        self.lock = Lock()
        self.jobs: dict[str, Job] = {}
        self.pending: Deque[str] = deque()
        self.host_running: dict[RenderHost, str | None] = {h: None for h in RenderHost}
        self.host_last_seen: dict[RenderHost, datetime | None] = {h: None for h in RenderHost}
        self.host_last_gpu: dict[RenderHost, float | None] = {h: None for h in RenderHost}

    def create(self, req: CreateJobRequest) -> Job:
        job = Job(
            id=uuid4().hex,
            blend_file=req.blend_file,
            frame_start=req.frame_start,
            frame_end=req.frame_end,
            output_dir=req.output_dir.strip() or r"\\wj114\01 完全共享\联机渲染\渲染输出",
            copy_target_dir=req.copy_target_dir.strip(),
            filename_template=req.filename_template,
            samples=req.samples,
            scene_name=req.scene_name,
            submitter_host=req.submitter_host,
            submitter_user=req.submitter_user,
            submitter_id=req.submitter_id or req.submitter_host or "unknown",
        )
        with self.lock:
            self.jobs[job.id] = job
            self.pending.append(job.id)
        return job

    def poll_for_host(self, host: RenderHost, gpu_usage_percent: float) -> Job | None:
        now = datetime.now(timezone.utc)
        with self.lock:
            self.host_last_seen[host] = now
            self.host_last_gpu[host] = gpu_usage_percent
            if self.host_running[host] is not None or gpu_usage_percent > 70:
                return None
            while self.pending:
                job_id = self.pending.popleft()
                job = self.jobs[job_id]
                if job.status != JobStatus.queued:
                    continue
                job.status = JobStatus.running
                job.assigned_host = host
                job.updated_at = now
                self.host_running[host] = job.id
                return job
        return None

    def update_result(self, host: RenderHost, job_id: str, result: JobResultRequest) -> Job:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="job not found")
            if job.assigned_host != host:
                raise HTTPException(status_code=409, detail="job host mismatch")
            job.status = result.status
            job.message = result.message
            job.updated_at = datetime.now(timezone.utc)
            self.host_running[host] = None
            return job


queue = JobQueue()
app = FastAPI(title="Jeson Network Render Server")


def _load_path_rules() -> list[dict]:
    text = os.getenv("JESON_PATH_RULES", "[]")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


PATH_RULES = _load_path_rules()


def resolve_path_for_host(raw_path: str, host: RenderHost) -> str:
    path = raw_path.strip()
    if path.startswith("smb://") or path.startswith("\\\\"):
        return path
    for rule in PATH_RULES:
        source = str(rule.get("from", "")).strip()
        targets = rule.get("to", {})
        if source and path.startswith(source) and isinstance(targets, dict):
            mapped = targets.get(host.value)
            if mapped:
                return path.replace(source, mapped, 1)
    return path


def build_output_pattern(output_dir: str, filename_template: str, job_id: str, scene_name: str) -> str:
    basename = filename_template.replace("{job_id}", job_id).replace("{scene}", scene_name or "scene")
    if "####" not in basename:
        basename = f"{basename}_####"
    clean_dir = output_dir.rstrip("/\\")
    return f"{clean_dir}/{basename}"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs")
def create_job(req: CreateJobRequest) -> dict:
    job = queue.create(req)
    return {"job_id": job.id, "status": job.status}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = queue.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "assigned_host": job.assigned_host,
        "submitter_id": job.submitter_id,
        "copy_target_dir": job.copy_target_dir,
        "updated_at": job.updated_at.isoformat(),
    }


@app.post("/workers/poll")
def poll_job(req: PollJobRequest) -> dict:
    job = queue.poll_for_host(req.host, req.gpu_usage_percent)
    if not job:
        return {"job": None}
    blend_file = resolve_path_for_host(job.blend_file, req.host)
    output_dir = resolve_path_for_host(job.output_dir, req.host)
    copy_target = resolve_path_for_host(job.copy_target_dir, req.host) if job.copy_target_dir else ""
    return {
        "job": {
            "job_id": job.id,
            "blend_file": blend_file,
            "frame_start": job.frame_start,
            "frame_end": job.frame_end,
            "output_pattern": build_output_pattern(output_dir, job.filename_template, job.id, job.scene_name),
            "copy_target_dir": copy_target,
            "samples": job.samples,
            "scene_name": job.scene_name,
        }
    }


@app.post("/workers/{host}/jobs/{job_id}/result")
def job_result(host: RenderHost, job_id: str, req: JobResultRequest) -> dict:
    job = queue.update_result(host, job_id, req)
    return {"job_id": job.id, "status": job.status, "message": job.message}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    host_rows = "".join(
        f"<tr><td>{h.value}</td><td>{queue.host_running[h] or '-'}</td><td>{queue.host_last_gpu[h] if queue.host_last_gpu[h] is not None else '-'}</td><td>{queue.host_last_seen[h].isoformat() if queue.host_last_seen[h] else '-'}</td></tr>"
        for h in RenderHost
    )
    jobs = sorted(queue.jobs.values(), key=lambda j: j.created_at, reverse=True)[:200]
    job_rows = "".join(
        f"<tr><td>{j.id}</td><td>{j.scene_name}</td><td>{j.status}</td><td>{j.assigned_host or '-'}</td><td>{j.copy_target_dir or '-'}</td><td>{j.updated_at.isoformat()}</td></tr>"
        for j in jobs
    )
    return f"""
    <html><head><meta charset='utf-8'><title>Jeson任务看板</title>
    <style>body{{font-family:Arial;padding:20px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px}}</style>
    </head><body>
    <h2>Jeson 任务看板（192.168.30.212）</h2>
    <h3>渲染主机</h3>
    <table><tr><th>Host</th><th>当前任务</th><th>GPU%</th><th>最后心跳</th></tr>{host_rows}</table>
    <h3>任务列表</h3>
    <table><tr><th>Job ID</th><th>Scene</th><th>Status</th><th>Host</th><th>复制目标</th><th>更新时间</th></tr>{job_rows}</table>
    </body></html>
    """
