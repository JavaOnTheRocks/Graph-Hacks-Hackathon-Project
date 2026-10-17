
import re
import uuid
from datetime import datetime, timezone

from falkordb import FalkorDB
from mem0 import Memory
from mem0_falkordb import register

from app.config import Settings


MEMORY_LABELS = {
    "semantic": "SemanticMemory",
    "episodic": "EpisodicMemory",
    "procedural": "ProceduralMemory",
}

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from",
    "what", "when", "where", "which", "would", "could",
    "should", "about", "have", "does", "into", "your",
    "user", "their", "them", "then", "than", "please",
    "remember", "memory", "memories", "find", "retrieve",
}


def extract_terms(text: str, max_terms: int = 8) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9_-]+", text.lower())
    return list(dict.fromkeys(
        word for word in words
        if len(word) > 2 and word not in STOPWORDS
    ))[:max_terms]


class LongTermMemory:
    def __init__(self, settings: Settings):
        register()

        self.mem0 = Memory.from_config({
                "vector_store": {
                "provider": "qdrant",
                "config": {
                "host": "localhost",
                "port": 6333,
                "collection_name": "continuityos_memories",
                "embedding_model_dims": 1536,
                },
            },
            "graph_store": {
                "provider": "falkordb",
                "config": {
                    "host": settings.falkordb_host,
                    "port": settings.falkordb_port,
                    "database": settings.mem0_graph_name,
                },
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": settings.openai_model,
                    "api_key": settings.openai_api_key,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "api_key": settings.openai_api_key,
                    "embedding_dims": 1536,
                },
            },
        })

        client_options = {
            "host": settings.falkordb_host,
            "port": settings.falkordb_port,
        }

        if settings.falkordb_password:
            client_options["password"] = settings.falkordb_password

        self.graph_client = FalkorDB(**client_options)
        self.graph = self.graph_client.select_graph(
            settings.continuity_graph_name
        )

    def add(
        self,
        memory_type: str,
        content: str,
        *,
        user_id: str,
    ) -> str:
        if memory_type not in MEMORY_LABELS:
            raise ValueError(f"Unsupported memory type: {memory_type}")
        if not content or not content.strip():
            raise ValueError("Memory content cannot be empty.")
        if not user_id or not user_id.strip():
            raise ValueError("user_id is required.")

        memory_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        label = MEMORY_LABELS[memory_type]
        entities = extract_terms(content) or ["general"]

        # Mem0 handles memory extraction and semantic memory operations.
        self.mem0.add(
            f"[MEMORY_TYPE: {memory_type}]\n{content.strip()}",
            user_id=user_id,
        )

        # The label is selected only from the allowlisted mapping.
        self.graph.query(
            f"""
            MERGE (u:ContinuityUser {{user_id: $user_id}})
            MERGE (m:{label} {{memory_id: $memory_id}})
            SET m.user_id = $user_id,
                m.memory_id = $memory_id,
                m.memory_type = $memory_type,
                m.content = $content,
                m.created_at = $created_at
            MERGE (u)-[:OWNS]->(m)
            WITH m
            UNWIND $entities AS entity_name
            MERGE (e:ContinuityEntity {{
                user_id: $user_id,
                name: entity_name
            }})
            MERGE (m)-[:MENTIONS]->(e)
            """,
            params={
                "user_id": user_id,
                "memory_id": memory_id,
                "memory_type": memory_type,
                "content": content.strip(),
                "created_at": created_at,
                "entities": entities,
            },
        )

        if memory_type == "episodic":
            self.graph.query(
                """
                MATCH (ep:EpisodicMemory {memory_id: $memory_id})
                      -[:MENTIONS]->(e)<-[:MENTIONS]-
                      (s:SemanticMemory)
                WHERE ep.user_id = $user_id
                  AND s.user_id = $user_id
                MERGE (ep)-[:RELATES_TO_FACT]->(s)
                """,
                params={"memory_id": memory_id, "user_id": user_id},
            )

        if memory_type == "procedural":
            self.graph.query(
                """
                MATCH (p:ProceduralMemory {memory_id: $memory_id})
                      -[:MENTIONS]->(e)<-[:MENTIONS]-
                      (ep:EpisodicMemory)
                WHERE p.user_id = $user_id
                  AND ep.user_id = $user_id
                MERGE (ep)-[:SUGGESTS_PROCEDURE]->(p)
                """,
                params={"memory_id": memory_id, "user_id": user_id},
            )

        return memory_id

    def retrieve(
        self,
        memory_type: str,
        query: str,
        *,
        user_id: str,
        limit: int = 5,
    ) -> list[dict]:
        if memory_type not in MEMORY_LABELS:
            raise ValueError(f"Unsupported memory type: {memory_type}")
        if not user_id or not user_id.strip():
            raise ValueError("user_id is required.")

        label = MEMORY_LABELS[memory_type]
        terms = extract_terms(query) or ["general"]

        if memory_type in {"semantic", "episodic"}:
            result = self.graph.query(
                f"""
                MATCH (u:ContinuityUser {{user_id: $user_id}})
                      -[:OWNS]->(seed:{label})
                WHERE seed.user_id = $user_id
                  AND any(term IN $terms
                          WHERE toLower(seed.content) CONTAINS term)
                OPTIONAL MATCH (seed)-[:MENTIONS]->(e)
                               <-[:MENTIONS]-(related:{label})
                WHERE related.user_id = $user_id
                WITH collect(DISTINCT seed) +
                     collect(DISTINCT related) AS all_memories
                UNWIND all_memories AS m
                WITH DISTINCT m
                WHERE m IS NOT NULL
                RETURN m.memory_id, m.content, m.created_at
                ORDER BY m.created_at DESC
                LIMIT $limit
                """,
                params={
                    "user_id": user_id,
                    "terms": terms,
                    "limit": limit,
                },
            )
        else:
            result = self.graph.query(
                """
                MATCH (u:ContinuityUser {user_id: $user_id})
                      -[:OWNS]->(p:ProceduralMemory)
                WHERE p.user_id = $user_id
                  AND any(term IN $terms
                          WHERE toLower(p.content) CONTAINS term)
                OPTIONAL MATCH (p)-[:MENTIONS]->(e)
                               <-[:MENTIONS]-(ep:EpisodicMemory)
                WHERE ep.user_id = $user_id
                RETURN p.memory_id, p.content, p.created_at,
                       collect(DISTINCT ep.content)[0..3]
                ORDER BY p.created_at DESC
                LIMIT $limit
                """,
                params={
                    "user_id": user_id,
                    "terms": terms,
                    "limit": limit,
                },
            )

        memories = []
        for row in result.result_set:
            item = {
                "memory_id": row[0],
                "content": row[1],
                "created_at": row[2],
            }
            if memory_type == "procedural" and len(row) > 3:
                item["related_episodes"] = row[3]
            memories.append(item)

        return memories

    def retrieve_all(
        self,
        query: str,
        *,
        user_id: str,
    ) -> dict:
        return {
            category: self.retrieve(
                category, query, user_id=user_id
            )
            for category in ("semantic", "episodic", "procedural")
        }

    @staticmethod
    def format_context(memories: dict) -> str:
        sections = []

        for category in ("semantic", "episodic", "procedural"):
            items = memories.get(category, [])
            if not items:
                continue

            lines = [f"{category.upper()} MEMORY:"]
            for item in items:
                lines.append(f"- {item['content']}")
                for episode in item.get("related_episodes", []):
                    if episode:
                        lines.append(f"  Related episode: {episode}")

            sections.append("\n".join(lines))

        return "\n\n".join(sections) or "No relevant long-term memories found."

    def capture_explicit_memory(
        self,
        user_query: str,
        *,
        user_id: str,
    ) -> str | None:
        text = user_query.lower()

        procedural_signals = (
            "remember this workflow",
            "remember this procedure",
            "my workflow is",
            "my procedure is",
            "always follow this process",
            "steps i use",
        )

        semantic_signals = (
            "remember that",
            "remember this preference",
            "remember my preference",
            "i prefer",
            "my preference is",
            "my name is",
            "i work as",
        )

        if any(signal in text for signal in procedural_signals):
            return self.add(
                "procedural", user_query, user_id=user_id
            )

        if any(signal in text for signal in semantic_signals):
            return self.add(
                "semantic", user_query, user_id=user_id
            )

        return None
