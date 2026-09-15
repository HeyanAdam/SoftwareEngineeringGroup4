\# 考研 AI 导学平台 - 后端



基于 FastAPI 的后端服务。



\## 技术栈



\- Python 3.11+

\- FastAPI

\- SQLAlchemy

\- MySQL + Redis + MinIO



\## 目录结构

kaoyan-backend/

├── app/

│ ├── main.py 入口，注册路由

│ ├── core/

│ │ ├── config.py 读取 .env

│ │ └── database.py 数据库连接

│ └── modules/

│ ├── user/ 用户模块

│ ├── ai\_chat/ AI 对话模块

│ └── study\_plan/ 学习规划模块

├── requirements.txt

├── .env.example

└── .gitignore



text



\## 启动方式



```bash

\# 1. 创建虚拟环境

python -m venv venv



\# 2. 激活虚拟环境（Windows）

venv\\Scripts\\activate



\# 3. 安装依赖

pip install -r requirements.txt



\# 4. 复制配置文件

copy .env.example .env



\# 5. 启动

uvicorn app.main:app --reload --port 8001

依赖的数据库服务

后端需要以下服务先启动（在项目根目录执行）：



bash

docker compose up -d

MySQL（端口 3307）



Redis（端口 6379）



MinIO（端口 9000 / 9001）



接口文档

启动后访问：



Swagger UI：http://127.0.0.1:8001/docs



ReDoc：http://127.0.0.1:8001/redoc



模块说明

模块	路径	说明

用户模块	/api/user/\*	注册、登录、用户信息

AI 对话	/api/ai/\*	RAG 问答、对话记录

学习规划	/api/plan/\*	学习计划、进度追踪

添加新模块的步骤

在 app/modules/ 下新建文件夹，比如 new\_module/



创建 \_\_init\_\_.py 和 router.py



在 router.py 里写接口



在 app/main.py 里注册路由



常见问题

Q：uvicorn 不是内部或外部命令？



A：虚拟环境没激活，执行 venv\\Scripts\\activate。



Q：连不上 MySQL？



A：检查 .env 里的 DB\_PORT 是否为 3307，以及 Docker 容器是否运行。

