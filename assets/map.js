function markerIcon(visited) {
  return window.L.divIcon({
    className: "",
    html: `<span class="map-marker${visited ? " is-visited" : ""}" aria-hidden="true"></span>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -15],
  });
}

function externalLink(label, href) {
  const link = document.createElement("a");
  link.href = href;
  link.textContent = label;
  link.rel = "external";
  return link;
}

function popupContent(brewery) {
  const wrapper = document.createElement("div");
  wrapper.className = "map-popup";

  const heading = document.createElement("h3");
  heading.textContent = brewery.name;

  const address = document.createElement("p");
  address.textContent = `${brewery.address}, ${brewery.city}`;

  const links = document.createElement("p");
  links.className = "map-popup-links";
  links.append(
    externalLink("Official site", brewery.website),
    externalLink("Directions", brewery.mapsUrl),
  );

  wrapper.append(heading, address, links);
  return wrapper;
}

export function createBeerMap(container, breweries, isVisited) {
  if (!window.L) {
    throw new Error("Leaflet did not load");
  }

  container.replaceChildren();
  const map = window.L.map(container, {
    scrollWheelZoom: false,
  });

  window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);

  const bounds = [];
  const markers = new Map();

  for (const brewery of breweries) {
    const location = [brewery.latitude, brewery.longitude];
    const marker = window.L.marker(location, {
      alt: brewery.name,
      title: brewery.name,
      keyboard: true,
      icon: markerIcon(isVisited(brewery.id)),
    });
    marker.bindPopup(popupContent(brewery));
    marker.addTo(map);
    bounds.push(location);
    markers.set(brewery.id, marker);
  }

  map.fitBounds(bounds, { padding: [28, 28], maxZoom: 12 });

  const resizeObserver = new ResizeObserver(() => map.invalidateSize({ pan: false }));
  resizeObserver.observe(container);

  return {
    setVisited(id, visited) {
      const marker = markers.get(id);
      if (marker) marker.setIcon(markerIcon(visited));
    },
  };
}
