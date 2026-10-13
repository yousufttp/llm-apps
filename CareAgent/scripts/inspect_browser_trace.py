"""Summarize only CopilotKit request envelopes/statuses in local test traces (never headers)."""
import json
import zipfile
from pathlib import Path

for path in Path("frontend/test-results").glob("*/trace.zip"):
    print(path.parent.name)
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.endswith(".network"):
                continue
            for line in archive.read(name).splitlines():
                event = json.loads(line)
                snap = event.get("snapshot", {})
                req, res = snap.get("request", {}), snap.get("response", {})
                if "/api/copilotkit" in req.get("url", ""):
                    post = req.get("postData", {})
                    data = post.get("text", "")
                    if post.get("_file") in archive.namelist():
                        data = archive.read(post["_file"]).decode(errors="replace")
                    sha = post.get("_sha1")
                    if sha and "resources/" + sha in archive.namelist():
                        data = archive.read("resources/" + sha).decode(errors="replace")
                    print(req.get("method"), req.get("url"), res.get("status"), data[:1000])
                    sha = res.get("content", {}).get("_sha1")
                    file = res.get("content", {}).get("_file")
                    if file in archive.namelist():
                        print(archive.read(file).decode(errors="replace")[:1200])
                    if sha and "resources/" + sha in archive.namelist():
                        print(archive.read("resources/" + sha).decode(errors="replace")[:1200])
