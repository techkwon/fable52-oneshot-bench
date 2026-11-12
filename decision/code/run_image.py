# -*- coding: utf-8 -*-
"""Bonus: grade photographed handwritten answers (image input). Same rubric as exam_essay."""
import base64, json, os, sys, time, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import run, cases_teacher as T
EXP = {"hw1": 3, "hw2": 2, "hw3": 1, "hw4": 0}
Q = {"points": {"type": "score", "instructions": "사진 속 학생의 손글씨 답안을 채점 기준표에 따라 채점하세요.", "criteria": T.ESSAY_RUBRIC}}
def post(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json", **headers})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, time.perf_counter() - t0, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, time.perf_counter() - t0, e.read().decode(errors="replace")
os.makedirs(os.path.join(HERE, "results", "image"), exist_ok=True)
for k, exp in EXP.items():
    b64 = base64.b64encode(open(os.path.join(HERE, "img", k + ".png"), "rb").read()).decode()
    stem = T.ESSAY_STEM + "\n[학생 답안] 아래 사진의 손글씨"
    g = post("https://generativelanguage.googleapis.com/v1beta/decisions", {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
             {"model": "gemini-decision-1", "input": [{"type": "text", "text": stem}, {"type": "image", "data": b64, "mime_type": "image/png"}], "questions": Q})
    ref = "asset-" + k + "-answer-photo"
    JQ = {"points": dict(Q["points"], instructions="`photo`에 찍힌 학생의 손글씨 답안을 `question`의 채점 기준표에 따라 채점하세요.")}
    j = post("https://api.typesafe.ai/v1/systemone", {"Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"], "TypeSafe-Danger-Zone-Images": "true"},
             {"model": "jev-1.14.0", "state": {"question": stem, "photo": ref},
              "assets": {ref: {"type": "image", "format": "png", "data_base64": b64}}, "questions": JQ})
    out = {"expect": exp, "gemini": g, "jev": j}
    json.dump(out, open(os.path.join(HERE, "results", "image", k + ".json"), "w"), ensure_ascii=False, indent=1)
    for name, (st, lat, body) in (("gemini", g), ("jev", j)):
        if st == 200:
            a = body["answers"]["points"]; p = a["probabilities"]
            print(k, "exp", exp, name, "pred", max(p, key=p.get), {x: round(v, 2) for x, v in p.items()}, "lat", round(lat, 2))
        else:
            print(k, name, "HTTP", st, str(body)[:300])
