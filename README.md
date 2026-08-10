# AI DevOps Agent

## Clone the repository

```bash
git clone ...
```

## Create a virtual environment

```bash
python -m venv venv
```

## Activate

Windows

```bash
venv\Scripts\activate
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Create a .env file

Copy `.env.example`

Fill in:

- GitLab Token
- Project ID

## Start Ollama

```bash
ollama serve
```

Pull the required model:

```bash
ollama pull qwen2.5-coder:3b
```

## Start Elasticsearch

...

## Run Backend

```bash
uvicorn main:app --reload
```

## Run Frontend

```bash
python main.py
```