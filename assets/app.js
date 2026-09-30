import { createBeerMap } from "./map.js";

const STORAGE_KEY = "frederick-beer-trail:v1";
const SVG_NS = "http://www.w3.org/2000/svg";

const elements = {
  visitedCount: document.querySelector("#visited-count"),
  breweryCount: document.querySelector("#brewery-count"),
  progress: document.querySelector("#trail-progress"),
  completion: document.querySelector("#completion-note"),
  trailStops: document.querySelector("#trail-stops"),
  filters: document.querySelector("#area-filters"),
  statusFilter: document.querySelector("#status-filter"),
  resultCount: document.querySelector("#result-count"),
  list: document.querySelector("#brewery-list"),
  emptyState: document.querySelector("#empty-state"),
  reset: document.querySelector("#reset-progress"),
  map: document.querySelector("#brewery-map"),
  mapStatus: document.querySelector("#map-status"),
  verifiedDate: document.querySelector("#verified-date"),
};

let breweries = [];
let visited = Object.create(null);
let selectedArea = "All";
let beerMap = null;
let highlightTimer = null;

function loadVisited(validIds) {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    if (!value || typeof value !== "object" || !value.visited || typeof value.visited !== "object") {
      return Object.create(null);
    }

    return Object.fromEntries(
      Object.entries(value.visited).filter(([id, state]) => validIds.has(id) && state === true),
    );
  } catch {
    return Object.create(null);
  }
}

function saveVisited() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ visited }));
  } catch {
    // Progress continues in memory when storage is blocked or unavailable.
  }
}

function isVisited(id) {
  return visited[id] === true;
}

function setVisited(id, state) {
  if (state) visited[id] = true;
  else delete visited[id];
  saveVisited();
  updateInterface();
  beerMap?.setVisited(id, state);
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function breweryCard(brewery) {
  const card = element("article", "brewery-card");
  card.id = `brewery-${brewery.id}`;
  card.dataset.breweryId = brewery.id;
  card.dataset.area = brewery.area;
  card.tabIndex = -1;

  const details = element("div", "card-details");
  const heading = element("h3", "", brewery.name);
  const headingId = `brewery-name-${brewery.id}`;
  heading.id = headingId;
  card.setAttribute("aria-labelledby", headingId);

  const place = element("p", "card-place");
  place.append(
    element("span", "", brewery.area),
    element("span", "card-type", brewery.type),
  );
  details.append(heading, place);
  if (brewery.note) details.append(element("p", "card-note", brewery.note));

  const actions = element("div", "card-actions");
  const label = element("label", "visit-control");
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.dataset.visitId = brewery.id;
  checkbox.setAttribute("aria-label", `Mark ${brewery.name} as visited`);
  checkbox.addEventListener("change", () => setVisited(brewery.id, checkbox.checked));
  label.append(
    checkbox,
    element("span", "visit-box"),
    element("span", "visit-label", "Mark visited"),
  );

  const links = element("p", "card-links");
  const website = element("a", "external-link", "Official site");
  website.href = brewery.website;
  website.rel = "external";
  const directions = element("a", "external-link", "Directions");
  directions.href = brewery.mapsUrl;
  directions.rel = "external";
  links.append(website, directions);

  actions.append(label, links);
  card.append(details, actions);
  return card;
}

function svgElement(tag, attributes = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  return node;
}

function trailLabelPosition(trail) {
  if (trail.labelSide === "above") {
    return { x: trail.x, y: trail.y - 25, anchor: "middle" };
  }
  if (trail.labelSide === "right") {
    return { x: trail.x + 23, y: trail.y + 5, anchor: "start" };
  }
  return { x: trail.x, y: trail.y + 34, anchor: "middle" };
}

function focusBrewery(id) {
  const card = document.querySelector(`#brewery-${CSS.escape(id)}`);
  if (!card) return;

  if (card.hidden) {
    selectedArea = "All";
    elements.statusFilter.value = "all";
    updateFilters();
    applyFilters();
  }

  clearTimeout(highlightTimer);
  document.querySelectorAll(".brewery-card.is-highlighted").forEach((item) => {
    item.classList.remove("is-highlighted");
  });
  card.classList.add("is-highlighted");
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.focus({ preventScroll: true });
  highlightTimer = window.setTimeout(() => card.classList.remove("is-highlighted"), 1800);
}

function trailStop(brewery) {
  const { trail } = brewery;
  const group = svgElement("g", {
    class: "trail-stop",
    role: "button",
    tabindex: "0",
    "data-brewery-id": brewery.id,
  });
  const labelPosition = trailLabelPosition(trail);
  const label = svgElement("text", {
    x: labelPosition.x,
    y: labelPosition.y,
    "text-anchor": labelPosition.anchor,
    "aria-hidden": "true",
  });
  label.textContent = trail.label;

  group.append(
    svgElement("circle", { class: "stop-halo", cx: trail.x, cy: trail.y, r: "18" }),
    svgElement("circle", { class: "stop-dot", cx: trail.x, cy: trail.y, r: "11" }),
    svgElement("path", {
      class: "stop-check",
      d: `M${trail.x - 5} ${trail.y} l4 4 l7 -8`,
    }),
    label,
  );
  group.addEventListener("click", () => focusBrewery(brewery.id));
  group.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      focusBrewery(brewery.id);
    }
  });
  return group;
}

function createAreaFilters() {
  const areas = ["All", ...new Set(breweries.map((brewery) => brewery.area))];
  const fragment = document.createDocumentFragment();

  for (const area of areas) {
    const button = element("button", "filter-button", area);
    button.type = "button";
    button.dataset.area = area;
    button.setAttribute("aria-pressed", String(area === selectedArea));
    button.addEventListener("click", () => {
      selectedArea = area;
      updateFilters();
      applyFilters();
    });
    fragment.append(button);
  }
  elements.filters.append(fragment);
}

function updateFilters() {
  elements.filters.querySelectorAll("button").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.area === selectedArea));
  });
}

function applyFilters() {
  const status = elements.statusFilter.value;
  let shown = 0;

  for (const card of elements.list.querySelectorAll(".brewery-card")) {
    const state = isVisited(card.dataset.breweryId);
    const areaMatches = selectedArea === "All" || card.dataset.area === selectedArea;
    const statusMatches =
      status === "all" || (status === "visited" && state) || (status === "not-visited" && !state);
    card.hidden = !(areaMatches && statusMatches);
    if (!card.hidden) shown += 1;
  }

  elements.resultCount.textContent = `${shown} ${shown === 1 ? "brewery" : "breweries"}`;
  elements.emptyState.hidden = shown !== 0;
}

function updateInterface() {
  const count = breweries.filter((brewery) => isVisited(brewery.id)).length;
  const total = breweries.length;

  elements.visitedCount.textContent = count;
  elements.breweryCount.textContent = total;
  elements.progress.max = total;
  elements.progress.value = count;
  elements.progress.textContent = `${Math.round((count / total) * 100)}% visited`;
  elements.completion.hidden = count !== total;
  document.body.classList.toggle("trail-complete", count === total);

  for (const brewery of breweries) {
    const state = isVisited(brewery.id);
    const card = document.querySelector(`#brewery-${CSS.escape(brewery.id)}`);
    const checkbox = card.querySelector("input[type='checkbox']");
    const visitLabel = card.querySelector(".visit-label");
    checkbox.checked = state;
    checkbox.setAttribute(
      "aria-label",
      `Mark ${brewery.name} as ${state ? "not visited" : "visited"}`,
    );
    visitLabel.textContent = state ? "Visited" : "Mark visited";
    card.classList.toggle("is-visited", state);

    const stop = elements.trailStops.querySelector(`[data-brewery-id="${CSS.escape(brewery.id)}"]`);
    stop.classList.toggle("is-visited", state);
    stop.setAttribute(
      "aria-label",
      `${brewery.name}, ${state ? "visited" : "not visited"}. Show brewery card.`,
    );
  }

  applyFilters();
}

function resetProgress() {
  if (Object.keys(visited).length === 0) return;
  if (!window.confirm("Reset every visited brewery? This cannot be undone.")) return;
  visited = Object.create(null);
  saveVisited();
  updateInterface();
  for (const brewery of breweries) beerMap?.setVisited(brewery.id, false);
}

function formatVerificationDate(value) {
  const date = new Date(`${value}T12:00:00Z`);
  if (Number.isNaN(date.valueOf())) return null;
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function initializeMap() {
  if (beerMap) return;
  try {
    beerMap = createBeerMap(elements.map, breweries, isVisited);
  } catch {
    elements.mapStatus.textContent =
      "The interactive map could not load. Use the directions links in the brewery list.";
  }
}

function lazyInitializeMap() {
  if (!("IntersectionObserver" in window)) {
    initializeMap();
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      observer.disconnect();
      initializeMap();
    },
    { rootMargin: "300px" },
  );
  observer.observe(elements.map);
}

function centerScrollableTrail() {
  const frame = elements.trailStops.closest(".trail-frame");
  if (!frame || frame.scrollWidth <= frame.clientWidth) return;
  frame.scrollLeft = (frame.scrollWidth - frame.clientWidth) * 0.48;
}

async function initialize() {
  try {
    const response = await fetch("data/breweries.json");
    if (!response.ok) throw new Error(`Data request failed with ${response.status}`);
    const data = await response.json();
    breweries = data.breweries;
    visited = loadVisited(new Set(breweries.map((brewery) => brewery.id)));

    const cardFragment = document.createDocumentFragment();
    const stopFragment = document.createDocumentFragment();
    for (const brewery of breweries) {
      cardFragment.append(breweryCard(brewery));
      stopFragment.append(trailStop(brewery));
    }
    elements.list.append(cardFragment);
    elements.trailStops.append(stopFragment);
    elements.list.setAttribute("aria-busy", "false");
    requestAnimationFrame(centerScrollableTrail);

    createAreaFilters();
    elements.statusFilter.addEventListener("change", applyFilters);
    elements.reset.addEventListener("click", resetProgress);
    const verified = formatVerificationDate(data.lastVerified);
    if (verified) elements.verifiedDate.textContent = `Brewery list last verified ${verified}.`;

    updateInterface();
    lazyInitializeMap();
  } catch (error) {
    console.error(error);
    elements.list.setAttribute("aria-busy", "false");
    elements.list.append(
      element(
        "p",
        "empty-state",
        "The brewery list could not load. Please refresh the page and try again.",
      ),
    );
  }
}

initialize();
