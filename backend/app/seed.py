"""Populate the database with a starter interview-prep curriculum.

Run with:  python -m app.seed
Safe to re-run — it skips categories that already have goals.
"""

from .database import SessionLocal, engine, Base
from .models import Goal, Category

CURRICULUM: dict[Category, list[str]] = {
    Category.OOP: [
        "Explain the 4 pillars: encapsulation, abstraction, inheritance, polymorphism",
        "Compare composition vs inheritance, with examples",
        "SOLID principles — write a short example violating & fixing each",
        "Abstract classes vs interfaces — when to use which",
        "Method overloading vs overriding",
    ],
    Category.OS: [
        "Process vs thread, and context switching cost",
        "Deadlock: 4 necessary conditions + prevention strategies",
        "Virtual memory, paging, and page replacement algorithms (LRU, FIFO)",
        "Scheduling algorithms: FCFS, SJF, Round Robin, Priority",
        "Mutex vs semaphore vs monitor",
    ],
    Category.CN: [
        "TCP vs UDP — handshake, reliability, use cases",
        "What happens when you type a URL into a browser (full flow)",
        "HTTP vs HTTPS, and how TLS handshake works",
        "DNS resolution steps",
        "Load balancing algorithms (round robin, least connections, consistent hashing)",
    ],
    Category.DSA: [
        "Arrays & Strings: two-pointer and sliding window patterns",
        "Linked Lists: reverse, detect cycle, merge two sorted lists",
        "Trees: BFS/DFS traversals, height, LCA",
        "Graphs: BFS/DFS, topological sort, Dijkstra's algorithm",
        "Dynamic Programming: 0/1 knapsack, longest common subsequence",
        "Heaps & Priority Queues: top-K problems",
        "Binary Search on answer space",
    ],
    Category.HLD: [
        "Design a URL shortener (TinyURL)",
        "Design a rate limiter",
        "Design a scalable chat application (WhatsApp-like)",
        "Design a news feed system (Twitter/Instagram)",
        "Design a distributed cache",
        "CAP theorem and how it shapes real system trade-offs",
    ],
    Category.LLD: [
        "Design a parking lot system (classes, relationships)",
        "Design a tic-tac-toe / chess game engine",
        "Design an elevator control system",
        "Design a library management system",
        "Design a splitwise-style expense sharing system",
    ],
    Category.DESIGN_PATTERNS: [
        "Singleton pattern — implementation & pitfalls (thread safety)",
        "Factory & Abstract Factory patterns",
        "Observer pattern (pub/sub)",
        "Strategy pattern",
        "Decorator pattern",
        "Builder pattern",
    ],
}


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for category, titles in CURRICULUM.items():
            already_has_goals = (
                db.query(Goal).filter(Goal.category == category).first()
            )
            if already_has_goals:
                continue
            for i, title in enumerate(titles):
                db.add(Goal(title=title, category=category, priority=100 + i))
        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
