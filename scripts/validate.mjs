import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const data = JSON.parse(await readFile(new URL("data/breweries.json", root), "utf8"));

if (!/^\d{4}-\d{2}-\d{2}$/.test(data.lastVerified)) {
  throw new Error("lastVerified must use YYYY-MM-DD");
}

if (!Array.isArray(data.breweries) || data.breweries.length === 0) {
  throw new Error("breweries must be a non-empty array");
}

const required = [
  "id",
  "name",
  "address",
  "city",
  "state",
  "zip",
  "latitude",
  "longitude",
  "website",
  "mapsUrl",
  "type",
  "area",
  "trail",
];
const ids = new Set();

for (const brewery of data.breweries) {
  for (const field of required) {
    if (brewery[field] === undefined || brewery[field] === "") {
      throw new Error(`${brewery.id ?? brewery.name ?? "Unknown brewery"} is missing ${field}`);
    }
  }
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(brewery.id)) {
    throw new Error(`Invalid stable ID: ${brewery.id}`);
  }
  if (ids.has(brewery.id)) throw new Error(`Duplicate brewery ID: ${brewery.id}`);
  ids.add(brewery.id);

  if (brewery.state !== "MD") throw new Error(`${brewery.id} is not in Maryland`);
  if (
    typeof brewery.latitude !== "number" ||
    typeof brewery.longitude !== "number" ||
    brewery.latitude < 39.2 ||
    brewery.latitude > 39.75 ||
    brewery.longitude < -77.75 ||
    brewery.longitude > -77.05
  ) {
    throw new Error(`${brewery.id} has coordinates outside Frederick County's vicinity`);
  }
  for (const field of ["website", "mapsUrl"]) {
    const url = new URL(brewery[field]);
    if (url.protocol !== "https:") throw new Error(`${brewery.id} ${field} must use HTTPS`);
  }
  if (
    typeof brewery.trail.x !== "number" ||
    typeof brewery.trail.y !== "number" ||
    !brewery.trail.label ||
    !brewery.trail.branch
  ) {
    throw new Error(`${brewery.id} has incomplete trail placement`);
  }
}

console.log(`Validated ${data.breweries.length} breweries (${data.lastVerified})`);
