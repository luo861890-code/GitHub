# -*- coding: utf-8 -*-
"""会话服务测试：创建/重命名/删除。"""
import os

from app.services.session_service import SessionService


def test_session_rename(work_tmp_dir):
    ss = SessionService()
    ss.sessions_file = os.path.join(work_tmp_dir, "sessions.json")
    ss.sessions = {}
    s = ss.create_session("初始标题")
    renamed = ss.rename_session(s.session_id, "新标题")
    assert renamed is not None
    assert renamed.title == "新标题"
    assert ss.rename_session("no_such", "x") is None
    assert ss.delete_session(s.session_id) is True
