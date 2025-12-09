'use client'

import { useState } from 'react'
import styles from './ProblemForm.module.css'

interface ProblemFormProps {
  onSubmit: (description: string) => void
  onBack: () => void
  initialValue: string
}

const exampleProblems = [
  {
    title: "Track customer conversations",
    description: "I need to keep track of customer support conversations from Zendesk and match them with payment data in Stripe to understand which customers are having issues."
  },
  {
    title: "Automate invoice reminders",
    description: "I want to automatically send reminder emails through SendGrid when QuickBooks invoices are overdue by more than 7 days."
  },
  {
    title: "Sync project updates",
    description: "When tasks in Asana are marked complete, I need to update our client in Slack and log the hours in our time tracking spreadsheet."
  },
  {
    title: "Analyze sales pipeline",
    description: "I need a weekly report that pulls deals from HubSpot, calculates conversion rates, and creates a summary document in Google Docs."
  }
]

export default function ProblemForm({ onSubmit, onBack, initialValue }: ProblemFormProps) {
  const [description, setDescription] = useState(initialValue)
  const [selectedExample, setSelectedExample] = useState<number | null>(null)

  const handleExampleClick = (index: number, exampleDesc: string) => {
    setSelectedExample(index)
    setDescription(exampleDesc)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (description.trim()) {
      onSubmit(description.trim())
    }
  }

  const wordCount = description.trim().split(/\s+/).filter(Boolean).length
  const isValid = wordCount >= 10

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className="container">
          <button onClick={onBack} className={styles.backButton}>
            ← Back
          </button>
          <h2 className={`${styles.title} animate-fadeInUp`}>
            What problem do you want to solve?
          </h2>
          <p className={`${styles.subtitle} animate-fadeInUp stagger-1`}>
            Describe one specific challenge your business faces. The more specific you are,
            the better we can configure your workspace.
          </p>
        </div>
      </div>

      <div className={`${styles.content} container`}>
        <form onSubmit={handleSubmit} className={`${styles.form} animate-fadeInUp stagger-2`}>
          <div className={styles.textareaWrapper}>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Example: I need to automatically sync customer support tickets from Zendesk with our CRM in HubSpot, so our sales team knows when customers are having issues..."
              className={styles.textarea}
              rows={8}
              autoFocus
            />
            <div className={styles.wordCount}>
              <span className={isValid ? styles.valid : styles.invalid}>
                {wordCount} words
              </span>
              {!isValid && <span className={styles.hint}>(at least 10 words needed)</span>}
            </div>
          </div>

          <div className={styles.helpText}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path
                d="M10 0C4.48 0 0 4.48 0 10C0 15.52 4.48 20 10 20C15.52 20 20 15.52 20 10C20 4.48 15.52 0 10 0ZM10 15C9.45 15 9 14.55 9 14C9 13.45 9.45 13 10 13C10.55 13 11 13.45 11 14C11 14.55 10.55 15 10 15ZM11 11H9V5H11V11Z"
                fill="currentColor"
              />
            </svg>
            <span>
              Focus on the outcome you want, not the technical details.
              Mention which tools are involved if relevant.
            </span>
          </div>

          <button
            type="submit"
            disabled={!isValid}
            className={`btn-accent ${styles.submitButton}`}
          >
            Generate My Workspace
            <span className={styles.arrow}>→</span>
          </button>
        </form>

        <div className={`${styles.examples} animate-fadeInUp stagger-3`}>
          <h3 className={styles.examplesTitle}>Need inspiration?</h3>
          <p className={styles.examplesSubtitle}>
            Here are some common problems Alberta business owners solve:
          </p>

          <div className={styles.exampleGrid}>
            {exampleProblems.map((example, index) => (
              <button
                key={index}
                onClick={() => handleExampleClick(index, example.description)}
                className={`${styles.exampleCard} ${selectedExample === index ? styles.selected : ''}`}
                type="button"
              >
                <h4 className={styles.exampleTitle}>{example.title}</h4>
                <p className={styles.exampleDescription}>{example.description}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
