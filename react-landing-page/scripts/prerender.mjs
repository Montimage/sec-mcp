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
rmSync(join(root, 'dist-ssr'), { recursive: true, force: true });
console.log(`prerender: injected ${app.length} bytes of markup into dist/index.html`);
