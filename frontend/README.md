# WorkspaceAlberta Frontend

A distinctive, Alberta-themed web interface for the WorkspaceAlberta workspace generator.

## Design Philosophy

This frontend deliberately avoids generic "AI slop" aesthetics in favor of a design that reflects Alberta's character:

### Visual Identity

- **Colors**: Inspired by Alberta's landscapes
  - Deep indigo sky and prairie blues
  - Wheat gold and harvest amber
  - Spruce forest greens
  - Chinook cloud whites

- **Typography**: Distinctive font pairing
  - **Crimson Pro**: Confident serif for headings
  - **Outfit**: Modern geometric sans for body text
  - Avoids overused choices like Inter, Roboto, Space Grotesk

- **Backgrounds**: Layered and atmospheric
  - Prairie-to-mountain gradients
  - Topographic patterns
  - Radial accent overlays

- **Motion**: Smooth and purposeful
  - Staggered reveal animations on page load
  - Wind-like parallax effects
  - Micro-interactions on hover

## Features

### 1. Hero Landing Page
- Animated mountain layers with parallax effect
- Clear value proposition
- Quick stats (50+ tools, 2 questions, 5min setup)
- Trust indicators (no credit card, no API keys stored, open source)

### 2. Tool Catalog Selector
- Browse 50+ business tools by category
- Search and filter functionality
- Visual integration status badges (Native, API, Custom, Cloud)
- Multi-select with animated checkmarks
- Real-time selection counter

### 3. Problem Description Form
- Guided textarea with word count validation
- Example problems for inspiration
- Helpful contextual hints
- Split layout with sticky examples

### 4. Configuration Preview
- Success celebration with generated workspace
- Tool summary cards
- Copy-to-clipboard generator command
- Download configuration as markdown
- Next steps guide
- Quick actions (edit, restart)

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: CSS Modules with CSS Variables
- **Animation**: Framer Motion + CSS animations
- **Fonts**: Google Fonts (Crimson Pro + Outfit)

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build

```bash
npm run build
npm start
```

## Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout with metadata
│   │   └── page.tsx            # Main app with step routing
│   ├── components/
│   │   ├── Hero.tsx            # Landing page
│   │   ├── Hero.module.css
│   │   ├── ToolSelector.tsx    # Tool selection grid
│   │   ├── ToolSelector.module.css
│   │   ├── ProblemForm.tsx     # Problem description
│   │   ├── ProblemForm.module.css
│   │   ├── ConfigPreview.tsx   # Preview & export
│   │   └── ConfigPreview.module.css
│   ├── data/
│   │   └── catalog.json        # Simplified tool catalog
│   └── styles/
│       └── globals.css         # Design system & variables
├── public/                     # Static assets
├── package.json
├── tsconfig.json
└── next.config.js
```

## Design System

All colors, typography, spacing, and other design tokens are defined as CSS variables in `src/styles/globals.css`:

```css
:root {
  /* Alberta Color Palette */
  --sky-deep: #1a2942;
  --wheat-gold: #d4a574;
  --spruce-dark: #1e3a2e;
  --chinook-white: #f5f1e8;

  /* Typography */
  --font-display: 'Crimson Pro', serif;
  --font-body: 'Outfit', sans-serif;

  /* Spacing, shadows, etc. */
}
```

## Integration with Backend

Currently, this frontend is a static demonstration. To integrate with the actual generator:

1. **API Endpoints**: Create Next.js API routes in `src/app/api/`
2. **Generator Integration**: Import and call the TypeScript generator from `../generator/generator.ts`
3. **File Generation**: Stream or download generated files (mcp.json, .env, etc.)
4. **GitHub Integration**: Add OAuth and repository creation via GitHub API

## Future Enhancements

- [ ] User authentication
- [ ] Save workspace configurations
- [ ] Direct GitHub repository creation
- [ ] Real-time validation of API keys
- [ ] Workspace management dashboard
- [ ] Usage analytics
- [ ] Tool recommendation engine

## Contributing

When adding new features:

1. Follow the established Alberta-inspired aesthetic
2. Use CSS variables from the design system
3. Add staggered animations for page elements
4. Test responsive layouts (mobile, tablet, desktop)
5. Maintain accessibility (keyboard nav, screen readers)

## License

Same as parent WorkspaceAlberta project
