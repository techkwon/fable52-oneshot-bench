// usage: node svgfit.mjs <model>  -> rec/svg-<model>.png (whole SVG fitted in 1280x800, object-fit: contain) + 3s mp4
// Written after the first SVG round was cropped by the viewport; every model is captured the same way.
import { createRequire } from "module";
import fs from "fs";
import { execFileSync } from "child_process";
const require = createRequire("/path/to/global/node_modules/");
const { chromium } = require("playwright");
const B = "/path/to/samples";
const m = process.argv[2];
const html = `${B}/rec/tmp-svgfit-${m}.html`;
fs.writeFileSync(html, `<body style="margin:0;background:#fff"><img src="file://${B}/runs/svg/${m}/index.svg" style="width:1280px;height:800px;object-fit:contain"></body>`);
const b = await chromium.launch({ channel: "chrome", headless: true });
const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
await p.goto("file://" + html); await p.waitForTimeout(600);
await p.screenshot({ path: `${B}/rec/svg-${m}.png` });
await b.close(); fs.rmSync(html);
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-loop", "1", "-i", `${B}/rec/svg-${m}.png`, "-t", "3", "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "16", `${B}/rec/svg-${m}.mp4`]);
console.log("fitted", m);
