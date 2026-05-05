import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from main import app, save_todos, load_todos, TodoItem, TODO_FILE

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown():
    save_todos([])
    yield
    save_todos([])


# ── 기본 CRUD ──────────────────────────────────────────────

def test_get_todos_empty():
    response = client.get("/todos")
    assert response.status_code == 200
    assert response.json() == []

def test_get_todos_with_items():
    todo = TodoItem(id=1, title="Test", description="Test description", completed=False)
    save_todos([todo.dict()])
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Test"

def test_create_todo():
    todo = {"id": 1, "title": "Test", "description": "Test description", "completed": False}
    response = client.post("/todos", json=todo)
    assert response.status_code == 200
    assert response.json()["title"] == "Test"

def test_create_todo_invalid():
    todo = {"id": 1, "title": "Test"}
    response = client.post("/todos", json=todo)
    assert response.status_code == 422

def test_update_todo():
    todo = TodoItem(id=1, title="Test", description="Test description", completed=False)
    save_todos([todo.dict()])
    updated_todo = {"id": 1, "title": "Updated", "description": "Updated description", "completed": True}
    response = client.put("/todos/1", json=updated_todo)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"

def test_update_todo_not_found():
    updated_todo = {"id": 1, "title": "Updated", "description": "Updated description", "completed": True}
    response = client.put("/todos/1", json=updated_todo)
    assert response.status_code == 404

def test_delete_todo():
    todo = TodoItem(id=1, title="Test", description="Test description", completed=False)
    save_todos([todo.dict()])
    response = client.delete("/todos/1")
    assert response.status_code == 200
    assert response.json()["message"] == "To-Do item deleted"

def test_delete_todo_not_found():
    response = client.delete("/todos/1")
    assert response.status_code == 200
    assert response.json()["message"] == "To-Do item deleted"

def test_load_todos_no_file():
    if os.path.exists(TODO_FILE):
        os.remove(TODO_FILE)
    result = load_todos()
    assert result == []

def test_read_root():
    from unittest.mock import patch, mock_open
    html_content = "<html><body>Todo App</body></html>"
    with patch("builtins.open", mock_open(read_data=html_content)):
        response = client.get("/")
    assert response.status_code == 200
    assert "Todo App" in response.text


# ── priority / category 필드 ────────────────────────────────

def test_create_todo_with_priority_and_category():
    todo = {
        "id": 1, "title": "High priority task", "description": "desc",
        "completed": False, "priority": "high", "category": "work"
    }
    response = client.post("/todos", json=todo)
    assert response.status_code == 200
    assert response.json()["priority"] == "high"
    assert response.json()["category"] == "work"

def test_create_todo_invalid_priority():
    todo = {
        "id": 1, "title": "Bad priority", "description": "desc",
        "completed": False, "priority": "urgent"
    }
    response = client.post("/todos", json=todo)
    assert response.status_code == 422


# ── 필터링 ──────────────────────────────────────────────────

def _seed_todos():
    todos = [
        {"id": 1, "title": "Work A", "description": "d", "completed": False, "priority": "high", "category": "work", "due": None},
        {"id": 2, "title": "Home B", "description": "d", "completed": True,  "priority": "low",  "category": "home", "due": "2026-06-01"},
        {"id": 3, "title": "Work C", "description": "d", "completed": False, "priority": "medium","category": "work", "due": "2026-05-10"},
    ]
    save_todos(todos)

def test_filter_by_priority():
    _seed_todos()
    response = client.get("/todos?priority=high")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == 1

def test_filter_by_category():
    _seed_todos()
    response = client.get("/todos?category=work")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

def test_filter_by_completed():
    _seed_todos()
    response = client.get("/todos?completed=true")
    assert response.status_code == 200
    data = response.json()
    assert all(t["completed"] for t in data)

def test_filter_combined():
    _seed_todos()
    response = client.get("/todos?category=work&completed=false")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(t["category"] == "work" for t in data)


# ── 정렬 ────────────────────────────────────────────────────

def test_sort_by_priority():
    _seed_todos()
    response = client.get("/todos?sort_by=priority")
    assert response.status_code == 200
    priorities = [t["priority"] for t in response.json()]
    assert priorities == ["high", "medium", "low"]

def test_sort_by_due():
    _seed_todos()
    response = client.get("/todos?sort_by=due")
    assert response.status_code == 200
    data = response.json()
    dues = [t["due"] for t in data if t["due"] is not None]
    assert dues == sorted(dues)


# ── 검색 ────────────────────────────────────────────────────

def test_search_by_title():
    _seed_todos()
    response = client.get("/todos/search?q=work")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all("work" in t["title"].lower() or "work" in t["description"].lower() for t in data)

def test_search_case_insensitive():
    _seed_todos()
    response = client.get("/todos/search?q=WORK")
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_search_no_results():
    _seed_todos()
    response = client.get("/todos/search?q=zzznomatch")
    assert response.status_code == 200
    assert response.json() == []

def test_search_empty_query():
    response = client.get("/todos/search?q=")
    assert response.status_code == 422
