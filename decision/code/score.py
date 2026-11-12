# -*- coding: utf-8 -*-
"""Score results/r*/<model>/<id>.json against expect keys. Writes summary.json and prints tables.
Prediction rules:
  choice -> answer['choice']
  noul   -> noul >= 0.5
  score  -> argmax of probabilities (level index); also keeps the expected-value 'score'
Confidence used for calibration: answer['confidence'] if present, else max(noul, 1-noul) for noul.
A question whose expect is None is not scored.
"""
import glob, json, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run import all_cases  # noqa

MODELS = ["gemini", "jev"]


def pred_of(ans):
    t = ans["type"]
    if t == "choice":
        return ans["choice"]
    if t == "noul":
        return ans["noul"] >= 0.5
    if t == "score":
        p = ans["probabilities"]
        return int(max(p, key=lambda k: p[k]))
    raise ValueError(t)


def conf_of(ans):
    if ans.get("confidence") is not None:
        return float(ans["confidence"])
    if ans["type"] == "noul":
        return max(ans["noul"], 1 - ans["noul"])
    return None


def top_prob(ans):
    if ans["type"] == "noul":
        return max(ans["noul"], 1 - ans["noul"])
    return max(ans["probabilities"].values())


def is_ok(pred, exp, qtype):
    if isinstance(exp, list):
        return pred in exp
    return pred == exp


def main():
    cases = {c["id"]: c for c in all_cases()}
    rows = []  # one row per (model, repeat, case, question)
    lat = defaultdict(list)
    toks = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(HERE, "results", "r*", "*", "*.json"))):
        d = json.load(open(path))
        rep = path.split(os.sep)[-3]
        c = cases.get(d["id"])
        if not c:
            continue
        lat[(d["model"], c["suite"])].append(d["latency"])
        u = d["response"].get("usage", {})
        toks[d["model"]].append(u.get("total_input_tokens", u.get("input_tokens", 0)))
        for q, exp in c["expect"].items():
            ans = d["response"]["answers"].get(q)
            if ans is None:
                rows.append(dict(model=d["model"], rep=rep, id=c["id"], suite=c["suite"], q=q, missing=True))
                continue
            p = pred_of(ans)
            r = dict(model=d["model"], rep=rep, id=c["id"], suite=c["suite"], q=q, qtype=ans["type"], pred=p,
                     exp=exp, conf=conf_of(ans), top=top_prob(ans), ambiguous=bool(c.get("ambiguous")))
            if ans["type"] == "score":
                r["ev"] = ans["score"]
            if exp is not None:
                r["ok"] = is_ok(p, exp, ans["type"])
                if ans["type"] == "score":
                    e = exp if isinstance(exp, list) else [exp]
                    r["within1"] = min(abs(p - x) for x in e) <= 1
            rows.append(r)

    summ = {"by_suite": {}, "latency": {}, "tokens": {}, "calibration": {}, "stability": {}, "cases": {}}
    suites = sorted({r["suite"] for r in rows})
    for m in MODELS:
        for s in suites:
            rs = [r for r in rows if r["model"] == m and r["suite"] == s and "ok" in r]
            if not rs:
                continue
            reps = sorted({r["rep"] for r in rs})
            summ["by_suite"].setdefault(s, {})[m] = dict(
                acc=sum(r["ok"] for r in rs) / len(rs), n=len(rs) // max(1, len(reps)), reps=len(reps),
                within1=(lambda w: sum(w) / len(w) if w else None)([r["within1"] for r in rs if "within1" in r]),
                conf_ok=statistics.mean([r["conf"] for r in rs if r["ok"] and r["conf"] is not None] or [0]),
                conf_bad=statistics.mean([r["conf"] for r in rs if not r["ok"] and r["conf"] is not None] or [0]),
            )
            L = lat[(m, s)]
            summ["latency"].setdefault(s, {})[m] = dict(median=statistics.median(L), mean=statistics.mean(L)) if L else None
        allrs = [r for r in rows if r["model"] == m and "ok" in r and r["conf"] is not None]
        bins = defaultdict(list)
        for r in allrs:
            bins[min(9, int(r["conf"] * 10))].append(r)
        ece = sum(len(b) / len(allrs) * abs(statistics.mean(x["conf"] for x in b) - statistics.mean(x["ok"] for x in b)) for b in bins.values()) if allrs else None
        summ["calibration"][m] = dict(
            n=len(allrs), acc=statistics.mean(r["ok"] for r in allrs) if allrs else None, ece=ece,
            bins={k: dict(n=len(b), conf=statistics.mean(x["conf"] for x in b), acc=statistics.mean(x["ok"] for x in b)) for k, b in sorted(bins.items())},
        )
        T = toks[m]
        summ["tokens"][m] = dict(calls=len(T), total=sum(T), mean=statistics.mean(T) if T else 0)
        # stability: same prediction in every repeat
        g = defaultdict(set)
        for r in rows:
            if r["model"] == m and "pred" in r:
                g[(r["id"], r["q"])].add(str(r["pred"]))
        summ["stability"][m] = dict(items=len(g), stable=sum(len(v) == 1 for v in g.values()),
                                    unstable=sorted(f"{k[0]}.{k[1]}" for k, v in g.items() if len(v) > 1))
    # per-case table (repeat r1 only for readability, plus agreement across reps)
    for r in rows:
        if "pred" not in r:
            continue
        key = f"{r['id']}.{r['q']}"
        e = summ["cases"].setdefault(key, dict(suite=r["suite"], exp=r["exp"], ambiguous=r["ambiguous"]))
        e.setdefault(r["model"], []).append(dict(rep=r["rep"], pred=r["pred"], conf=r["conf"], top=r["top"], ok=r.get("ok"), ev=r.get("ev")))
    json.dump(summ, open(os.path.join(HERE, "summary.json"), "w"), ensure_ascii=False, indent=1, default=str)

    print(f"{'suite':14} {'model':7} {'acc':>6} {'±1':>6} {'n':>4} {'conf✓':>6} {'conf✗':>6} {'lat(med)':>9}")
    for s in suites:
        for m in MODELS:
            b = summ["by_suite"].get(s, {}).get(m)
            if not b:
                continue
            L = summ["latency"][s][m]
            w = f"{b['within1']:.0%}" if b["within1"] is not None else "-"
            print(f"{s:14} {m:7} {b['acc']:6.0%} {w:>6} {b['n']:4} {b['conf_ok']:6.2f} {b['conf_bad']:6.2f} {L['median']:8.2f}s")
    for m in MODELS:
        c = summ["calibration"][m]
        print(m, "overall acc", f"{c['acc']:.1%}" if c["acc"] is not None else "-", "ECE", f"{c['ece']:.3f}" if c["ece"] is not None else "-",
              "| stable", summ["stability"][m]["stable"], "/", summ["stability"][m]["items"], "| tokens", summ["tokens"][m])
    print("unstable:", {m: summ["stability"][m]["unstable"] for m in MODELS})
    print("\nWRONG (any repeat):")
    for k, e in summ["cases"].items():
        bad = {m: [(x["pred"], round(x["conf"] or 0, 2)) for x in e.get(m, []) if x["ok"] is False] for m in MODELS}
        if any(bad.values()):
            print(f"  {k:22} exp={e['exp']}  " + "  ".join(f"{m}:{v}" for m, v in bad.items() if v))


if __name__ == "__main__":
    main()
