# 🤖 AI DevOps Agent

An AI-powered DevOps assistant that automates the journey from a natural-language development request to a GitLab Merge Request.

Built as an **Internship Project at Enfec Technologies**, the application combines LLM-powered agents, LangGraph workflows, GitLab integration, Elasticsearch, automated testing, and JWT authentication into a single developer workflow.

---

## 🚀 What It Does

Instead of manually creating a branch, writing code, testing it, committing changes, pushing to GitLab, and opening a Merge Request, a developer can simply describe what they want to build.

For example:

> Create a Python function that adds two numbers and handles integers and decimals.

The AI DevOps Agent then:

1. Understands the requirement using an LLM.
2. Generates a suitable branch name, commit message, and Merge Request title.
3. Searches previous Merge Requests using Elasticsearch for relevant context.
4. Generates the required code.
5. Automatically generates unit tests.
6. Executes the generated tests using `pytest`.
7. Presents the generated workflow to the user for approval.
8. Creates a Git branch.
9. Commits and pushes the generated code.
10. Creates a GitLab Merge Request.

The user remains in control through a **human-in-the-loop approval step** before repository changes are made.

---

# ✨ Features

### 🧠 AI-Powered Requirement Analysis

The agent accepts natural-language development requests and extracts:

- Requirement analysis
- Suggested branch name
- Commit message
- Merge Request title

---

### 🔎 Elasticsearch-Powered Context Retrieval

Previous Merge Requests are indexed in Elasticsearch.

Before generating a new implementation, the agent searches for relevant historical Merge Requests and uses them as additional context.

This enables the system to reuse information from previous development activity.

---

### 💻 AI Code Generation

The agent generates implementation code based on the user's request and the retrieved repository context.

---

### 🧪 Automated Unit Test Generation

For generated code, the system automatically:

- Generates unit tests using an LLM
- Executes tests using `pytest`
- Captures test output
- Detects failing test cases

The workflow can attempt to correct generated tests when failures occur.

---

### 👤 Human-in-the-Loop Approval

Before making changes to the Git repository, the workflow pauses and asks the user for approval.

The user can:

- ✅ Approve the workflow
- ❌ Reject the workflow

Repository changes are only performed after approval.

---

### 🌳 Automated Git Workflow

After approval, the agent can:

1. Create a new branch
2. Write the generated code to the repository
3. Commit the changes
4. Push the branch to GitLab
5. Create a Merge Request

---

### 🔐 JWT Authentication

The application includes JWT-based authentication.

The workflow is:

```text
User Login
    ↓
Backend verifies credentials
    ↓
JWT token generated
    ↓
Token stored by frontend
    ↓
Protected API requests include:

Authorization: Bearer <token>
    ↓
Backend validates JWT
    ↓
Authenticated request is processed
