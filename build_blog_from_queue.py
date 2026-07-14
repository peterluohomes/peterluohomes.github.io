#!/usr/bin/env python3
"""Reads queue.json, keeps posts that (a) are due and (b) target the blog,
then rebuilds /blog/en and /blog/zh via blog_gen. Run from the repo root."""
import os, json, datetime as dt
import blog_gen

QUEUE = os.environ.get("QUEUE_FILE", "queue.json")
SITE_ROOT = os.environ.get("SITE_ROOT", ".")

def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("posts", data) if isinstance(data, dict) else data

def is_due(p):
    raw = p.get("scheduledFor")
    if not raw:
        return True
    try:
        d = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return True
    return d <= dt.datetime.now(dt.timezone.utc)

def targets_blog(p):
    return any((t.get("platform") == "blog") for t in (p.get("targets") or []))

posts = [p for p in load(QUEUE) if targets_blog(p) and is_due(p)]
blog_gen.build_blog(posts, SITE_ROOT)
print(f"built /blog from {len(posts)} post(s)")
