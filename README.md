# Frederick Beer Trail

Frederick Beer Trail is a small, independent guide to breweries currently operating in Frederick
County, Maryland. Visitors can mark breweries as visited, follow their progress, browse a schematic
trail, and use a geographic map. It is a [Mudhop](https://mudhop.com/) project, not an official
Frederick County tourism program.

## Architecture

The site is static and client-side only: semantic HTML, CSS, small JavaScript modules, and one JSON
data file. There is no backend, database, account system, authentication, analytics, or scraping.
Leaflet powers the geographic map; map tiles and geographic data come from OpenStreetMap.

Visited state is stored in the browser under `frederick-beer-trail:v1` with this shape:

```json
{
  "visited": {
    "attaboy": true
  }
}
```

Invalid storage is ignored, removed brewery IDs are discarded, and the checklist still works for
the current session if local storage is unavailable.

## Brewery data

[`data/breweries.json`](data/breweries.json) is the only brewery data source. Its records generate
the total, progress, filters, cards, schematic stops, and geographic markers.

To maintain the directory:

1. Add, remove, or edit a brewery in `data/breweries.json`.
2. Keep `id` stable after publication; it is the identity used for saved progress.
3. Verify that the business is operating as a brewery at a physical Frederick County location.
4. Confirm the address, official HTTPS website, directions URL, and coordinates.
5. Give the stop a legible `trail` position in the SVG's `1000 × 560` coordinate space.
6. Update the top-level `lastVerified` date after reviewing the full list.
7. Run `npm run check` and preview the result at phone and desktop widths.

Do not add hours, tap lists, ratings, events, or other frequently changing details. Short visit notes
are appropriate only when they prevent confusion, such as an event-oriented operation.

## Local development

The project has no package dependencies. Node.js 24 is used for validation and the production copy;
any local static server can serve the source directly.

```bash
npm run check
npm run start
```

Open <http://localhost:8000/>. Opening `index.html` directly will not work because browsers block
the JSON request from `file:` URLs.

Create the exact production artifact with:

```bash
npm run build
```

The generated site is written to ignored `dist/`.

## Deployment

`.github/workflows/pages.yml` validates, builds, and deploys `dist/` on pushes to `main`. In the
repository settings, set **Pages → Build and deployment → Source** to **GitHub Actions**. The current
canonical URL is `https://derailable.github.io/frederick-draft/`; update the canonical and Open Graph
URLs in `index.html` if a custom domain is configured later. No `CNAME` is currently configured.

## Credits and license

The map uses [Leaflet](https://leafletjs.com/) and
[OpenStreetMap](https://www.openstreetmap.org/copyright). OpenStreetMap data is available under the
ODbL; Leaflet is BSD-2-Clause licensed. Project code is available under the repository's
[MIT License](LICENSE).
