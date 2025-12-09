'use client'

import { useState } from 'react'
import Hero from '@/components/Hero'
import ToolSelector from '@/components/ToolSelector'
import ProblemForm from '@/components/ProblemForm'
import ConfigPreview from '@/components/ConfigPreview'

type Step = 'welcome' | 'tools' | 'problem' | 'preview'

export default function Home() {
  const [currentStep, setCurrentStep] = useState<Step>('welcome')
  const [selectedTools, setSelectedTools] = useState<string[]>([])
  const [problemDescription, setProblemDescription] = useState('')

  const handleToolsSelected = (tools: string[]) => {
    setSelectedTools(tools)
    setCurrentStep('problem')
  }

  const handleProblemSubmit = (description: string) => {
    setProblemDescription(description)
    setCurrentStep('preview')
  }

  const handleBack = () => {
    if (currentStep === 'problem') setCurrentStep('tools')
    if (currentStep === 'preview') setCurrentStep('problem')
  }

  const handleRestart = () => {
    setCurrentStep('welcome')
    setSelectedTools([])
    setProblemDescription('')
  }

  return (
    <main>
      {currentStep === 'welcome' && (
        <Hero onStart={() => setCurrentStep('tools')} />
      )}

      {currentStep === 'tools' && (
        <ToolSelector
          onSelect={handleToolsSelected}
          initialSelection={selectedTools}
        />
      )}

      {currentStep === 'problem' && (
        <ProblemForm
          onSubmit={handleProblemSubmit}
          onBack={handleBack}
          initialValue={problemDescription}
        />
      )}

      {currentStep === 'preview' && (
        <ConfigPreview
          tools={selectedTools}
          problem={problemDescription}
          onBack={handleBack}
          onRestart={handleRestart}
        />
      )}
    </main>
  )
}
