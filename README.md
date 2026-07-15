# Agent Approval Dashboard

A full-stack approval dashboard for managing AI agent approval requests with Jira integration and an AI-powered chat assistant. Built with **FastAPI** (backend), **React + Vite** (frontend), **PostgreSQL** (database), and **Agno AgentOS** (AI agent).

---

## 🏗 Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React + Vite  │────▶│    FastAPI      │────▶│   PostgreSQL    │
│   (Frontend)    │     │    (Backend)    │     │   (Database)    │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │  Jira    │ │  Agno    │ │  MCP     │
              │  Cloud   │ │  AgentOS │ │  Atlassian│
              └──────────┘ └──────────┘ └──────────┘
```

---

## ✨ Features

### 🎯 Approval Dashboard
- **Tabbed interface**: Pending / Approved / Blocked / All requests
- **Real-time polling** (15s interval) for new approval requests
- **Expandable request cards** showing:
  - Tool name & description
  - Agent ID & run ID
  - Full JSON arguments
  - Context/reasoning
  - Requester info
- **One-click Approve/Block** actions with optimistic UI updates
- **Jira-backed approvals** — decisions sync via Jira Automation webhook

### 🤖 AI Chat Assistant (Approvals Assistant)
- Embedded chat widget in the dashboard
- Powered by **Agno AgentOS** with **NVIDIA Nemotron-3-Super-120B** model
- **MCP (Model Context Protocol)** tools for Jira/Confluence integration
- Natural language queries: *"Show pending approvals"*, *"Approve SCRUM-42"*
- Conversation history maintained per session

### 🔗 Jira Integration
- **Bidirectional sync**: Dashboard ↔ Jira issues
- **Webhook receiver** for Jira Automation rule callbacks
- **Custom fields** for approval tracking:
  - `approval_id` — links Jira issue to Agno approval row
  - `tool_name` — which agent tool requested approval
  - `agent_id` — originating agent identifier
  - `approval_type` — `audit` (post-hoc) or `required` (gate)
- **JQL-powered listing** with status filtering
- **Workflow transitions** via REST API (Approve/Reject)

### 🔐 Authentication
- JWT-based auth with HttpOnly-compatible localStorage storage
- Admin users stored in PostgreSQL (`admins` table)
- Password hashing via `bcrypt`
- Token expiry: 7 days

### 🗄 Database Schema (PostgreSQL)
```
ai.agno_approvals          # Core approval requests (from Agno)
ai.tool_descriptions       # Human-readable tool descriptions (LEFT JOINed)
admins                     # Dashboard admin users
```

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **npm**
- **PostgreSQL 14+** (with `uuid-ossp` extension)
- **Jira Cloud** instance with API token
- **NVIDIA API Key** (for Nemotron model)
- **uv** (recommended) or `pip` for Python deps

### 1. Clone & Configure

```bash
git clone <your-repo>
cd dashboard
```

#### Backend Environment (`.env` in `backend/`)
```bash
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/approval_db

# JWT
JWT_SECRET=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080  # 7 days

# Jira Cloud
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@domain.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_PROJECT_KEY=APR
JIRA_ISSUE_TYPE=Task

# Jira Custom Field IDs (find via GET /rest/api/3/field)
JIRA_FIELD_APPROVAL_ID=customfield_10050
JIRA_FIELD_TOOL_NAME=customfield_10051
JIRA_FIELD_AGENT_ID=customfield_10052
JIRA_FIELD_APPROVAL_TYPE=customfield_10053

# Jira Webhook Secret (must match Automation rule header)
JIRA_WEBHOOK_SECRET=your-webhook-secret

# Agno AgentOS
AGNO_AGENT_URL=http://localhost:7777

# NVIDIA Nemotron
NVIDIA_API_KEY=your-nvidia-api-key
```

#### Frontend Environment (`.env` in `frontend/`)
```bash
VITE_API_BASE=http://localhost:8000
```

### 2. Database Setup

```bash
# Create database & enable uuid-ossp
psql -U postgres -c "CREATE DATABASE approval_db;"
psql -U postgres -d approval_db -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"

# Run migrations (creates tables in ai schema)
psql -U postgres -d approval_db -f backend/database/schema.sql
```

> **Note**: The schema creates tables in the `ai` schema. Ensure your `DATABASE_URL` user has `CREATE SCHEMA` privileges or pre-create the schema.

### 3. Create Admin User

```bash
cd backend
python -c "
from auth import hash_password
from database import init_pool, get_pool
import asyncio

async def create_admin():
    await init_pool()
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO admins (email, password_hash) VALUES (\$1, \$2) ON CONFLICT DO NOTHING',
            'admin@example.com', hash_password('your-secure-password')
        )
    await pool.close()

asyncio.run(create_admin())
"
```

### 4. Install & Run

#### Backend (Terminal 1)
```bash
cd backend
uv sync  # or: pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

#### Agno Agent Server (Terminal 2)
```bash
cd backend
uv sync  # ensures agno, mcp-atlassian, etc.
uvicorn jira_agent:app --reload --port 7777
```

#### Frontend (Terminal 3)
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** → Login with admin credentials → Dashboard loads.

---

## 🔧 Jira Automation Setup

The dashboard uses **Jira as the source of truth** for approval decisions. Configure a Jira Automation rule:

### 1. Create Custom Fields (Jira Settings → Issues → Custom Fields)
| Field Name | Type | Key (example) |
|------------|------|---------------|
| Approval ID | Text (single line) | `customfield_10050` |
| Tool Name | Text (single line) | `customfield_10051` |
| Agent ID | Text (single line) | `customfield_10052` |
| Approval Type | Select List (single) | `customfield_10053` |
| *Options*: `audit`, `required` | | |

### 2. Create Automation Rule
**Project Settings → Automation → Create Rule**

- **Trigger**: *Issue transitioned* → **To status**: `Approved`, `Rejected`
- **Condition**: *Issue fields condition* → Issue Type = `Task` (or your approval issue type)
- **Action**: *Send web request*
  - **URL**: `https://your-backend/webhooks/jira-approval`
  - **Method**: `POST`
  - **Headers**: `X-Webhook-Secret: your-webhook-secret`
  - **Body** (JSON):
    ```json
    {
      "issue_key": "{{issue.key}}",
      "approval_id": "{{issue.customfield_10050}}",
      "status": "{{issue.status.name}}",
      "resolved_by": "{{issue.assignee.displayName}}"
    }
    ```

### 3. Workflow Setup
Ensure your Jira workflow has:
- Statuses: `Pending` (initial), `Approved`, `Rejected`
- Transitions: `Pending → Approved`, `Pending → Rejected`

---

## 📁 Project Structure

```
dashboard/
├── backend/
│   ├── main.py                 # FastAPI app, auth, approval CRUD
│   ├── jira_agent.py           # Agno AgentOS + MCP tools server (port 7777)
│   ├── jira_client.py          # Jira Cloud REST API client
│   ├── jira_webhook.py         # Jira Automation webhook receiver
│   ├── jira_dashboard.py       # Jira-backed dashboard endpoints
│   ├── chatbot.py              # Chat widget → Agno agent proxy
│   ├── approval_listener.py    # Postgres LISTEN/NOTIFY for real-time updates
│   ├── database.py             # AsyncPG connection pool
│   ├── auth.py                 # JWT + bcrypt
│   ├── models.py               # Pydantic models
│   ├── sync_tool_descriptions.py  # Populates ai.tool_descriptions
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Root: auth gate + Dashboard
│   │   ├── api.js              # Authenticated fetch wrapper
│   │   ├── components/
│   │   │   ├── Dashboard.jsx   # Tabbed list + chat toggle
│   │   │   ├── RequestCard.jsx # Expandable approval card
│   │   │   ├── ChatWidget.jsx  # AI chat interface
│   │   │   └── Login.jsx       # Login form
│   │   └── styles.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## 🔌 API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Login → returns JWT |

### Approvals (Jira-backed)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/jira/approvals?status=pending` | List approvals (pending/approved/rejected/all) |
| `GET` | `/api/jira/approvals/{issue_key}` | Get single approval detail |
| `POST` | `/api/jira/approvals/{issue_key}/resolve` | Approve/Reject via Jira transition |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Send message to Agno agent |

### Webhooks
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/webhooks/jira-approval` | Jira Automation callback |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |

---

## 🛠 Development

### Running Tests
```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

### Database Migrations
```bash
# Apply new schema changes
psql -U postgres -d approval_db -f backend/database/schema.sql
```

### Sync Tool Descriptions
```bash
cd backend
python sync_tool_descriptions.py
```
Populates `ai.tool_descriptions` from your Agno agent's tool registry.

---

## 🐳 Docker Deployment (Optional)

```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: approval_db
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backend/database/schema.sql:/docker-entrypoint-initdb.d/schema.sql

  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: ./backend/.env
    depends_on: [postgres]

  agent:
    build: ./backend
    command: uvicorn jira_agent:app --host 0.0.0.0 --port 7777
    ports: ["7777:7777"]
    env_file: ./backend/.env
    depends_on: [postgres]

  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    env_file: ./frontend/.env
    depends_on: [backend]

volumes:
  pgdata:
```

---

## 🔒 Security Checklist (Production)

- [ ] Change `JWT_SECRET` to a strong random string
- [ ] Set `CORS_ORIGINS` to your frontend domain only
- [ ] Use HTTPS for all endpoints
- [ ] Store secrets in a vault (AWS Secrets Manager, HashiCorp Vault, etc.)
- [ ] Enable PostgreSQL SSL (`sslmode=require` in `DATABASE_URL`)
- [ ] Rotate Jira API tokens periodically
- [ ] Set up rate limiting on `/api/auth/login`
- [ ] Enable audit logging for approval decisions

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| `uvicorn: command not found` | `uv sync` or `pip install uvicorn` |
| `asyncpg.exceptions.InvalidCatalogNameError` | Create database first: `createdb approval_db` |
| `JWT_SECRET not set` | Add to `.env` file |
| `Cannot connect to Agno agent` | Ensure `uvicorn jira_agent:app --port 7777` is running |
| `Jira webhook 401` | Verify `JIRA_WEBHOOK_SECRET` matches Automation rule header |
| `Custom field not found` | Check field IDs via `GET /rest/api/3/field` in Jira |
| `CORS error` | Set `allow_origins` in `main.py` to your frontend URL |

---

## 📚 Key Dependencies

### Backend
- **FastAPI** — Web framework
- **asyncpg** — Async PostgreSQL driver
- **python-jose** — JWT handling
- **passlib[bcrypt]** — Password hashing
- **httpx** — Async HTTP client
- **Agno** — AgentOS framework
- **MCPTools** — Model Context Protocol for Atlassian
- **NVIDIA Nemotron** — LLM via NVIDIA API

### Frontend
- **React 18** + **Vite**
- **Vanilla CSS** (no framework)
- **Fetch API** (native)

---

## 📄 License

MIT License — feel free to use and modify for your team.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Run tests & lint
5. Submit a PR

---

*Built with ❤️ for AI agent governance*
