import * as Sentry from '@sentry/react'

Sentry.init({
  dsn: 'https://806c8ed88281995339b8a9f14726f09f@o4509557900509184.ingest.us.sentry.io/4509557902344192',
  // Setting this option to true will send default PII data to Sentry.
  // For example, automatic IP address collection on events
  sendDefaultPii: true

  //   ACTIVATE TRACING

  //   integrations: [Sentry.browserTracingIntegration()],
  //   // Tracing
  //   tracesSampleRate: 1.0, //  Capture 100% of the transactions
  //   // Set 'tracePropagationTargets' to control for which URLs distributed tracing should be enabled
  //   tracePropagationTargets: ['localhost', /^https:\/\/yourserver\.io\/api/]

  //   ACTIVATE REPLAY

  //   integrations: [
  //     Sentry.replayIntegration()
  //   ],
  //   // Session Replay
  //   replaysSessionSampleRate: 0.1, // This sets the sample rate at 10%. You may want to change it to 100% while in development and then sample at a lower rate in production.
  //   replaysOnErrorSampleRate: 1.0 // If you're not already sampling the entire session, change the sample rate to 100% when sampling sessions where errors occur.
})

import { createRoot } from 'react-dom/client'
import 'tailwindcss/tailwind.css'
import App from 'components/App'

const container = document.getElementById('root') as HTMLDivElement
const root = createRoot(container)

root.render(<App />)
