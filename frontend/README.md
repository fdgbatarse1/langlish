# Langlish - English Learning Voice Assistant Frontend

## Description

Langlish is a real-time English learning voice assistant that uses OpenAI's speech-to-speech technology to provide immersive and interactive language practice. Learners can speak naturally and receive immediate spoken feedback, corrections, and guidance from an AI English tutor. This frontend provides a modern React-based web interface that enables seamless voice interaction, helping learners expand their vocabulary through intuitive and engaging conversations with real-time audio recording and playback capabilities.

## Features

- Real-time audio recording and playback
- WebSocket communication with backend
- Responsive design with Tailwind CSS
- TypeScript for type safety
- Modern React 18 with hooks
- Vite for fast development and building
- Audio processing and queue management
- Voice activity detection integration

## Prerequisites

- Node.js 18 or higher
- npm or pnpm package manager
- Modern web browser with microphone access
- Running Langlish backend service

## Installation

### Using pnpm (Recommended)

1. Clone the repository and navigate to the frontend directory:

```bash
cd frontend
```

2. Install pnpm if you haven't already:

```bash
npm install -g pnpm
```

3. Install dependencies:

```bash
pnpm install
```

### Using npm

1. Navigate to the frontend directory:

```bash
cd frontend
```

2. Install dependencies:

```bash
npm install
```

## Running the Application

### Development Server

Start the development server with hot reload:

```bash
pnpm run dev
# or
npm run dev
```

The application will be available at `http://localhost:5173`

### Production Build

Build the application for production:

```bash
pnpm run build
# or
npm run build
```

Preview the production build:

```bash
pnpm run preview
# or
npm run preview
```

## Development

### Type Checking

```bash
pnpm run typecheck
# or
npm run typecheck
```

### Linting

```bash
pnpm run lint
# or
npm run lint
```

### Testing

Run tests:

```bash
pnpm run test
# or
npm run test
```

Run tests with UI:

```bash
pnpm run test:ui
# or
npm run test:ui
```

## Configuration

### Backend Connection

The frontend connects to the backend WebSocket at `ws://localhost:8000/streamline` by default. To change this, modify the `socketUrl` constant in `src/components/App.tsx`.

### Audio Settings

Audio recording uses WebM/Opus format with the following default settings:

- Sample rate: 24kHz (converted from browser default)
- Channels: Mono
- Format: PCM16 for backend communication

## Project Structure

```
frontend/
├── src/
│   ├── components/      # React components
│   │   └── App.tsx     # Main application component
│   ├── index.tsx       # Application entry point
│   └── index.css       # Global styles
├── public/             # Static assets
├── dist/               # Build output
├── package.json        # Dependencies and scripts
├── vite.config.ts      # Vite configuration
├── tailwind.config.mjs # Tailwind CSS configuration
├── tsconfig.json       # TypeScript configuration
└── README.md           # This file
```

## Browser Compatibility

- Chrome/Chromium 88+
- Firefox 85+
- Safari 14+
- Edge 88+

**Note:** Microphone access requires HTTPS in production environments.

## Troubleshooting

### Microphone Access Issues

1. Ensure microphone permissions are granted
2. Check browser console for permission errors
3. Verify HTTPS is used in production
4. Test microphone access in browser settings

### WebSocket Connection Issues

1. Verify backend server is running
2. Check network connectivity
3. Ensure WebSocket URL is correct
4. Review browser console for connection errors

## License

This project is licensed under the terms specified in the LICENSE file in the root directory.
