import { cp, mkdir, rm } from "node:fs/promises";

const output = new URL("../dist/", import.meta.url);
const root = new URL("../", import.meta.url);

await rm(output, { recursive: true, force: true });
await mkdir(new URL("assets/", output), { recursive: true });
await mkdir(new URL("data/", output), { recursive: true });

for (const path of [
  "index.html",
  ".nojekyll",
  "assets/app.js",
  "assets/map.js",
  "assets/styles.css",
  "assets/favicon.svg",
  "data/breweries.json",
]) {
  await cp(new URL(path, root), new URL(path, output));
}

console.log("Built static site in dist/");
