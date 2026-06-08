"""DEV 播种辅助函数。

seed_dev_scene 是单一事实源，供 build_app 启动播种和 /debug/reset-db 端点复用。
"""
from __future__ import annotations

from backend.db.dal import DAL


def seed_dev_scene(dal: DAL) -> int:
    """创建并激活一个空的场次「1」，附带 slugline（室外/日/街道），返回 scene_id。

    场次编号默认走纯数字（1、2、3…），新建场次由用户自行填数字。

    无条件创建新场次（不做幂等检查），调用方负责「是否需要播种」的 guard。
    """
    seed_id = dal.create_scene("1")
    dal.set_active_scene(seed_id)
    dal.update_scene_heading(seed_id, int_ext="室外", time_of_day="日", location="街道")
    return seed_id
