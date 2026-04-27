import requests
import sys

def create_default_user(username, password):
    url = "http://localhost:8000/api/auth/register"
    data = {
        "username": username,
        "password": password
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print(f"成功创建用户: {username}")
        else:
            print(f"创建失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"连接失败，请确保后端服务已启动 (uvicorn app.main:app --reload)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python create_user.py <用户名> <密码>")
    else:
        create_default_user(sys.argv[1], sys.argv[2])
