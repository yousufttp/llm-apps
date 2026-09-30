"""
Mini GraphRAG Pipeline
======================
A lightweight GraphRAG implementation for learning purposes.
Uses Claude API for entity/relationship extraction and community summarization.

Pipeline Steps:
1. Load documents
2. Extract entities and relationships (LLM)
3. Build knowledge graph (NetworkX)
4. Detect communities (Leiden algorithm)
5. Generate community summaries (LLM)
6. Query: Local Search + Global Search
"""

import json
import os
from pathlib import Path

# ============================================================
# STEP 1: Document Loader
# ============================================================

def load_documents(data_dir: str) -> list[dict]:
    """Load all markdown files from the data directory."""
    docs = []
    for filepath in sorted(Path(data_dir).glob("*.md")):
        text = filepath.read_text()
        docs.append({
            "id": filepath.stem,
            "filename": filepath.name,
            "content": text
        })
        print(f"  Loaded: {filepath.name} ({len(text)} chars)")
    return docs


# ============================================================
# STEP 2: Entity & Relationship Extraction (LLM)
# ============================================================

EXTRACTION_PROMPT = """You are an expert at extracting structured information from IT documentation.

Given the following document, extract:
1. **Entities**: Services, databases, teams, people, tools, infrastructure components
2. **Relationships**: How entities are connected (depends_on, owns, manages, monitors, escalates_to, etc.)

Return ONLY valid JSON in this exact format (no markdown, no backticks):
{
  "entities": [
    {"name": "Entity Name", "type": "service|database|team|person|tool|infrastructure", "description": "Brief description"}
  ],
  "relationships": [
    {"source": "Entity A", "target": "Entity B", "type": "depends_on|owns|manages|leads|monitors|escalates_to|communicates_via", "description": "Brief description of relationship"}
  ]
}

Rules:
- Normalize entity names (e.g., always use "Payment Service" not "pay-svc" and "pay-svc" separately)
- Include the short code as part of the description if available
- Extract ALL entities and relationships, don't skip any
- Each relationship should be directional (source -> target)

Document:
{document_text}
"""

def extract_entities_and_relationships(doc: dict, llm_call_fn) -> dict:
    """
    Use LLM to extract entities and relationships from a document.
    
    Args:
        doc: Document dict with 'content' field
        llm_call_fn: Function that takes a prompt string and returns LLM response text
    
    Returns:
        Dict with 'entities' and 'relationships' lists
    """
    prompt = EXTRACTION_PROMPT.replace("{document_text}", doc["content"])
    
    response_text = llm_call_fn(prompt)
    
    # Clean response - strip markdown code fences if present
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]  # Remove first line
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"  WARNING: Failed to parse LLM response for {doc['id']}: {e}")
        print(f"  Response preview: {cleaned[:200]}...")
        result = {"entities": [], "relationships": []}
    
    print(f"  Extracted from {doc['id']}: {len(result.get('entities', []))} entities, {len(result.get('relationships', []))} relationships")
    return result


# ============================================================
# STEP 3: Build Knowledge Graph
# ============================================================

def build_graph(all_extractions: list[dict]):
    """
    Build a NetworkX graph from extracted entities and relationships.
    
    This is where the magic happens - we merge entities across documents
    and create a unified graph.
    """
    import networkx as nx
    
    G = nx.Graph()
    
    # Track entity info for merging
    entity_registry = {}  # name -> {type, descriptions}
    
    for extraction in all_extractions:
        # Add entities as nodes
        for entity in extraction.get("entities", []):
            name = entity["name"]
            if name not in entity_registry:
                entity_registry[name] = {
                    "type": entity.get("type", "unknown"),
                    "descriptions": []
                }
            entity_registry[name]["descriptions"].append(entity.get("description", ""))
        
        # Add relationships as edges
        for rel in extraction.get("relationships", []):
            source = rel["source"]
            target = rel["target"]
            
            # Ensure both nodes exist
            for node_name in [source, target]:
                if node_name not in entity_registry:
                    entity_registry[node_name] = {
                        "type": "unknown",
                        "descriptions": []
                    }
            
            # Add edge (or update if exists)
            if G.has_edge(source, target):
                existing = G[source][target]
                existing["types"].append(rel.get("type", "related_to"))
                existing["descriptions"].append(rel.get("description", ""))
            else:
                G.add_edge(
                    source, target,
                    types=[rel.get("type", "related_to")],
                    descriptions=[rel.get("description", "")]
                )
    
    # Add merged entity info to nodes
    for name, info in entity_registry.items():
        merged_desc = " | ".join(set(d for d in info["descriptions"] if d))
        G.add_node(name, type=info["type"], description=merged_desc)
    
    print(f"\n  Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


# ============================================================
# STEP 4: Community Detection
# ============================================================

def detect_communities(G) -> dict:
    """
    Detect communities in the graph using greedy modularity.
    
    In production GraphRAG, the Leiden algorithm is used.
    We use NetworkX's built-in greedy modularity for simplicity.
    
    Returns:
        Dict mapping community_id -> list of node names
    """
    import networkx as nx
    from networkx.algorithms.community import greedy_modularity_communities
    
    if G.number_of_nodes() == 0:
        return {}
    
    # Detect communities
    communities = greedy_modularity_communities(G)
    
    # Convert to dict
    community_map = {}
    for idx, community in enumerate(communities):
        community_map[idx] = sorted(list(community))
        print(f"  Community {idx}: {community_map[idx]}")
    
    # Also tag nodes with their community
    for comm_id, members in community_map.items():
        for member in members:
            G.nodes[member]["community"] = comm_id
    
    return community_map


# ============================================================
# STEP 5: Generate Community Summaries (LLM)
# ============================================================

SUMMARY_PROMPT = """You are summarizing a cluster of related IT infrastructure entities for a knowledge base.

Given these entities and their relationships, write a clear 3-5 sentence summary that captures:
1. What this cluster is about (the theme)
2. Key entities and their roles
3. Important dependencies or risks

Entities in this community:
{entity_details}

Relationships within this community:
{relationship_details}

Write ONLY the summary paragraph, nothing else.
"""

def generate_community_summaries(G, community_map: dict, llm_call_fn) -> dict:
    """
    Generate a natural language summary for each community.
    These summaries are what Global Search uses.
    """
    summaries = {}
    
    for comm_id, members in community_map.items():
        # Gather entity details
        entity_details = []
        for member in members:
            node_data = G.nodes[member]
            entity_details.append(
                f"- {member} (type: {node_data.get('type', 'unknown')}): {node_data.get('description', 'N/A')}"
            )
        
        # Gather relationship details (edges within community)
        rel_details = []
        for m1 in members:
            for m2 in members:
                if G.has_edge(m1, m2):
                    edge = G[m1][m2]
                    rel_types = ", ".join(edge.get("types", ["related"]))
                    rel_details.append(f"- {m1} --[{rel_types}]--> {m2}")
        
        prompt = SUMMARY_PROMPT.replace(
            "{entity_details}", "\n".join(entity_details)
        ).replace(
            "{relationship_details}", "\n".join(rel_details) if rel_details else "No direct relationships within this cluster."
        )
        
        summary = llm_call_fn(prompt)
        summaries[comm_id] = summary.strip()
        print(f"  Community {comm_id} summary generated ({len(summary)} chars)")
    
    return summaries


# ============================================================
# STEP 6: Search - Local and Global
# ============================================================

LOCAL_SEARCH_PROMPT = """You are an IT support assistant. Answer the question using ONLY the provided context.

Question: {question}

Relevant Entity: {entity_name}
Entity Type: {entity_type}
Entity Description: {entity_description}

Connected Entities (Neighbors):
{neighbor_details}

Direct Relationships:
{relationship_details}

Answer the question concisely based on this graph context. If the information isn't available, say so.
"""

def local_search(G, question: str, llm_call_fn) -> str:
    """
    Local Search: Find the most relevant entity, gather its neighborhood,
    and use LLM to answer.
    """
    # Step 1: Use LLM to identify the key entity in the question
    entity_names = list(G.nodes())
    identify_prompt = f"""Given this question: "{question}"
And these available entities: {json.dumps(entity_names)}
Which entity is most relevant? Return ONLY the entity name, nothing else."""
    
    target_entity = llm_call_fn(identify_prompt).strip().strip('"')
    
    if target_entity not in G.nodes:
        # Fuzzy match - find closest
        target_entity = min(entity_names, key=lambda x: _string_distance(x.lower(), target_entity.lower()))
    
    print(f"  Local Search targeting entity: {target_entity}")
    
    # Step 2: Gather neighborhood
    node_data = G.nodes[target_entity]
    neighbors = list(G.neighbors(target_entity))
    
    neighbor_details = []
    relationship_details = []
    for neighbor in neighbors:
        n_data = G.nodes[neighbor]
        neighbor_details.append(
            f"- {neighbor} (type: {n_data.get('type', 'unknown')}): {n_data.get('description', 'N/A')}"
        )
        edge = G[target_entity][neighbor]
        rel_types = ", ".join(edge.get("types", ["related"]))
        descs = " | ".join(edge.get("descriptions", []))
        relationship_details.append(f"- {target_entity} --[{rel_types}]--> {neighbor}: {descs}")
    
    # Step 3: Send to LLM
    prompt = LOCAL_SEARCH_PROMPT.replace("{question}", question)\
        .replace("{entity_name}", target_entity)\
        .replace("{entity_type}", node_data.get("type", "unknown"))\
        .replace("{entity_description}", node_data.get("description", "N/A"))\
        .replace("{neighbor_details}", "\n".join(neighbor_details))\
        .replace("{relationship_details}", "\n".join(relationship_details))
    
    return llm_call_fn(prompt)


GLOBAL_SEARCH_PROMPT = """You are an IT infrastructure analyst. Answer the question using the community summaries below.
These summaries represent different clusters of related systems and teams in our infrastructure.

Question: {question}

Community Summaries:
{all_summaries}

Provide a comprehensive answer that synthesizes information across all relevant communities. 
If the information isn't fully available, acknowledge what's missing.
"""

def global_search(community_summaries: dict, question: str, llm_call_fn) -> str:
    """
    Global Search: Use pre-computed community summaries to answer
    broad/summary questions.
    """
    all_summaries = []
    for comm_id, summary in community_summaries.items():
        all_summaries.append(f"### Cluster {comm_id}:\n{summary}")
    
    prompt = GLOBAL_SEARCH_PROMPT.replace("{question}", question)\
        .replace("{all_summaries}", "\n\n".join(all_summaries))
    
    return llm_call_fn(prompt)


def _string_distance(a: str, b: str) -> int:
    """Simple string distance for fuzzy matching."""
    if a == b:
        return 0
    if a in b or b in a:
        return 1
    return abs(len(a) - len(b)) + sum(1 for ca, cb in zip(a, b) if ca != cb)


# ============================================================
# STEP 7: Visualization (Optional - for debugging)
# ============================================================

def export_graph_data(G, community_map: dict, community_summaries: dict, output_path: str):
    """Export graph data to JSON for visualization."""
    nodes = []
    for name, data in G.nodes(data=True):
        nodes.append({
            "id": name,
            "type": data.get("type", "unknown"),
            "description": data.get("description", ""),
            "community": data.get("community", -1)
        })
    
    edges = []
    for source, target, data in G.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "types": data.get("types", []),
            "descriptions": data.get("descriptions", [])
        })
    
    output = {
        "nodes": nodes,
        "edges": edges,
        "communities": {str(k): v for k, v in community_map.items()},
        "community_summaries": {str(k): v for k, v in community_summaries.items()}
    }
    
    Path(output_path).write_text(json.dumps(output, indent=2))
    print(f"\n  Graph data exported to {output_path}")
    return output


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(data_dir: str, llm_call_fn, output_dir: str = None):
    """
    Run the complete GraphRAG pipeline.
    
    Args:
        data_dir: Directory containing markdown documents
        llm_call_fn: Function that takes a prompt and returns LLM response
        output_dir: Optional directory to save graph data
    """
    print("=" * 60)
    print("GRAPHRAG MINI PIPELINE")
    print("=" * 60)
    
    # Step 1: Load documents
    print("\n[Step 1] Loading documents...")
    docs = load_documents(data_dir)
    print(f"  Total: {len(docs)} documents loaded")
    
    # Step 2: Extract entities and relationships
    print("\n[Step 2] Extracting entities & relationships (LLM calls)...")
    all_extractions = []
    for doc in docs:
        print(f"\n  Processing: {doc['filename']}...")
        extraction = extract_entities_and_relationships(doc, llm_call_fn)
        all_extractions.append(extraction)
    
    # Step 3: Build graph
    print("\n[Step 3] Building knowledge graph...")
    G = build_graph(all_extractions)
    
    # Step 4: Detect communities
    print("\n[Step 4] Detecting communities...")
    community_map = detect_communities(G)
    print(f"  Total: {len(community_map)} communities detected")
    
    # Step 5: Generate community summaries
    print("\n[Step 5] Generating community summaries (LLM calls)...")
    community_summaries = generate_community_summaries(G, community_map, llm_call_fn)
    
    # Export graph data
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        export_graph_data(G, community_map, community_summaries, f"{output_dir}/graph_data.json")
    
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")
    print(f"  Communities: {len(community_map)}")
    print("=" * 60)
    
    return G, community_map, community_summaries


# ============================================================
# DEMO MODE (uses mock LLM for testing without API key)
# ============================================================

def mock_llm_call(prompt: str) -> str:
    """
    Mock LLM that returns pre-built extractions.
    Use this to test the pipeline without an API key.
    """
    if "Payment Service Playbook" in prompt and "extract" in prompt.lower():
        return json.dumps({
            "entities": [
                {"name": "Payment Service", "type": "service", "description": "Critical Tier-1 microservice (pay-svc) handling payment transactions on port 8443"},
                {"name": "Payments Team", "type": "team", "description": "Team responsible for Payment Service"},
                {"name": "Sarah Chen", "type": "person", "description": "Lead of Payments Team"},
                {"name": "payments-db", "type": "database", "description": "PostgreSQL primary data store on AWS RDS db-prod-payments"},
                {"name": "payments-cache", "type": "infrastructure", "description": "Redis cache for session and transaction caching"},
                {"name": "User Service", "type": "service", "description": "Service for customer authentication and profile lookup (user-svc)"},
                {"name": "Notification Service", "type": "service", "description": "Sends payment confirmations via email and SMS (notify-svc)"},
                {"name": "Stripe API", "type": "tool", "description": "External payment gateway for credit card processing"},
                {"name": "Database Team", "type": "team", "description": "Team managing PostgreSQL databases"},
                {"name": "Priya Patel", "type": "person", "description": "Lead of Database Team"},
                {"name": "Platform Team", "type": "team", "description": "Team managing shared infrastructure (Redis, Kafka, K8s)"},
                {"name": "James Wilson", "type": "person", "description": "Lead of Platform Team"},
                {"name": "Identity Team", "type": "team", "description": "Team responsible for User Service"},
                {"name": "Marcus Johnson", "type": "person", "description": "Lead of Identity Team"},
                {"name": "Communications Team", "type": "team", "description": "Team responsible for Notification Service"},
                {"name": "Ana Rodriguez", "type": "person", "description": "Lead of Communications Team"},
                {"name": "Datadog", "type": "tool", "description": "Monitoring platform - dashboard: Payment Service Overview"},
                {"name": "PagerDuty", "type": "tool", "description": "Alert routing to payments-oncall rotation"},
                {"name": "prod-east-1", "type": "infrastructure", "description": "Kubernetes cluster in production"}
            ],
            "relationships": [
                {"source": "Payments Team", "target": "Payment Service", "type": "owns", "description": "Payments Team owns and operates Payment Service"},
                {"source": "Sarah Chen", "target": "Payments Team", "type": "leads", "description": "Sarah Chen leads the Payments Team"},
                {"source": "Payment Service", "target": "payments-db", "type": "depends_on", "description": "Primary data store for payment transactions"},
                {"source": "Payment Service", "target": "payments-cache", "type": "depends_on", "description": "Redis cache for transaction caching"},
                {"source": "Payment Service", "target": "User Service", "type": "depends_on", "description": "For customer authentication and profile lookup"},
                {"source": "Payment Service", "target": "Notification Service", "type": "depends_on", "description": "Sends payment confirmation emails and SMS"},
                {"source": "Payment Service", "target": "Stripe API", "type": "depends_on", "description": "External payment gateway"},
                {"source": "Database Team", "target": "payments-db", "type": "manages", "description": "Database Team manages the payments database"},
                {"source": "Priya Patel", "target": "Database Team", "type": "leads", "description": "Priya Patel leads the Database Team"},
                {"source": "Platform Team", "target": "payments-cache", "type": "manages", "description": "Platform Team manages Redis infrastructure"},
                {"source": "James Wilson", "target": "Platform Team", "type": "leads", "description": "James Wilson leads the Platform Team"},
                {"source": "Payment Service", "target": "prod-east-1", "type": "deployed_on", "description": "Deployed on production Kubernetes cluster"},
                {"source": "Datadog", "target": "Payment Service", "type": "monitors", "description": "Monitors transaction success rate, latency, error rate"},
                {"source": "PagerDuty", "target": "Payment Service", "type": "monitors", "description": "Alert routing for payment service incidents"}
            ]
        })
    
    elif "User Service Playbook" in prompt and "extract" in prompt.lower():
        return json.dumps({
            "entities": [
                {"name": "User Service", "type": "service", "description": "Tier-1 microservice (user-svc) for auth, authorization, profile management on port 8080"},
                {"name": "Identity Team", "type": "team", "description": "Team responsible for User Service"},
                {"name": "Marcus Johnson", "type": "person", "description": "Lead of Identity Team"},
                {"name": "users-db", "type": "database", "description": "PostgreSQL database for user profiles on AWS RDS db-prod-users"},
                {"name": "session-cache", "type": "infrastructure", "description": "Redis cluster for active user sessions"},
                {"name": "Auth0", "type": "tool", "description": "External identity provider for OAuth2/OIDC"},
                {"name": "Audit Service", "type": "service", "description": "Logs authentication events for compliance (audit-svc)"},
                {"name": "Compliance Team", "type": "team", "description": "Team responsible for Audit Service"},
                {"name": "David Kim", "type": "person", "description": "Lead of Compliance Team"},
                {"name": "Order Service", "type": "service", "description": "Retrieves user profiles for order processing (order-svc)"},
                {"name": "Admin Portal", "type": "service", "description": "Staff authentication and RBAC (admin-web)"},
                {"name": "Payment Service", "type": "service", "description": "Calls user-svc for customer verification"}
            ],
            "relationships": [
                {"source": "Identity Team", "target": "User Service", "type": "owns", "description": "Identity Team owns User Service"},
                {"source": "Marcus Johnson", "target": "Identity Team", "type": "leads", "description": "Marcus Johnson leads Identity Team"},
                {"source": "User Service", "target": "users-db", "type": "depends_on", "description": "Primary data store for user profiles"},
                {"source": "User Service", "target": "session-cache", "type": "depends_on", "description": "Redis for session management"},
                {"source": "User Service", "target": "Auth0", "type": "depends_on", "description": "External identity provider"},
                {"source": "User Service", "target": "Audit Service", "type": "depends_on", "description": "Logs auth events for compliance"},
                {"source": "Compliance Team", "target": "Audit Service", "type": "owns", "description": "Compliance Team owns Audit Service"},
                {"source": "David Kim", "target": "Compliance Team", "type": "leads", "description": "David Kim leads Compliance Team"},
                {"source": "Payment Service", "target": "User Service", "type": "depends_on", "description": "Customer verification before payments"},
                {"source": "Order Service", "target": "User Service", "type": "depends_on", "description": "User profile retrieval for orders"},
                {"source": "Admin Portal", "target": "User Service", "type": "depends_on", "description": "Staff auth and RBAC"},
                {"source": "Platform Team", "target": "session-cache", "type": "manages", "description": "Platform Team manages Redis infrastructure"},
                {"source": "Database Team", "target": "users-db", "type": "manages", "description": "Database Team manages user database"}
            ]
        })
    
    elif "Order Service Playbook" in prompt and "extract" in prompt.lower():
        return json.dumps({
            "entities": [
                {"name": "Order Service", "type": "service", "description": "Tier-1 microservice (order-svc) for order lifecycle on port 8081"},
                {"name": "Commerce Team", "type": "team", "description": "Team responsible for Order Service"},
                {"name": "Lisa Wang", "type": "person", "description": "Lead of Commerce Team"},
                {"name": "orders-db", "type": "database", "description": "PostgreSQL database for order records on AWS RDS db-prod-orders"},
                {"name": "Inventory Service", "type": "service", "description": "Stock availability and reservation (inventory-svc)"},
                {"name": "Warehouse Team", "type": "team", "description": "Team responsible for Inventory Service"},
                {"name": "Tom Richards", "type": "person", "description": "Lead of Warehouse Team"},
                {"name": "Kafka", "type": "infrastructure", "description": "Event bus (events-broker) for order state change events"},
                {"name": "Notification Service", "type": "service", "description": "Sends order confirmations and shipping updates"}
            ],
            "relationships": [
                {"source": "Commerce Team", "target": "Order Service", "type": "owns", "description": "Commerce Team owns Order Service"},
                {"source": "Lisa Wang", "target": "Commerce Team", "type": "leads", "description": "Lisa Wang leads Commerce Team"},
                {"source": "Order Service", "target": "User Service", "type": "depends_on", "description": "User profile and address retrieval"},
                {"source": "Order Service", "target": "Payment Service", "type": "depends_on", "description": "Payment processing during checkout"},
                {"source": "Order Service", "target": "orders-db", "type": "depends_on", "description": "Primary data store for orders"},
                {"source": "Order Service", "target": "Inventory Service", "type": "depends_on", "description": "Stock checks and reservation"},
                {"source": "Order Service", "target": "Notification Service", "type": "depends_on", "description": "Order confirmations and updates"},
                {"source": "Order Service", "target": "Kafka", "type": "depends_on", "description": "Event publishing for order state changes"},
                {"source": "Warehouse Team", "target": "Inventory Service", "type": "owns", "description": "Warehouse Team owns Inventory Service"},
                {"source": "Tom Richards", "target": "Warehouse Team", "type": "leads", "description": "Tom Richards leads Warehouse Team"},
                {"source": "Platform Team", "target": "Kafka", "type": "manages", "description": "Platform Team manages Kafka"},
                {"source": "Database Team", "target": "orders-db", "type": "manages", "description": "Database Team manages orders database"}
            ]
        })
    
    elif "Platform Infrastructure" in prompt and "extract" in prompt.lower():
        return json.dumps({
            "entities": [
                {"name": "Platform Team", "type": "team", "description": "Manages shared infra: K8s, Redis, Kafka, CI/CD"},
                {"name": "James Wilson", "type": "person", "description": "Lead of Platform Team"},
                {"name": "prod-east-1", "type": "infrastructure", "description": "Kubernetes cluster with 24 m5.2xlarge worker nodes in us-east-1"},
                {"name": "Kafka", "type": "infrastructure", "description": "5-broker event bus cluster running Kafka 3.5"},
                {"name": "payments-cache", "type": "infrastructure", "description": "Dedicated Redis cluster, 3 nodes, 64GB each"},
                {"name": "session-cache", "type": "infrastructure", "description": "Dedicated Redis cluster, 3 nodes, 32GB each"},
                {"name": "general-cache", "type": "infrastructure", "description": "Shared Redis instance, single node, 16GB"},
                {"name": "Database Team", "type": "team", "description": "Manages all PostgreSQL instances"},
                {"name": "Priya Patel", "type": "person", "description": "Lead of Database Team"},
                {"name": "payments-db", "type": "database", "description": "Payment Service DB, Multi-AZ"},
                {"name": "users-db", "type": "database", "description": "User Service DB, Multi-AZ with read replica"},
                {"name": "orders-db", "type": "database", "description": "Order Service DB, Multi-AZ with read replica"},
                {"name": "Istio", "type": "tool", "description": "Service mesh for inter-service mTLS communication"},
                {"name": "NGINX", "type": "tool", "description": "Ingress controller with TLS termination"}
            ],
            "relationships": [
                {"source": "James Wilson", "target": "Platform Team", "type": "leads", "description": "James Wilson leads Platform Team"},
                {"source": "Platform Team", "target": "prod-east-1", "type": "manages", "description": "Platform Team manages K8s cluster"},
                {"source": "Platform Team", "target": "Kafka", "type": "manages", "description": "Platform Team manages Kafka brokers"},
                {"source": "Platform Team", "target": "payments-cache", "type": "manages", "description": "Platform Team manages payments Redis"},
                {"source": "Platform Team", "target": "session-cache", "type": "manages", "description": "Platform Team manages session Redis"},
                {"source": "Platform Team", "target": "general-cache", "type": "manages", "description": "Platform Team manages shared Redis"},
                {"source": "Priya Patel", "target": "Database Team", "type": "leads", "description": "Priya Patel leads Database Team"},
                {"source": "Database Team", "target": "payments-db", "type": "manages", "description": "Manages payments database"},
                {"source": "Database Team", "target": "users-db", "type": "manages", "description": "Manages users database"},
                {"source": "Database Team", "target": "orders-db", "type": "manages", "description": "Manages orders database"},
                {"source": "prod-east-1", "target": "Istio", "type": "uses", "description": "K8s cluster uses Istio service mesh"},
                {"source": "prod-east-1", "target": "NGINX", "type": "uses", "description": "K8s cluster uses NGINX ingress"}
            ]
        })
    
    elif "community" in prompt.lower() and "summar" in prompt.lower():
        # Return a mock community summary
        if "Payment Service" in prompt:
            return "This cluster represents the core payment processing infrastructure. Payment Service (pay-svc) is the central Tier-1 service owned by Sarah Chen's Payments Team, handling all transaction processing on port 8443. It critically depends on payments-db (PostgreSQL on AWS RDS) managed by Priya Patel's Database Team, and payments-cache (Redis) managed by James Wilson's Platform Team. The Stripe API provides external payment gateway functionality. Key risk: Payment Service failure cascades to order processing since Order Service depends on it for checkout."
        elif "User Service" in prompt:
            return "This cluster covers user identity and authentication infrastructure. User Service (user-svc), owned by Marcus Johnson's Identity Team, is the highest-uptime service (99.99% SLA) providing auth, authorization, and session management. It depends on users-db, session-cache (Redis), and Auth0 for external identity. The Audit Service, owned by David Kim's Compliance Team, logs all auth events. Critical risk: User Service is an upstream dependency for Payment Service, Order Service, and Admin Portal — an outage here cascades to nearly all customer-facing operations."
        elif "Order Service" in prompt or "Inventory" in prompt:
            return "This cluster covers the commerce and fulfillment pipeline. Order Service (order-svc), led by Lisa Wang's Commerce Team, orchestrates the complete order lifecycle including payment, inventory, and notifications. It depends on both User Service and Payment Service upstream, and Inventory Service (owned by Tom Richards' Warehouse Team) for stock management. Kafka serves as the event bus for order state changes. Key risk: This is the most dependency-heavy service — failures in User Service, Payment Service, or Inventory Service all block order creation."
        else:
            return "This cluster contains shared platform infrastructure managed by James Wilson's Platform Team and Priya Patel's Database Team. Components include the prod-east-1 Kubernetes cluster (24 nodes), Kafka event broker (5 brokers), multiple Redis instances (payments-cache, session-cache, general-cache), and PostgreSQL databases. Istio service mesh provides mTLS between services. Key risk: Platform Team components are foundational — Kafka or Kubernetes failures affect every service in the system."
    
    elif "most relevant" in prompt.lower() or "which entity" in prompt.lower():
        # Entity identification for local search
        if "payment" in prompt.lower() or "pay" in prompt.lower():
            return "Payment Service"
        elif "user" in prompt.lower() or "auth" in prompt.lower() or "login" in prompt.lower():
            return "User Service"
        elif "order" in prompt.lower():
            return "Order Service"
        elif "database" in prompt.lower() or "priya" in prompt.lower():
            return "Database Team"
        elif "kafka" in prompt.lower() or "event" in prompt.lower():
            return "Kafka"
        elif "platform" in prompt.lower() or "james" in prompt.lower():
            return "Platform Team"
        else:
            return "Payment Service"  # default
    
    else:
        # Generic answer for search queries
        return "Based on the provided context, I can see the relationships and dependencies. The system involves multiple interconnected services, teams, and infrastructure components. Please refer to the specific entity details and relationships for accurate information."


if __name__ == "__main__":
    print("\nRunning GraphRAG Mini Pipeline with MOCK LLM...\n")
    
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    
    # Run pipeline with mock LLM
    G, community_map, community_summaries = run_pipeline(
        data_dir=data_dir,
        llm_call_fn=mock_llm_call,
        output_dir=output_dir
    )
    
    # Demo queries
    print("\n" + "=" * 60)
    print("DEMO QUERIES")
    print("=" * 60)
    
    # Local Search Demo
    print("\n--- LOCAL SEARCH ---")
    question1 = "What does Payment Service depend on?"
    print(f"\nQ: {question1}")
    answer1 = local_search(G, question1, mock_llm_call)
    print(f"A: {answer1}")
    
    # Global Search Demo
    print("\n--- GLOBAL SEARCH ---")
    question2 = "What are the main infrastructure risks across our system?"
    print(f"\nQ: {question2}")
    answer2 = global_search(community_summaries, question2, mock_llm_call)
    print(f"A: {answer2}")
