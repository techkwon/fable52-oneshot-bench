# -*- coding: utf-8 -*-
"""Run every case on Gemini Decision 1 and TypeSafe Jev, same questions, same input text.
usage: python3 run.py [--repeat 3] [--suite hakpok,minwon,...] [--only id1,id2]
Writes results/r<k>/<model>/<id>.json  (raw response + latency + http status).
Already-existing result files are skipped (re-run safe).
"""
import argparse, json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

def load_env():
    for line in open(os.path.join(HERE, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

load_env()

def jev_questions(qs):
    """Jev uses {"true": .., "false": ..} for noul criteria; Gemini uses true_description/false_description."""
    out = {}
    for k, q in qs.items():
        q = dict(q)
        cr = q.get("criteria")
        if q["type"] == "noul" and isinstance(cr, dict) and "true_description" in cr:
            q["criteria"] = {"true": cr["true_description"], "false": cr["false_description"]}
        out[k] = q
    return out


MODELS = {
    "gemini": dict(url="https://generativelanguage.googleapis.com/v1beta/decisions",
                   headers=lambda: {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                   body=lambda c: {"model": "gemini-decision-1", "input": c["input"], "questions": c["questions"]}),
    "jev": dict(url="https://api.typesafe.ai/v1/systemone",
                headers=lambda: {"Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"]},
                body=lambda c: {"model": "jev-1.14.0", "state": c["input"], "questions": jev_questions(c["questions"])}),
}


def call(model, case):
    m = MODELS[model]
    data = json.dumps(m["body"](case), ensure_ascii=False).encode()
    req = urllib.request.Request(m["url"], data=data, method="POST",
                                 headers={"Content-Type": "application/json", **m["headers"]()})
    t0 = time.perf_counter()
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = json.loads(r.read().decode())
                return dict(status=r.status, latency=time.perf_counter() - t0, response=body, attempts=attempt + 1)
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 * (attempt + 1)); t0 = time.perf_counter(); continue
            try:
                txt = json.loads(txt)
            except Exception:
                pass
            return dict(status=e.code, latency=time.perf_counter() - t0, response=None, error=txt, attempts=attempt + 1)
        except Exception as e:  # network
            if attempt < 3:
                time.sleep(2); t0 = time.perf_counter(); continue
            return dict(status=0, latency=None, response=None, error=str(e), attempts=attempt + 1)


def all_cases():
    import cases_teacher
    out = cases_teacher.suites()
    try:
        import cases_web
        out = cases_web.suites() + out
    except ImportError:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--suite", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--models", default="gemini,jev")
    a = ap.parse_args()
    cases = all_cases()
    if a.suite:
        cases = [c for c in cases if c["suite"] in a.suite.split(",")]
    if a.only:
        cases = [c for c in cases if c["id"] in a.only.split(",")]
    jobs = []
    for k in range(1, a.repeat + 1):
        for model in a.models.split(","):
            for c in cases:
                path = os.path.join(HERE, "results", f"r{k}", model, c["id"] + ".json")
                if not os.path.exists(path):
                    jobs.append((path, model, c))
    print(f"{len(cases)} cases, {len(jobs)} calls to make")

    def work(job):
        path, model, c = job
        res = call(model, c)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        res.update(id=c["id"], suite=c["suite"], model=model)
        if res["status"] == 200:
            with open(path, "w") as f:
                json.dump(res, f, ensure_ascii=False, indent=1)
        return model, c["id"], res["status"], res.get("error")

    with ThreadPoolExecutor(4) as ex:
        for model, cid, st, err in ex.map(work, jobs):
            if st != 200:
                print("FAIL", model, cid, st, str(err)[:300])
    print("done")


if __name__ == "__main__":
    main()
