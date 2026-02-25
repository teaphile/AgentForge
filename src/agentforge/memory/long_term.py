"""Persistent memory backed by SQLite with optional ChromaDB vector search."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from agentforge.memory.base import BaseMemory


class LongTermMemory(BaseMemory):

    def __init__(self, db_path: str = ".agentforge/memory.db", shared: bool = True):
        self.db_path = db_path
        self.shared = shared
        self._chroma_collection = None

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._db_lock = threading.Lock()
        self._init_db()

        # Try to initialize ChromaDB (optional dependency for semantic search)
        self._init_chromadb()

    def _init_db(self):
        """Create tables if they don't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                content TEXT NOT NULL,
                importance REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                accessed_at TEXT,
                access_count INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_agent ON memories(agent_name)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance)
        """)
        self._conn.commit()

    def _init_chromadb(self):
        """Initialize ChromaDB for vector search (best-effort)."""
        try:
            import chromadb

            chroma_path = str(Path(self.db_path).parent / "chromadb")
            client = chromadb.PersistentClient(path=chroma_path)
            self._chroma_collection = client.get_or_create_collection(
                name="agentforge_memories",
                metadata={"hnsw:space": "cosine"},
            )
        except ImportError:
            self._chroma_collection = None
        except Exception:
            self._chroma_collection = None

    async def _db_execute(self, sql: str, params: tuple = ()) -> None:
        def _run():
            with self._db_lock:
                self._conn.execute(sql, params)
        await asyncio.to_thread(_run)

    async def _db_execute_commit(self, sql: str, params: tuple = ()) -> None:
        def _run():
            with self._db_lock:
                self._conn.execute(sql, params)
                self._conn.commit()
        await asyncio.to_thread(_run)

    async def _db_query(self, sql: str, params: tuple = ()) -> list:
        def _run():
            with self._db_lock:
                return self._conn.execute(sql, params).fetchall()
        return await asyncio.to_thread(_run)

    async def _db_commit(self) -> None:
        def _run():
            with self._db_lock:
                self._conn.commit()
        await asyncio.to_thread(_run)

    async def store(self, agent_name: str, content: str, importance: float = 0.5, metadata: dict | None = None) -> str:
        memory_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(metadata or {})

        await self._db_execute_commit(
            "INSERT INTO memories "
            "(id, agent_name, content, importance, created_at, accessed_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (memory_id, agent_name, content, importance, now, now, meta_json),
        )

        # Add to ChromaDB for semantic search
        if self._chroma_collection is not None:
            try:
                self._chroma_collection.add(
                    ids=[memory_id],
                    documents=[content],
                    metadatas=[{"agent_name": agent_name, "importance": importance, "created_at": now}],
                )
            except Exception:
                pass

        return memory_id

    async def recall(self, agent_name: str, query: str, limit: int = 5) -> list[dict]:
        # Try semantic search with ChromaDB first
        if self._chroma_collection is not None:
            try:
                where_filter = None if self.shared else {"agent_name": agent_name}
                results = await asyncio.to_thread(
                    self._chroma_collection.query,
                    query_texts=[query],
                    n_results=limit,
                    where=where_filter,
                )

                if results and results["documents"] and results["documents"][0]:
                    memories = []
                    for i, doc in enumerate(results["documents"][0]):
                        meta = results["metadatas"][0][i] if results["metadatas"] else {}
                        mem_id = results["ids"][0][i] if results["ids"] else None

                        if mem_id:
                            now = datetime.now(timezone.utc).isoformat()
                            await self._db_execute(
                                "UPDATE memories SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                                (now, mem_id),
                            )
                            await self._db_commit()

                        memories.append({
                            "content": doc,
                            "importance": meta.get("importance", 0.5),
                            "created_at": meta.get("created_at", ""),
                        })
                    return memories
            except Exception:
                pass

        # Fallback: SQLite keyword search
        query_words = query.lower().split()
        if self.shared:
            rows = await self._db_query(
                "SELECT id, content, importance, created_at FROM memories "
                "ORDER BY importance DESC, created_at DESC LIMIT ?",
                (limit * 3,),
            )
        else:
            rows = await self._db_query(
                "SELECT id, content, importance, created_at FROM memories "
                "WHERE agent_name = ? "
                "ORDER BY importance DESC, created_at DESC LIMIT ?",
                (agent_name, limit * 3),
            )

        scored = []
        for row in rows:
            content_lower = row["content"].lower()
            matches = sum(1 for w in query_words if w in content_lower)
            score = (matches / max(len(query_words), 1)) + row["importance"] * 0.3
            scored.append((score, dict(row)))

        scored.sort(key=lambda x: x[0], reverse=True)
        results_list = []
        for _, row in scored[:limit]:
            now = datetime.now(timezone.utc).isoformat()
            await self._db_execute(
                "UPDATE memories SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                (now, row["id"]),
            )
            results_list.append({
                "content": row["content"],
                "importance": row["importance"],
                "created_at": row["created_at"],
            })
        await self._db_commit()
        return results_list

    async def forget(self, min_importance: float = 0.1, max_age_days: int = 30):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        rows = await self._db_query(
            "SELECT id FROM memories WHERE importance < ? AND created_at < ? AND access_count < 3",
            (min_importance, cutoff),
        )

        ids_to_delete = [row["id"] for row in rows]
        if ids_to_delete:
            placeholders = ",".join("?" * len(ids_to_delete))
            await self._db_execute_commit(
                f"DELETE FROM memories WHERE id IN ({placeholders})",
                tuple(ids_to_delete),
            )

            # Remove from ChromaDB
            if self._chroma_collection is not None:
                try:
                    self._chroma_collection.delete(ids=ids_to_delete)
                except Exception:
                    pass

    async def clear(self, agent_name: str | None = None):
        if agent_name is None:
            await self._db_execute("DELETE FROM memories")
            if self._chroma_collection is not None:
                try:
                    # ChromaDB doesn't have a clear method; recreate collection
                    import chromadb

                    chroma_path = str(Path(self.db_path).parent / "chromadb")
                    client = chromadb.PersistentClient(path=chroma_path)
                    client.delete_collection("agentforge_memories")
                    self._chroma_collection = client.get_or_create_collection(
                        name="agentforge_memories",
                        metadata={"hnsw:space": "cosine"},
                    )
                except Exception:
                    pass
        else:
            await self._db_execute(
                "DELETE FROM memories WHERE agent_name = ?",
                (agent_name,),
            )
        await self._db_commit()

    def close(self):
        self._conn.close()
