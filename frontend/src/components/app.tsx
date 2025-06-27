import AgentStreamline from './agent-streamline'
import Streamline from './streamline'
import { useState } from 'react'

const App = () => {
  const [activeSection, setActiveSection] = useState('streamline')

  return (
    <div className="flex min-h-screen flex-col p-4">
      <div className="flex justify-between gap-4">
        <button
          onClick={() => setActiveSection('streamline')}
          className={`px-6 py-2 text-sm font-medium transition-colors ${
            activeSection === 'streamline'
              ? 'border-b-2 border-gray-900 text-gray-900'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Streamline
        </button>
        <button
          onClick={() => setActiveSection('agent')}
          className={`px-6 py-2 text-sm font-medium transition-colors ${
            activeSection === 'agent'
              ? 'border-b-2 border-gray-900 text-gray-900'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Agent Streamline
        </button>
      </div>

      <div className="container flex flex-1 items-center justify-center">
        {activeSection === 'agent' && <AgentStreamline />}
        {activeSection === 'streamline' && <Streamline />}
      </div>
    </div>
  )
}

export default App
