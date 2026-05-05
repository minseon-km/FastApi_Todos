"""
Locust 부하 테스트 스크립트 — FastAPI Todo App
실행: locust -f locustfile.py --host=http://<서버IP>:5002

Web UI: http://localhost:8089
  - Number of users: 50 (동시 접속자)
  - Spawn rate: 5 (초당 증가)
  - Duration: 2~3분 권장 (Grafana 패널에 충분한 데이터 확보)
"""

import random
from locust import HttpUser, task, between

PRIORITIES = ["high", "medium", "low"]
CATEGORIES = ["work", "home", "study", "health"]

SAMPLE_TODOS = [
    {"title": "Buy groceries", "description": "Milk, eggs, bread", "category": "home"},
    {"title": "Write report", "description": "Q2 performance report", "category": "work"},
    {"title": "Study FastAPI", "description": "Read docs and practice", "category": "study"},
    {"title": "Morning run", "description": "5km at the park", "category": "health"},
    {"title": "Fix bug #42", "description": "Null pointer in user service", "category": "work"},
    {"title": "Call dentist", "description": "Schedule appointment", "category": "health"},
    {"title": "Read book", "description": "Clean Code chapter 5", "category": "study"},
    {"title": "Clean room", "description": "Vacuum and organize desk", "category": "home"},
]

SEARCH_KEYWORDS = ["work", "study", "bug", "report", "clean"]


class TodoUser(HttpUser):
    """
    태스크 비율 (weight 기반):
      GET /todos             40%
      POST /todos            20%
      PUT /todos/{id}        15%
      DELETE /todos/{id}     10%
      GET /todos?filter      10%
      GET /todos/search       5%
    """
    wait_time = between(0.5, 2.0)

    def on_start(self):
        self._next_id = random.randint(1000, 9999)
        self._created_ids: list[int] = []

        # 초기 데이터 5개 삽입 (수정/삭제 태스크에서 사용)
        for i in range(5):
            self._create_one()

    def _next_todo_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _create_one(self):
        sample = random.choice(SAMPLE_TODOS)
        todo_id = self._next_todo_id()
        payload = {
            "id": todo_id,
            "title": sample["title"],
            "description": sample["description"],
            "completed": False,
            "priority": random.choice(PRIORITIES),
            "category": sample["category"],
            "due": random.choice(["2026-06-01", "2026-07-15", "2026-08-30", None]),
        }
        with self.client.post("/todos", json=payload, catch_response=True) as resp:
            if resp.status_code == 200:
                self._created_ids.append(todo_id)

    # ── 태스크 정의 ─────────────────────────────────────────

    @task(40)
    def get_all_todos(self):
        self.client.get("/todos")

    @task(20)
    def create_todo(self):
        self._create_one()

    @task(15)
    def update_todo(self):
        if not self._created_ids:
            return
        todo_id = random.choice(self._created_ids)
        sample = random.choice(SAMPLE_TODOS)
        payload = {
            "id": todo_id,
            "title": sample["title"] + " (updated)",
            "description": sample["description"],
            "completed": random.choice([True, False]),
            "priority": random.choice(PRIORITIES),
            "category": sample["category"],
            "due": None,
        }
        with self.client.put(f"/todos/{todo_id}", json=payload, catch_response=True) as resp:
            if resp.status_code == 404:
                resp.success()  # 이미 삭제된 항목 — 오류로 집계하지 않음
                self._created_ids = [i for i in self._created_ids if i != todo_id]

    @task(10)
    def delete_todo(self):
        if not self._created_ids:
            return
        todo_id = self._created_ids.pop(random.randrange(len(self._created_ids)))
        self.client.delete(f"/todos/{todo_id}")

    @task(10)
    def get_todos_filtered(self):
        params = {}
        if random.random() < 0.6:
            params["priority"] = random.choice(PRIORITIES)
        if random.random() < 0.4:
            params["category"] = random.choice(CATEGORIES)
        if random.random() < 0.3:
            params["completed"] = random.choice(["true", "false"])
        if random.random() < 0.5:
            params["sort_by"] = random.choice(["priority", "due", "id"])
        self.client.get("/todos", params=params)

    @task(5)
    def search_todos(self):
        keyword = random.choice(SEARCH_KEYWORDS)
        self.client.get("/todos/search", params={"q": keyword})
