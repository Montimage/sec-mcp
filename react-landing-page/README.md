# sec-mcp Landing Page

This is the landing page for the sec-mcp security checking toolkit. It provides a modern, responsive web interface that showcases the features and capabilities of sec-mcp.

## Technologies

- React (via Vite)
- TailwindCSS for styling
- GitHub Actions for automatic deployment

## Local Development

### Prerequisites

- Node.js (v24 LTS or newer; see `.nvmrc`)
- npm or yarn

### Setup and Run

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. View the site at [http://localhost:3000](http://localhost:3000)

## Building for Production

To build the landing page for production:

```bash
npm run build
```

This will generate static files in the `dist/` directory.

## Deployment

This project is automatically deployed to GitHub Pages whenever changes are pushed to the main branch. The deployment is handled by GitHub Actions as defined in `.github/workflows/deploy-landing-page.yml`.

### Manually Triggering Deployment

You can manually trigger the deployment workflow by:

1. Going to the GitHub repository
2. Clicking on "Actions" tab
3. Selecting "Deploy Landing Page to GitHub Pages" workflow
4. Clicking "Run workflow"

## Customization

### Colors and Styling

The site uses Tailwind CSS v4. All design tokens — colours, fonts and fluid type
scale — live in the `@theme` block at the top of `src/index.css`; there is no
`tailwind.config.js` and one would be ignored.

The palette is deliberately four colours: black, white, gray and signal green
(`#22C55E`). Green is only ever used for text, hairlines, borders and focus
rings, never as a background fill. Note that the base gray `#6B7280` measures
4.34:1 on black and so **fails WCAG AA for text** — it is reserved for rules and
borders, while `--color-dim` and `--color-faint` carry secondary and label text.
Keep that split if you add new styles.

### Content

The content is divided into components in the `src/components/` directory:

- `Header.jsx` - Fixed navigation bar with mobile menu
- `Hero.jsx` - Hero section and the headline stat strip
- `Terminal.jsx` - Self-typing CLI session shown in the hero
- `Features.jsx` - Capability grid
- `Sources.jsx` - The ten blacklist feeds (keep in sync with `sec_mcp/config.json`)
- `MCPServer.jsx` - MCP server config and exposed tools
- `Installation.jsx` - Install timeline and Python quickstart
- `APIReference.jsx` - Python API methods and return types
- `Footer.jsx` - Closing call to action, link columns and colophon

Shared primitives:

- `SectionHeading.jsx` - The numbered section header used by every section
- `CodeBlock.jsx` - Syntax-highlighted code with a copy button
- `Reveal.jsx` - IntersectionObserver scroll reveal (honours `prefers-reduced-motion`)
- `Logo.jsx` - The sec-mcp mark

Edit these files to update the content of the landing page.

## License

This landing page is part of the sec-mcp project and is licensed under Apache-2.0.