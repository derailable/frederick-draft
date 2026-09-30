# Frederick Beer Trail

This repository is a static, client-side guide to currently operating breweries in Frederick
County, Maryland. Keep it dependency-light and GitHub Pages compatible. There is no backend,
scraper, database, account system, or live inventory.

`data/breweries.json` is the single brewery source of truth. Never duplicate brewery records or
hardcode totals in HTML or JavaScript. Keep stable brewery IDs because local progress uses them.
Only include operating brewery locations physically inside Frederick County. Avoid volatile data
such as hours, tap lists, events, ratings, and reviews.

Before handoff run `npm run check` and `npm run build`.
