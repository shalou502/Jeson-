bl_info = {
    "name": "Jeson联机渲染发送口",
    "author": "Jeson",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "属性 > 输出 > 联机发送",
    "description": "发送渲染队列或当前文件到联机服务器",
    "category": "Render",
}

import json
import os
import random
import shutil
import socket
import urllib.error
import urllib.request

import bpy

DEFAULT_SERVER = "http://192.168.30.212:8000"
DEFAULT_CACHE_DIR = r"\\wj114\01 完全共享\联机渲染\渲染缓存"
DEFAULT_OUTPUT_DIR = r"\\wj114\01 完全共享\联机渲染\渲染输出"


class JesonSendProps(bpy.types.PropertyGroup):
    server_url: bpy.props.StringProperty(name="服务器", default=DEFAULT_SERVER)
    cache_dir: bpy.props.StringProperty(name="缓存位置", default=DEFAULT_CACHE_DIR)
    temp_output_dir: bpy.props.StringProperty(name="临时渲染输出", default=DEFAULT_OUTPUT_DIR)
    target_output_dir: bpy.props.StringProperty(name="指定输出路径(可空)", default="")
    filename_template: bpy.props.StringProperty(name="命名模板", default="{scene}_{job_id}_####")


def _ensure_dir(path: str):
    if path:
        os.makedirs(path, exist_ok=True)


def _copy_to_cache(src_blend: str, cache_dir: str, task_name: str) -> str:
    _ensure_dir(cache_dir)
    dest = os.path.join(cache_dir, f"{task_name}.blend")
    shutil.copy2(src_blend, dest)
    return dest


def _post_job(server_url: str, payload: dict):
    req = urllib.request.Request(
        url=f"{server_url}/jobs",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15):
        return


class RENDER_OT_send_queue_to_network(bpy.types.Operator):
    bl_idname = "render.send_queue_to_network"
    bl_label = "发送渲染队列"

    def execute(self, context):
        props = context.scene.jeson_send_props
        queue = getattr(context.scene, "render_queue", None)
        if not queue or len(queue) == 0:
            self.report({"ERROR"}, "找不到 render_queue 或队列为空")
            return {"CANCELLED"}

        sent = 0
        for item in queue:
            src = getattr(item, "filepath", "")
            if not src or not os.path.exists(src):
                continue
            scene_name = getattr(item, "name", "scene")
            cached_blend = _copy_to_cache(src, props.cache_dir, scene_name)
            payload = {
                "blend_file": cached_blend,
                "frame_start": context.scene.frame_start,
                "frame_end": context.scene.frame_end,
                "output_dir": props.temp_output_dir,
                "copy_target_dir": props.target_output_dir.strip(),
                "filename_template": props.filename_template,
                "samples": context.scene.cycles.samples if hasattr(context.scene, "cycles") else 128,
                "scene_name": scene_name,
                "submitter_host": socket.gethostname(),
                "submitter_user": "",
                "submitter_id": socket.gethostname(),
            }
            try:
                _post_job(props.server_url.rstrip("/"), payload)
                sent += 1
            except urllib.error.URLError as exc:
                self.report({"ERROR"}, f"发送失败: {exc}")
                return {"CANCELLED"}

        self.report({"INFO"}, f"✅ 已发送队列任务 {sent} 个")
        return {"FINISHED"}


class RENDER_OT_send_current_to_network(bpy.types.Operator):
    bl_idname = "render.send_current_to_network"
    bl_label = "发送当前文件"

    def execute(self, context):
        props = context.scene.jeson_send_props
        src = bpy.data.filepath
        if not src or not os.path.exists(src):
            self.report({"ERROR"}, "请先保存当前 .blend")
            return {"CANCELLED"}

        base = bpy.path.display_name_from_filepath(src)
        rand5 = f"{random.randint(0, 99999):05d}"
        scene_name = f"{base}_{rand5}"
        cached_blend = _copy_to_cache(src, props.cache_dir, scene_name)

        payload = {
            "blend_file": cached_blend,
            "frame_start": context.scene.frame_start,
            "frame_end": context.scene.frame_end,
            "output_dir": props.temp_output_dir,
            "copy_target_dir": props.target_output_dir.strip(),
            "filename_template": props.filename_template,
            "samples": context.scene.cycles.samples if hasattr(context.scene, "cycles") else 128,
            "scene_name": scene_name,
            "submitter_host": socket.gethostname(),
            "submitter_user": "",
            "submitter_id": socket.gethostname(),
        }
        try:
            _post_job(props.server_url.rstrip("/"), payload)
        except urllib.error.URLError as exc:
            self.report({"ERROR"}, f"发送失败: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"✅ 已发送当前文件：{scene_name}")
        return {"FINISHED"}


class RENDER_OT_open_task_list(bpy.types.Operator):
    bl_idname = "render.open_task_list"
    bl_label = "查看任务列表"

    def execute(self, context):
        server = context.scene.jeson_send_props.server_url.strip().rstrip("/") or DEFAULT_SERVER
        bpy.ops.wm.url_open(url=f"{server}/dashboard")
        return {"FINISHED"}


class RENDER_PT_send_panel(bpy.types.Panel):
    bl_label = "联机发送"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "output"

    def draw(self, context):
        layout = self.layout
        p = context.scene.jeson_send_props
        layout.prop(p, "server_url")
        layout.prop(p, "cache_dir")
        layout.prop(p, "temp_output_dir")
        layout.prop(p, "target_output_dir")
        layout.prop(p, "filename_template")

        row = layout.row(align=True)
        row.operator("render.send_queue_to_network", icon="EXPORT")
        row.operator("render.send_current_to_network", icon="FILE_TICK")
        row.operator("render.open_task_list", icon="URL")


classes = (
    JesonSendProps,
    RENDER_OT_send_queue_to_network,
    RENDER_OT_send_current_to_network,
    RENDER_OT_open_task_list,
    RENDER_PT_send_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.jeson_send_props = bpy.props.PointerProperty(type=JesonSendProps)


def unregister():
    if hasattr(bpy.types.Scene, "jeson_send_props"):
        del bpy.types.Scene.jeson_send_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
