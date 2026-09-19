import React from 'react';
import { renderToString } from 'react-dom/server';
import App from './App';

// SSR entry — bundled by `vite build --ssr` into dist-ssr/, then
// scripts/prerender.mjs injects the rendered markup into dist/index.html so
// crawlers that never execute JavaScript still receive the full page.
export function render() {
    return renderToString(
        <React.StrictMode>
            <App />
        </React.StrictMode>
    );
}
