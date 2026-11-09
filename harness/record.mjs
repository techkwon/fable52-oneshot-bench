// usage: node record.mjs <file> <outdir> <seconds> [actions.json]
// Records a local HTML/SVG page with Chrome's screencast (JPEG frames + timestamps) and logs console errors.
import { createRequire } from "module";
import fs from "fs";
import path from "path";
const require = createRequire("<global node_modules>/");
const { chromium } = require("playwright");
const [file, outdir, secs, actionsFile] = process.argv.slice(2);
const W = 1280, H = 800;
fs.rmSync(outdir, { recursive: true, force: true });
fs.mkdirSync(path.join(outdir, "f"), { recursive: true });
const actions = actionsFile ? JSON.parse(fs.readFileSync(actionsFile, "utf8")) : [];
const browser = await chromium.launch({ channel: "chrome", headless: true, args: ["--autoplay-policy=no-user-gesture-required", "--enable-unsafe-swiftshader", "--use-angle=metal", "--enable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
const logs = [];
page.on("console", (m) => { if (["error", "warning"].includes(m.type())) logs.push(`[${m.type()}] ${m.text()}`.slice(0, 400)); });
page.on("pageerror", (e) => logs.push(`[pageerror] ${String(e).slice(0, 400)}`));
page.on("requestfailed", (r) => logs.push(`[requestfailed] ${r.url().slice(0, 200)}`));
const cdp = await ctx.newCDPSession(page);
const frames = []; let lastFrame = null;
let n = 0;
cdp.on("Page.screencastFrame", async (ev) => {
  const name = `f/${String(n++).padStart(5, "0")}.jpg`;
  frames.push({ name, t: ev.metadata.timestamp }); lastFrame = ev.data;
  fs.writeFileSync(path.join(outdir, name), Buffer.from(ev.data, "base64"));
  cdp.send("Page.screencastFrameAck", { sessionId: ev.sessionId }).catch(() => {});
});
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
const t0 = Date.now();
await page.goto("file://" + path.resolve(file));
// actions: [{at: seconds, do: "key"|"down"|"up"|"click"|"move"|"mdown"|"mup"|"drag", key, x, y, x2, y2, ms}]
// screen-reading dodge bot: same code for every game. Looks at pixels only (blue = player, red = enemies).
const helper = await ctx.newPage();
await helper.setContent("<canvas id=c></canvas>");
const DIRS = [[1,0],[1,1],[0,1],[-1,1],[-1,0],[-1,-1],[0,-1],[1,-1]];
const KEYS = { "1": "ArrowRight", "-1": "ArrowLeft" }, KEYSY = { "1": "ArrowDown", "-1": "ArrowUp" };
const bot = async (until) => {
  const rect = await page.evaluate(() => { const c = document.querySelector("canvas"); const r = c.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; });
  let held = new Set();
  while ((Date.now() - t0) / 1000 < until) {
    if (!lastFrame) { await page.waitForTimeout(30); continue; }
    const st = await helper.evaluate(async ([b64, R]) => {
      const img0 = new Image(); img0.src = "data:image/jpeg;base64," + b64; await img0.decode();
      const img = { width: R.width, height: R.height };
      const c = document.getElementById("c"); const S = 4; c.width = Math.round(img.width / S); c.height = Math.round(img.height / S);
      const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(img0, R.x, R.y, R.width, R.height, 0, 0, c.width, c.height);
      const d = g.getImageData(0, 0, c.width, c.height).data; let bx = 0, by = 0, bn = 0; const reds = [];
      for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) {
        const i = (y * c.width + x) * 4, r = d[i], gg = d[i + 1], b = d[i + 2];
        if (b > 170 && r < 130 && b - r > 80) { bx += x; by += y; bn++; }
        else if (r > 170 && b < 140 && gg < 140 && r - b > 70) reds.push([x * S, y * S]);
      }
      return { w: img.width, h: img.height, p: bn > 3 ? [bx / bn * S, by / bn * S] : null, reds };
    }, [lastFrame, rect]);
    let best = null;
    if (st.p && st.reds.length) {
      let bs = -1e9;
      for (const [dx, dy] of DIRS) {
        const L = Math.hypot(dx, dy), nx = st.p[0] + dx / L * 70, ny = st.p[1] + dy / L * 70;
        let sc = 0;
        for (const [rx, ry] of st.reds) {
          let ex = Math.abs(rx - nx), ey = Math.abs(ry - ny); ex = Math.min(ex, st.w - ex); ey = Math.min(ey, st.h - ey);
          sc -= 1 / (ex * ex + ey * ey + 400);
        }
        if (sc > bs) { bs = sc; best = [dx, dy]; }
      }
    }
    const want = new Set(); if (best) { if (best[0]) want.add(KEYS[best[0]]); if (best[1]) want.add(KEYSY[best[1]]); }
    for (const k of held) if (!want.has(k)) await page.keyboard.up(k);
    for (const k of want) if (!held.has(k)) await page.keyboard.down(k);
    held = want;
    await page.waitForTimeout(40);
  }
  for (const k of held) await page.keyboard.up(k);
};
const run = async (a) => {
  if (a.do === "bot") return bot(a.until);
  if (a.do === "key") await page.keyboard.press(a.key, { delay: 140 });
  else if (a.do === "down") await page.keyboard.down(a.key);
  else if (a.do === "up") await page.keyboard.up(a.key);
  else if (a.do === "click") await page.mouse.click(a.x, a.y);
  else if (a.do === "move") await page.mouse.move(a.x, a.y, { steps: a.steps ?? 8 });
  else if (a.do === "mdown") { await page.mouse.move(a.x, a.y); await page.mouse.down(); }
  else if (a.do === "mup") { if (a.x != null) await page.mouse.move(a.x, a.y, { steps: a.steps ?? 10 }); await page.mouse.up(); }
  else if (a.do === "drag") { await page.mouse.move(a.x, a.y); await page.mouse.down(); await page.mouse.move(a.x2, a.y2, { steps: a.steps ?? 15 }); await page.waitForTimeout(a.ms ?? 50); await page.mouse.up(); }
};
for (const a of actions.sort((p, q) => p.at - q.at)) {
  const wait = a.at * 1000 - (Date.now() - t0);
  if (wait > 0) await page.waitForTimeout(wait);
  try { await run(a); } catch (e) { logs.push(`[action] ${e}`); }
}
const left = Number(secs) * 1000 - (Date.now() - t0);
if (left > 0) await page.waitForTimeout(left);
await cdp.send("Page.stopScreencast");
await page.screenshot({ path: path.join(outdir, "last.png") });
const text = await page.evaluate(() => document.body ? document.body.innerText.slice(0, 1500) : "");
await browser.close();
let cc = "ffconcat version 1.0\n";
for (let i = 0; i < frames.length; i++) {
  const d = i + 1 < frames.length ? frames[i + 1].t - frames[i].t : Math.max(1 / 30, Number(secs) - (frames[i].t - frames[0].t));
  cc += `file '${frames[i].name}'\nduration ${Math.max(0.001, d).toFixed(4)}\n`;
}
if (frames.length) cc += `file '${frames.at(-1).name}'\n`;
fs.writeFileSync(path.join(outdir, "frames.ffconcat"), cc);
fs.writeFileSync(path.join(outdir, "report.json"), JSON.stringify({ file, frames: frames.length, span: frames.length ? frames.at(-1).t - frames[0].t : 0, logs, text }, null, 1));
console.log(outdir, "frames", frames.length, "logs", logs.length);
