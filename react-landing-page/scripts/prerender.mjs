import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';

// Runs after `vite build && vite build --ssr`. Bakes the server-rendered App
// markup into dist/index.html so crawlers that do not execute JavaScript
// (GPTBot, ClaudeBot, PerplexityBot, ...) receive real content instead of an
// empty #root shell. The SSR bundle is discarded afterwards — it only exists
// to produce the markup.
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const { render } = await import(pathToFileURL(join(root, 'dist-ssr/entry-server.js')));

const htmlPath = join(root, 'dist/index.html');
const html = readFileSync(htmlPath, 'utf8');
const app = render();
const marker = '<div id="root"></div>';
if (!html.includes(marker)) {
    throw new Error(`prerender: ${marker} not found in dist/index.html`);
}
writeFileSync(htmlPath, html.replace(marker, `<div id="root">${app}</div>`));

// Keep the sitemap fresh on every publish: public/sitemap.xml is the canonical
// URL list; dist/sitemap.xml gets its <lastmod> bumped to the build date so the
// deployed copy never drifts stale (issue #138).
const today = new Date().toISOString().slice(0, 10);
const sitemap = readFileSync(join(root, 'public/sitemap.xml'), 'utf8');
const stamped = sitemap.replace(/<lastmod>[^<]*<\/lastmod>/g, `<lastmod>${today}</lastmod>`);
if (!/<lastmod>\d{4}-\d{2}-\d{2}<\/lastmod>/.test(stamped)) {
    throw new Error('prerender: no <lastmod> date stamped into sitemap.xml');
}
writeFileSync(join(root, 'dist/sitemap.xml'), stamped);
console.log(`prerender: stamped dist/sitemap.xml lastmod=${today}`);

rmSync(join(root, 'dist-ssr'), { recursive: true, force: true });
console.log(`prerender: injected ${app.length} bytes of markup into dist/index.html`);
