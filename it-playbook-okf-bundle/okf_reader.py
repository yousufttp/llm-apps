"""
okf_reader.py

A minimal OKF (Open Knowledge Format) bundle parser and query tool.

What this teaches:
  1. Parsing YAML frontmatter + markdown body (the OKF concept doc shape)
  2. Building a knowledge GRAPH from markdown links between concepts
     (this is the part plain "folder of markdown" doesn't give you for free)
  3. A simple keyword-based retrieval over that graph
     (stand-in for what a real RAG pipeline would do with embeddings)

Usage:
  python okf_reader.py runbooks graph          -> print the concept graph
  python okf_reader.py runbooks query "ays"    -> find + expand related concepts
"""

import sys
import os
import re
import json

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)\)")


def parse_frontmatter(text):
    """Very small YAML-ish parser: good enough for flat key: value and key: [a, b] lists."""
    fm = {}
    for line in text.strip().splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip() for v in value[1:-1].split(",") if v.strip()]
            fm[key] = items
        else:
            fm[key] = value
    return fm


def load_bundle(root_dir):
    """Walk the directory, parse every .md file into a concept node."""
    concepts = {}
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            full_path = os.path.join(dirpath, fname)
            rel_path = "/" + os.path.relpath(full_path, root_dir).replace(os.sep, "/")

            with open(full_path, "r", encoding="utf-8") as f:
                raw = f.read()

            match = FRONTMATTER_RE.match(raw)
            if not match:
                continue  # not a valid OKF concept doc

            frontmatter_text, body = match.groups()
            fm = parse_frontmatter(frontmatter_text)

            # Extract outgoing links -> this is the "graph" part of OKF
            links = [target for _, target in LINK_RE.findall(body)]

            concepts[rel_path] = {
                "path": rel_path,
                "type": fm.get("type", "Unknown"),
                "title": fm.get("title", fname),
                "description": fm.get("description", ""),
                "tags": fm.get("tags", []),
                "links": links,
                "body": body.strip(),
            }
    return concepts


def print_graph(concepts):
    for path, node in concepts.items():
        print(f"{node['title']}  [{node['type']}]  ({path})")
        for tag in node["tags"]:
            pass
        if node["tags"]:
            print(f"  tags: {', '.join(node['tags'])}")
        for link in node["links"]:
            target_title = concepts.get(link, {}).get("title", link)
            print(f"  -> links to: {target_title}")
        print()


def query(concepts, keyword, hops=1):
    """
    Simple keyword search over title/description/tags/body,
    then expand `hops` steps along the link graph.
    This mimics what a real retriever + graph-expansion RAG step does,
    minus the embeddings.
    """
    keyword = keyword.lower()
    matched = set()

    for path, node in concepts.items():
        haystack = " ".join([
            node["title"], node["description"],
            " ".join(node["tags"]), node["body"]
        ]).lower()
        if keyword in haystack:
            matched.add(path)

    # expand via graph links
    frontier = set(matched)
    for _ in range(hops):
        next_frontier = set()
        for path in frontier:
            for link in concepts.get(path, {}).get("links", []):
                if link in concepts:
                    next_frontier.add(link)
        matched |= next_frontier
        frontier = next_frontier

    print(f"Query: '{keyword}' (expanded {hops} hop(s) through links)\n")
    for path in matched:
        node = concepts[path]
        print(f"- {node['title']}  [{node['type']}]  ({path})")
    print(f"\n{len(matched)} concept(s) found. In a real RAG pipeline, "
          f"these concept bodies would now be fed into the LLM's context window.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    root_dir = sys.argv[1]
    command = sys.argv[2]
    concepts = load_bundle(root_dir)

    if command == "graph":
        print_graph(concepts)
    elif command == "query":
        keyword = sys.argv[3] if len(sys.argv) > 3 else ""
        query(concepts, keyword)
    else:
        print(f"Unknown command: {command}")
