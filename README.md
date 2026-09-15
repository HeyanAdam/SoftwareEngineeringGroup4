\# 考研 AI 导学平台



面向考研学生的 AI 陪伴式导学平台。



\## 技术栈



\- 前端：Vue3 + Element Plus + ECharts + Pinia

\- 后端：Python + FastAPI

\- 数据库：MySQL + Redis + MinIO

\- 实时通信：WebSocket

\- 部署：Docker Compose



\## 目录结构



kaoyan-ai-platform/

├── kaoyan-frontend/    前端项目

├── kaoyan-backend/     后端项目

├── README.md

└── .gitignore



\## 团队成员



\- 前端组：

\- 后端组：

\- AI 组：



\## 本地开发



\### 前端



cd kaoyan-frontend

npm install

npm run dev



访问 http://localhost:5173



\### 后端



cd kaoyan-backend



激活虚拟环境（Windows）：

venv\\Scripts\\activate



安装依赖：

pip install -r requirements.txt



启动：

uvicorn app.main:app --reload --port 8001



访问 http://127.0.0.1:8001/docs 查看接口文档



\## 环境变量



后端配置见 kaoyan-backend/.env.example，复制为 .env 并填入真实配置。



\## AI 核心



\- RAG 检索增强生成

\- 用户画像

\- 个性化学习规划

\- 推荐评分

\- 多模态问答

