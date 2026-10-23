// Rasterise SVG masters to PNG. Called by build.py with a jobs file:
//   [{ svg, out, mode: "width"|"height", value, background|null }, ...]
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { Resvg } = require("@resvg/resvg-js");

const jobs = JSON.parse(readFileSync(process.argv[2], "utf8"));
for (const job of jobs) {
  const svg = readFileSync(job.svg, "utf8");
  const opts = { fitTo: { mode: job.mode, value: job.value } };
  if (job.background) opts.background = job.background;
  const png = new Resvg(svg, opts).render().asPng();
  writeFileSync(job.out, png);
}
console.log(`rendered ${jobs.length} PNGs`);
