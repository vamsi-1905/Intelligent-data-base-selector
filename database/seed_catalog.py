"""
Seed the catalog with 16 databases and evidence-backed suitability scores.

Applied automatically when the app starts (see database/migrations.py).
Manual run from the project root:   python -m database.seed_catalog

Scores are qualitative 1-10 suitability ratings (higher is always better;
for Cost, 10 means cheapest) derived from each project's documented
capabilities. Every score stores a one-line reason and a documentation link.
"""

CRITERIA = [
    ("Latency", "Suitability for low-latency queries", 0.13),
    ("Scalability", "Suitability for growth in workload and data", 0.13),
    ("Cost", "Affordability and cost efficiency (10 = cheapest)", 0.10),
    ("Security", "Security and access-control capabilities", 0.13),
    ("Vector Search", "Suitability for vector similarity search", 0.17),
    ("Transactions", "Transactional and consistency capabilities", 0.10),
    ("Availability", "Availability and resilience capabilities", 0.10),
    ("AI Integration", "Suitability for AI application integration", 0.06),
    ("Storage Capacity", "Capacity to store very large datasets", 0.08),
]
ORDER = [c[0] for c in CRITERIA]

# name: (type, description, docs_url, [(score, reason) x 9 in ORDER])
CATALOG = {
    "PostgreSQL": ("Relational", "Open-source relational database with strong SQL, ACID transactions and extensibility",
        "https://www.postgresql.org/docs/current/", [
        (8, "Mature planner and indexing give low-latency OLTP queries"),
        (7, "Vertical scaling and read replicas; sharding needs extensions"),
        (9, "Open source with no license fees"),
        (9, "Role-based access, row-level security, TLS and SCRAM authentication"),
        (7, "The pgvector extension adds HNSW and IVFFlat indexes"),
        (10, "Full ACID with MVCC and serializable isolation"),
        (9, "Streaming replication and standard failover tooling"),
        (8, "pgvector plus wide ML and ORM tooling support"),
        (8, "Handles multi-terabyte datasets on a single primary")]),
    "MySQL": ("Relational", "Widely used relational database for transactional web applications",
        "https://dev.mysql.com/doc/", [
        (8, "InnoDB serves indexed reads with low latency"),
        (7, "Read replicas scale reads; sharding needs Vitess or similar"),
        (9, "Community edition is free to use"),
        (8, "TLS, roles and password policies; audit features in enterprise tiers"),
        (4, "Vector similarity search is limited outside HeatWave"),
        (9, "InnoDB provides ACID transactions"),
        (8, "Replication, Group Replication and InnoDB Cluster"),
        (6, "Fewer native AI integrations than PostgreSQL"),
        (7, "InnoDB tables scale to terabytes on a single server")]),
    "MongoDB": ("Document", "Document-oriented database for flexible application data",
        "https://www.mongodb.com/docs/manual/", [
        (8, "WiredTiger storage and flexible indexing give fast reads"),
        (9, "Native sharding for horizontal scale"),
        (7, "Free to self-host; Atlas managed service is paid"),
        (8, "RBAC, TLS and client-side field-level encryption"),
        (7, "Atlas Vector Search handles embeddings"),
        (7, "Multi-document ACID transactions supported since 4.0"),
        (9, "Replica sets with automatic failover"),
        (8, "Atlas Vector Search with LangChain and LlamaIndex integrations"),
        (9, "Sharded clusters hold very large datasets")]),
    "Elasticsearch": ("Search", "Distributed search and analytics engine",
        "https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html", [
        (9, "Inverted indexes give fast full-text search at scale"),
        (9, "Shards distribute data and queries across nodes"),
        (6, "Memory-hungry clusters raise infrastructure cost"),
        (8, "RBAC, TLS and document-level security"),
        (8, "Native dense_vector fields and approximate kNN search"),
        (3, "No multi-document ACID transactions"),
        (9, "Replica shards and automatic shard recovery"),
        (9, "Hybrid search and inference integrations for RAG"),
        (9, "Clusters scale out to very large indexes")]),
    "Qdrant": ("Vector", "Open-source vector database for similarity search",
        "https://qdrant.tech/documentation/", [
        (9, "Rust engine with HNSW indexing for fast ANN queries"),
        (8, "Distributed mode with sharding and replication"),
        (8, "Open source; self-hosting is free"),
        (7, "API keys and TLS; fewer enterprise access controls"),
        (10, "Purpose-built vector search with payload filtering"),
        (4, "No multi-record ACID transactions"),
        (8, "Replication across nodes in distributed mode"),
        (9, "Integrations with LangChain and LlamaIndex"),
        (8, "On-disk storage and quantization reduce memory needs")]),
    "Pinecone": ("Vector", "Fully managed vector database service",
        "https://docs.pinecone.io/", [
        (9, "Managed indexes built for low-latency vector queries"),
        (9, "Serverless indexes scale automatically"),
        (5, "Usage-based managed pricing with no self-host option"),
        (8, "Encryption in transit and at rest with RBAC"),
        (10, "Purpose-built vector search with metadata filtering"),
        (3, "No multi-record transactions"),
        (9, "Fully managed with built-in replication"),
        (9, "Native LangChain and LlamaIndex integrations"),
        (8, "Serverless indexes scale to very large vector counts")]),
    "Redis": ("Key-Value", "In-memory data store used for caching, queues and fast lookups",
        "https://redis.io/docs/", [
        (10, "In-memory design gives sub-millisecond reads"),
        (7, "Redis Cluster shards keys but data must fit in memory"),
        (6, "RAM-based storage is costly at large sizes"),
        (7, "ACLs and TLS; fewer built-in audit controls"),
        (7, "Vector search through the Redis Query Engine"),
        (5, "MULTI/EXEC batches commands but has no rollback"),
        (8, "Replication with Sentinel or Cluster failover"),
        (8, "Vector search, semantic caching and LangChain support"),
        (4, "Dataset size is bounded by available memory")]),
    "Cassandra": ("Wide-Column", "Masterless wide-column database for write-heavy, high-availability workloads",
        "https://cassandra.apache.org/doc/latest/", [
        (7, "Fast writes; read latency depends on the data model"),
        (10, "Linear horizontal scaling with a masterless ring"),
        (7, "Open source, but large clusters add operating cost"),
        (7, "Role-based access control and TLS"),
        (6, "Vector search added in Cassandra 5.0 via storage-attached indexes"),
        (4, "Lightweight transactions only within a single partition"),
        (10, "Masterless replication with no single point of failure"),
        (5, "Few native AI integrations"),
        (9, "Designed for very large distributed datasets")]),
    "Neo4j": ("Graph", "Native graph database for connected data and relationship queries",
        "https://neo4j.com/docs/", [
        (8, "Index-free adjacency speeds relationship traversals"),
        (6, "Clustering available; sharding is more limited"),
        (6, "Community edition is free; enterprise features need a license"),
        (8, "RBAC and encryption in Enterprise edition"),
        (7, "Native vector indexes since Neo4j 5.x"),
        (9, "Fully ACID transactions"),
        (8, "Clustering for failover in Enterprise edition"),
        (8, "GraphRAG patterns and LangChain integration"),
        (7, "Scales to large graphs on a single cluster")]),
    "SQLite": ("Embedded", "Serverless embedded SQL database stored in a single file",
        "https://www.sqlite.org/docs.html", [
        (9, "In-process engine with no network overhead"),
        (3, "Single-writer model limits concurrent write scaling"),
        (10, "Public domain with no server to operate"),
        (4, "No built-in user authentication or network encryption"),
        (4, "Vector search only through extensions"),
        (8, "ACID transactions with serializable isolation"),
        (3, "Single file with no built-in replication"),
        (5, "Useful for on-device apps; AI features come from extensions"),
        (5, "Database files can be very large but live on one machine")]),
    "Milvus": ("Vector", "Open-source distributed vector database",
        "https://milvus.io/docs", [
        (9, "Purpose-built ANN indexes for fast similarity search"),
        (9, "Cloud-native distributed architecture"),
        (7, "Open source, but distributed deployments need infrastructure"),
        (7, "RBAC and TLS support"),
        (10, "Multiple ANN index types built for vector workloads"),
        (3, "No multi-entity ACID transactions"),
        (8, "Replicas and redundant components"),
        (9, "LangChain and LlamaIndex integrations"),
        (9, "Built for billion-scale vector collections")]),
    "Weaviate": ("Vector", "Open-source vector database with built-in vectorization modules",
        "https://weaviate.io/developers/weaviate", [
        (9, "HNSW indexes give fast approximate search"),
        (8, "Sharding and replication"),
        (7, "Open source; managed cloud is paid"),
        (7, "API key and OIDC authentication with RBAC"),
        (10, "Purpose-built vector search with hybrid queries"),
        (3, "No multi-object ACID transactions"),
        (8, "Replication with tunable consistency"),
        (9, "Built-in vectorizer modules and generative search for RAG"),
        (8, "Horizontal scaling through sharding")]),
    "ClickHouse": ("Analytical", "Columnar OLAP database for fast analytical queries",
        "https://clickhouse.com/docs", [
        (9, "Columnar engine returns analytical queries quickly"),
        (9, "Sharding and replication across clusters"),
        (8, "Open source; heavy compression lowers storage cost"),
        (7, "RBAC, TLS and row policies"),
        (6, "Vector similarity indexes are supported"),
        (3, "Not built for OLTP; transactions are limited"),
        (8, "Replication coordinated by ClickHouse Keeper"),
        (6, "Analytical backend with fewer AI-native features"),
        (9, "Columnar compression suits very large datasets")]),
    "DynamoDB": ("Key-Value", "Fully managed NoSQL key-value and document database on AWS",
        "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/", [
        (9, "Single-digit millisecond reads and writes at scale"),
        (10, "Automatic partitioning with no capacity ceiling"),
        (6, "Pay per request; costs rise with heavy throughput"),
        (9, "IAM access control, encryption at rest and VPC endpoints"),
        (2, "No native vector search"),
        (7, "ACID transactions across up to 100 items"),
        (10, "Multi-AZ replication and global tables"),
        (5, "AI workloads need separate AWS services"),
        (10, "Tables have no size limit")]),
    "CockroachDB": ("Relational", "Distributed SQL database with serializable transactions",
        "https://www.cockroachlabs.com/docs/", [
        (7, "Consensus replication adds write latency"),
        (9, "Horizontal scaling with automatic rebalancing"),
        (6, "Core is free; enterprise features and cloud are paid"),
        (8, "RBAC, encryption and audit logging"),
        (5, "Vector support is recent and less mature"),
        (10, "Serializable isolation by default"),
        (10, "Survives node and region failures"),
        (6, "PostgreSQL-compatible drivers and ORMs"),
        (9, "Scales out across nodes for large datasets")]),
    "Chroma": ("Vector", "Lightweight open-source embedding database for LLM applications",
        "https://docs.trychroma.com/", [
        (8, "Local in-memory index gives fast similarity search"),
        (5, "Mainly single-node; distributed mode is newer"),
        (9, "Open source and free to self-host"),
        (5, "Basic authentication options only"),
        (9, "Built around embeddings and similarity search"),
        (3, "No multi-record transactions"),
        (4, "Limited built-in replication"),
        (9, "Designed for LLM apps with LangChain support"),
        (5, "Best suited to small and medium collections")]),
}


ALIASES = {
    "Apache Cassandra": "Cassandra",
    "Postgres": "PostgreSQL",
    "Postgresql": "PostgreSQL",
    "Elastic Search": "Elasticsearch",
    "Amazon DynamoDB": "DynamoDB",
    "AWS DynamoDB": "DynamoDB",
    "Cockroach DB": "CockroachDB",
    "ChromaDB": "Chroma",
    "Chroma DB": "Chroma",
    "Mongo DB": "MongoDB",
}


def fit_band(score):
    if score >= 9:
        return "Strong fit"
    if score >= 7:
        return "Good fit"
    if score >= 5:
        return "Moderate fit"
    return "Weak fit"


def seed(cur):
    """
    Upsert criteria, databases and curated scores using an open cursor.

    Scores researched from the web or estimated by a model (origin 'web' or
    'model') are never overwritten. Legacy rows with no origin (the original
    seed data) are replaced.
    """

    for name, description, weight in CRITERIA:
        cur.execute(
            """
            INSERT INTO criteria (name, description, weight, score_direction)
            VALUES (%s, %s, %s, 'higher')
            ON CONFLICT (name) DO UPDATE
            SET description = EXCLUDED.description, weight = EXCLUDED.weight;
            """,
            (name, description, weight),
        )

    for alias, canonical in ALIASES.items():
        cur.execute(
            """
            UPDATE database_systems SET name = %s
            WHERE lower(name) = lower(%s)
              AND NOT EXISTS (SELECT 1 FROM database_systems WHERE name = %s);
            """,
            (canonical, alias, canonical),
        )

    for name, (db_type, description, docs, rows) in CATALOG.items():
        assert len(rows) == len(ORDER), name
        cur.execute(
            """
            INSERT INTO database_systems (name, database_type, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (name) DO UPDATE
            SET database_type = EXCLUDED.database_type,
                description = EXCLUDED.description
            RETURNING database_id;
            """,
            (name, db_type, description),
        )
        database_id = cur.fetchone()[0]

        for criterion, (score, reason) in zip(ORDER, rows):
            reasoning = f"{fit_band(score)} for {criterion.lower()}: {reason[0].lower() + reason[1:]}."
            cur.execute(
                """
                INSERT INTO database_criteria_scores
                    (database_id, criterion_id, score, evidence, reasoning, source_url, origin, updated_at)
                SELECT %s, criterion_id, %s, %s, %s, %s, 'curated', CURRENT_TIMESTAMP
                FROM criteria WHERE name = %s
                ON CONFLICT (database_id, criterion_id) DO UPDATE
                SET score = EXCLUDED.score,
                    evidence = EXCLUDED.evidence,
                    reasoning = EXCLUDED.reasoning,
                    source_url = EXCLUDED.source_url,
                    origin = 'curated',
                    updated_at = CURRENT_TIMESTAMP
                WHERE database_criteria_scores.origin IS NULL
                   OR database_criteria_scores.origin = 'curated';
                """,
                (database_id, score, reason, reasoning, docs, criterion),
            )


def main():
    from database.migrations import ensure_catalog

    ensure_catalog()
    print(f"Catalog ready: {len(CATALOG)} curated databases, {len(CRITERIA)} criteria.")


if __name__ == "__main__":
    main()