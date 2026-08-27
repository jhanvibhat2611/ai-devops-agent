# 🤖 AI DevOps Agent

> **Built during my AI/Software Engineering Internship at Enfec Technologies.**

An AI-powered DevOps agent that transforms natural language software requirements into tested code and GitLab Merge Requests through a human-in-the-loop workflow.

Built using **FastAPI, LangGraph, Qwen, Elasticsearch, GitLab API, JWT Authentication, and Flet**.

---

## 🚀 What it does

The user gives the agent a requirement such as:

> Create a Python function that checks whether a number is prime.

The agent then:

1. 🔍 Searches Elasticsearch for relevant Merge Request context
2. 🧠 Analyzes the requirement using an LLM
3. 🌿 Generates a branch name, commit message, and Merge Request title
4. 💻 Generates the implementation
5. 🧪 Generates and executes unit tests using `pytest`
6. 👤 Pauses for human approval
7. 🚀 Creates a Git branch and commits the generated code
8. 📤 Pushes the changes to GitLab
9. 🔀 Creates a Merge Request

The project also supports **AI-powered Merge Request reviews and code suggestions**.

---

## 🔄 Agent Workflow

```text
                         ┌──────────────────────┐
                         │   User Requirement   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │ Search Similar Merge Requests │
                    │       (Elasticsearch)         │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    Analyze Requirement       │
                    │        using Qwen            │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        Generate Code         │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     Generate Unit Tests      │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │       Execute pytest         │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                         ┌──────────────────┐
                         │ Human Approval?  │
                         └────────┬─────────┘
                                  │
                     ┌────────────┴────────────┐
                     │                         │
                     ▼                         ▼
                ❌ Reject                  ✅ Approve
                     │                         │
                     ▼                         ▼
                    End                 Create Branch
                                              │
                                              ▼
                                         Commit Code
                                              │
                                              ▼
                                         Push to GitLab
                                              │
                                              ▼
                                      Create Merge Request
```

---

## ✨ Key Features

### 🧠 AI Requirement Analysis
Converts natural language requirements into structured development tasks, including:

- Requirement analysis
- Branch name generation
- Commit message generation
- Merge Request title generation

### 🔎 Context Retrieval with Elasticsearch
Stores and searches Merge Request metadata to retrieve relevant context before generating a solution.

### 💻 AI Code Generation
Generates implementation code based on the user's requirement and retrieved context.

### 🧪 Automated Unit Testing
Generates unit tests and executes them using `pytest` before proceeding with the workflow.

### 👤 Human-in-the-Loop Workflow
Uses **LangGraph interrupts and resume functionality** to pause the workflow and require explicit user approval before repository changes are made.

### 🌿 Git & GitLab Automation
After approval, the agent can automatically:

- Create a branch
- Write generated code
- Commit changes
- Push to GitLab
- Create a Merge Request

### 🔐 JWT Authentication
Implements JWT-based authentication and protects sensitive workflow actions.

### 🔍 AI Merge Request Review
Analyzes Merge Request diffs and generates AI-powered code review feedback.

### 💡 AI Code Suggestions
Generates improvement suggestions for Merge Request code and supports accepting AI-generated suggestions.

---

## 🏗️ Architecture

```text
┌──────────────┐
│    Flet UI   │
└──────┬───────┘
       │ HTTP + JWT
       ▼
┌──────────────────────┐
│   FastAPI Backend    │
└──────────┬───────────┘
           │
    ┌──────┼───────────────┐
    │      │               │
    ▼      ▼               ▼
┌────────┐ ┌─────────────┐ ┌──────────────┐
│LangGraph│ │Elasticsearch│ │  GitLab API  │
│Workflow │ │   Context   │ │ Repository   │
└────┬────┘ └─────────────┘ └──────────────┘
     │
     ▼
┌──────────────┐
│   Qwen LLM   │
│              │
│ • Analysis   │
│ • Code       │
│ • Tests      │
│ • Review     │
└──────────────┘
```

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| Backend | Python, FastAPI |
| AI / Agent Workflow | Qwen, LangGraph |
| Search & Context | Elasticsearch |
| Authentication | JWT |
| Testing | Pytest |
| Git Integration | Git, GitLab API |
| Frontend | Flet |

---

## 📂 Project Structure

```text
ai-devops-agent/
│
├── backend/
│   ├── main.py
│   ├── workflow/
│   │   ├── graph.py
│   │   └── nodes.py
│   ├── storage/
│   │   ├── auth.py
│   │   └── database.py
│   ├── elasticsearch_client.py
│   └── ai_review.py
│
├── frontend/
│   ├── main.py
│   ├── api.py
│   └── views/
│
└── README.md
```

---

## ⚙️ Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/ai-devops-agent.git
cd ai-devops-agent
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

**Windows**

```bash
venv\Scripts\activate
```

**Linux/macOS**

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file and configure the required credentials:

```env
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24

GITLAB_TOKEN=your_gitlab_token
PROJECT_ID=your_gitlab_project_id
```

Also configure the required LLM and Elasticsearch settings.

> **Never commit `.env` files, API keys, JWT secrets, or GitLab tokens to GitHub.**

### 5. Start the backend

```bash
cd backend
uvicorn main:app --reload
```

### 6. Start the frontend

```bash
cd frontend
python main.py
```

---

## 🎯 Project Motivation

This project explores how AI agents can automate repetitive parts of the software development lifecycle while keeping developers in control.

The core workflow follows a **human-in-the-loop approach**:

```text
AI analyzes → AI generates → AI tests → Human approves → Automation executes
```

---

## 🚧 Future Improvements

- User-specific GitLab authentication
- Multi-repository support and repository selection
- OAuth-based GitLab integration
- Improved validation and correction of AI-generated tests
- Dockerization
- CI/CD pipeline
- Background job processing

---

## 👩‍💻 Author

**Jhanvi Bhat**

