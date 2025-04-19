# sec-mcp Landing Page

This is the landing page for the sec-mcp security checking toolkit. It provides a modern, responsive web interface that showcases the features and capabilities of sec-mcp.

## Technologies

- React (via Vite)
- TailwindCSS for styling
- GitHub Actions for automatic deployment

## Local Development

### Prerequisites

- Node.js (v16+)
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

The site uses TailwindCSS for styling. You can customize the colors, fonts, and other design elements by editing the `tailwind.config.js` file.

### Content

The content is divided into components in the `src/components/` directory:

- `Header.jsx` - Navigation bar
- `Hero.jsx` - Main hero section
- `Features.jsx` - Features showcase
- `Installation.jsx` - Installation instructions
- `APIReference.jsx` - API documentation
- `MCPServer.jsx` - MCP server integration details
- `Footer.jsx` - Page footer

Edit these files to update the content of the landing page.

## License

This landing page is part of the sec-mcp project and is licensed under MIT.