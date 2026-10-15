"""服务冒烟测试（离线，不联网）：提交 selftest 任务→worker 跑→候选落库 pending 且带 source_url。"""
import os, tempfile, time
os.environ["HSS_DB"] = os.path.join(tempfile.mkdtemp(), "svc.db")
os.environ["HSS_INPROC_WORKER"] = "1"
from fastapi.testclient import TestClient
import service.app as app_mod
with TestClient(app_mod.app) as c:
    assert c.get("/health").json()["ok"]
    jid = c.post("/api/v1/crawl", json={"entry_url": "selftest:nwpu", "school_id": "1", "school_name": "示例大学", "deep": True}).json()["jobId"]
    for _ in range(50):
        j = c.get(f"/api/v1/crawl/{jid}").json()
        if j["status"] in ("done", "failed"): break
        time.sleep(0.1)
    assert j["status"] == "done", j
    assert j["candidate_count"] == 6, j
    cands = c.get("/api/v1/candidates", params={"status": "pending"}).json()["candidates"]
    assert len(cands) == 6, len(cands)
    assert all(x["source_url"] for x in cands), "候选必带原文地址"
    assert all(x["status"] == "pending" for x in cands), "一律人工审核：只产 pending"
    print(f"service smoke ok：job done，候选 {len(cands)} 条，均 pending 且带 source_url")
    print("  示例：", cands[0]["degree_type"], cands[0]["metric"], cands[0]["limit_pct"], cands[0]["source_url"])
