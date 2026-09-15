\# 考研 AI 导学平台



面向考研学生的 AI 陪伴式导学平台。



\## 项目简介



\- \*\*项目定位\*\*：面向考研学生的 AI 陪伴式导学平台

\- \*\*核心功能\*\*：RAG 问答、用户画像、个性化规划、推荐评分、多模态问答

\- \*\*实施原则\*\*：模块化单体，先完成学习闭环，再扩展语音与数字人



\## 技术栈



| 层级 | 技术 |

| --- | --- |

| 前端 | Vue3 + Element Plus + ECharts + Pinia |

| 后端 | Python + FastAPI |

| 数据库 | MySQL + Redis + MinIO |

| 实时通信 | WebSocket |

| 部署 | Docker Compose |



\## 目录结构

kaoyan-ai-platform/

├── kaoyan-frontend/ 前端项目

├── kaoyan-backend/ 后端项目

├── docker-compose.yml 数据库一键启动

├── README.md 本文件

└── .gitignore



\## 环境准备



第一次使用，需要安装以下 4 个工具：



| 工具 | 版本要求 | 下载地址 |

| --- | --- | --- |

| Node.js | 18+ | https://nodejs.org |

| Python | 3.11+ | https://www.python.org |

| Git | 任意 | https://git-scm.com |

| Docker Desktop | 最新版 | https://www.docker.com/products/docker-desktop/ |



> \*\*Windows 用户注意\*\*

> - 安装 Python 时，必须勾选 "Add Python to PATH"

> - 安装 Docker Desktop 时，需要先装 WSL2（Windows 会自动提示）



\## 快速开始



\### 1. 克隆仓库



```bash

git clone https://github.com/HeyanAdam/SoftwareEngineeringGroup4.git

cd SoftwareEngineeringGroup4



2\. 启动数据库（MySQL + Redis + MinIO）

bash

docker compose up -d

验证：



bash

docker ps

应该看到 3 个容器在运行：kaoyan-mysql、kaoyan-redis、kaoyan-minio。



3\. 启动后端

bash

cd kaoyan-backend



\# 创建虚拟环境

python -m venv venv



\# 激活虚拟环境（Windows）

venv\\Scripts\\activate



\# 安装依赖

pip install -r requirements.txt



\# 复制配置文件

copy .env.example .env



\# 启动

uvicorn app.main:app --reload --port 8001

验证：打开浏览器访问 http://127.0.0.1:8001/docs ，能看到接口文档。



4\. 启动前端

新开一个终端：



bash

cd kaoyan-frontend

npm install

npm run dev

验证：打开浏览器访问 http://localhost:5173 。



常用命令速查

操作	命令

启动数据库	docker compose up -d

停止数据库	docker compose down

查看数据库状态	docker ps

启动后端	cd kaoyan-backend → venv\\Scripts\\activate → uvicorn app.main:app --reload --port 8001

启动前端	cd kaoyan-frontend → npm run dev

接口地址

地址	说明

http://127.0.0.1:8001/	后端根接口

http://127.0.0.1:8001/docs	Swagger 接口文档

http://127.0.0.1:8001/api/db-check	数据库连接测试

http://127.0.0.1:8001/api/user/ping	用户模块测试

http://127.0.0.1:8001/api/ai/ping	AI 对话模块测试

http://127.0.0.1:8001/api/plan/ping	学习规划模块测试

http://localhost:5173	前端页面

数据库说明

服务	端口	用途

MySQL	3307	用户数据、对话记录、学习计划

Redis	6379	缓存、会话状态、用户画像

MinIO	9000（API）/ 9001（控制台）	多模态文件

MySQL 默认账号



用户：root



密码：kaoyan123



数据库：kaoyan



MinIO 默认账号



用户：minioadmin



密码：minioadmin



团队成员

前端组：



后端组：



AI 组：



常见问题

Q：docker compose up -d 卡住不动？



A：国内网络问题，需要在 Docker Desktop 的 Settings → Docker Engine 里配置镜像加速器。



Q：uvicorn 不是内部或外部命令？



A：虚拟环境没激活，执行 venv\\Scripts\\activate。



Q：后端启动报错连不上 MySQL？



A：检查 .env 里的 DB\_PORT 是否和 docker-compose.yml 里的端口一致（默认 3307）。



Q：端口被占用？



A：修改 docker-compose.yml 里对应的端口号，或停掉占用端口的程序。



text



\---



\## 操作步骤



\*\*第 1 步：进入 Monorepo 根目录\*\*

cd Desktop\\kaoyan-ai-platform



text



\*\*第 2 步：打开 README.md\*\*

notepad README.md



text



\*\*第 3 步：在记事本里按 `Ctrl + A` 全选，按 `Delete` 删除全部内容\*\*



\*\*第 4 步：把上面那一整块（从 `# 考研 AI 导学平台` 到最后）完整复制粘贴进去\*\*



\*\*第 5 步：按 `Ctrl + S` 保存，关闭记事本\*\*



\*\*第 6 步：回到终端执行 `dir` 确认 `README.md` 大小变大了\*\*



\*\*把 `dir` 的结果截图发我。\*\* 然后我们继续写后端的 README。





