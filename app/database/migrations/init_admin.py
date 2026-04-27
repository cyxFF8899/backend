from __future__ import annotations
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from backend.app.db import DB
from backend.app.config import Settings
from backend.app.models import User
from backend.app.auth import get_password_hash
from sqlalchemy import select

def create_admin(username, password):
    settings = Settings.from_env()
    db = DB(settings)
    
    with db.session() as session:
        user = session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        
        if user:
            print(f"用户 {username} 已存在，正在更新为管理员并重置密码...")
            user.is_admin = True
            user.hashed_password = get_password_hash(password)
        else:
            print(f"正在创建新的管理员用户: {username}...")
            new_user = User(
                username=username,
                email=f"{username}@example.com",
                hashed_password=get_password_hash(password),
                is_active=True,
                is_admin=True
            )
            session.add(new_user)
        
        session.commit()
        print(f"成功！管理员账号: {username}, 密码: {password}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        create_admin("admin", "admin123")
    else:
        create_admin(sys.argv[1], sys.argv[2])
