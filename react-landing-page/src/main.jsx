import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import './webmcp.js';

const container = document.getElementById('root');
const app = (
    <React.StrictMode>
        <App />
    </React.StrictMode>
);

// The production index.html ships server-rendered markup baked in by
// scripts/prerender.mjs — attach to it. A bare container (dev server)
// mounts fresh.
if (container.hasChildNodes()) {
    ReactDOM.hydrateRoot(container, app);
} else {
    ReactDOM.createRoot(container).render(app);
}