from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Literal
import json
import os
import threading
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


class TodoItem(BaseModel):
    id: int
    title: str
    description: str
    completed: bool
    due: Optional[str] = None
    priority: Optional[Literal["high", "medium", "low"]] = None
    category: Optional[str] = None


TODO_FILE = "todo.json"
_file_lock = threading.Lock()

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, None: 3}


def load_todos() -> list:
    with _file_lock:
        return _read_todos()


def _read_todos() -> list:
    """락을 이미 보유한 상태에서 파일을 읽음."""
    if not os.path.exists(TODO_FILE):
        return []
    try:
        with open(TODO_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _write_todos(todos: list) -> None:
    """락을 이미 보유한 상태에서 파일을 씀."""
    with open(TODO_FILE, "w") as f:
        json.dump(todos, f, indent=4)


def save_todos(todos: list) -> None:
    with _file_lock:
        _write_todos(todos)


@app.get("/todos", response_model=list[TodoItem])
def get_todos(
    priority: Optional[Literal["high", "medium", "low"]] = Query(None),
    category: Optional[str] = Query(None),
    completed: Optional[bool] = Query(None),
    sort_by: Optional[Literal["priority", "due", "id"]] = Query(None),
):
    todos = load_todos()

    if priority is not None:
        todos = [t for t in todos if t.get("priority") == priority]
    if category is not None:
        todos = [t for t in todos if t.get("category") == category]
    if completed is not None:
        todos = [t for t in todos if t.get("completed") == completed]

    if sort_by == "priority":
        todos = sorted(todos, key=lambda t: PRIORITY_ORDER[t.get("priority")])
    elif sort_by == "due":
        todos = sorted(todos, key=lambda t: (t.get("due") is None, t.get("due")))
    elif sort_by == "id":
        todos = sorted(todos, key=lambda t: t["id"])

    return todos


@app.get("/todos/search", response_model=list[TodoItem])
def search_todos(q: str = Query(..., min_length=1)):
    todos = load_todos()
    q_lower = q.lower()
    return [
        t for t in todos
        if q_lower in t["title"].lower() or q_lower in t["description"].lower()
    ]


@app.post("/todos", response_model=TodoItem)
def create_todo(todo: TodoItem):
    with _file_lock:
        todos = _read_todos()
        todos.append(todo.model_dump())
        _write_todos(todos)
    return todo


@app.put("/todos/{todo_id}", responses={404: {"description": "Todo not found"}}, response_model=TodoItem)
def update_todo(todo_id: int, updated_todo: TodoItem):
    with _file_lock:
        todos = _read_todos()
        for todo in todos:
            if todo["id"] == todo_id:
                todo.update(updated_todo.model_dump())
                _write_todos(todos)
                return updated_todo
    raise HTTPException(status_code=404, detail="To-Do item not found")


@app.delete("/todos/{todo_id}", response_model=dict)
def delete_todo(todo_id: int):
    with _file_lock:
        todos = _read_todos()
        filtered = [t for t in todos if t["id"] != todo_id]
        if len(filtered) == len(todos):
            raise HTTPException(status_code=404, detail="To-Do item not found")
        _write_todos(filtered)
    return {"message": "To-Do item deleted"}


@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("templates/index.html", "r") as file:
        content = file.read()
    return HTMLResponse(content=content)
