'use client'

import { useState, useMemo } from 'react'
import styles from './ConfigPreview.module.css'
import catalog from '@/data/catalog.json'

interface ConfigPreviewProps {
  tools: string[]
  problem: string
  onBack: () => void
  onRestart: () => void
}

interface Tool {
  id: string
  display_name: string
  category: string
  description: string
  integration_status: string
}

export default function ConfigPreview({ tools, problem, onBack, onRestart }: ConfigPreviewProps) {
  const [copiedSection, setCopiedSection] = useState<string | null>(null)

  const selectedTools = useMemo(() => {
    return catalog.filter((tool: Tool) => tools.includes(tool.id))
  }, [tools])

  const handleCopy = async (text: string, section: string) => {
    await navigator.clipboard.writeText(text)
    setCopiedSection(section)
    setTimeout(() => setCopiedSection(null), 2000)
  }

  const handleDownload = () => {
    const content = `# WorkspaceAlberta Configuration

## Problem Statement
${problem}

## Selected Tools (${tools.length})
${selectedTools.map((tool: Tool) => `- ${tool.display_name} (${tool.category})`).join('\n')}

## Next Steps
1. Clone the WorkspaceAlberta repository
2. Run the generator with these tool IDs:
   npx ts-node generator/generator.ts ${tools.join(' ')}
3. Fill in your API keys in the generated .env file
4. Open the workspace in Cursor IDE

---
Generated with WorkspaceAlberta
Built for Alberta entrepreneurs
`

    const blob = new Blob([content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'workspace-config.md'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const commandString = `npx ts-node generator/generator.ts ${tools.join(' ')}`

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className="container">
          <div className={styles.successIcon}>
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
              <circle cx="32" cy="32" r="32" fill="currentColor" opacity="0.1" />
              <path
                d="M44 24L28 40L20 32"
                stroke="currentColor"
                strokeWidth="4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h2 className={`${styles.title} animate-fadeInUp stagger-1`}>
            Your Workspace is Ready!
          </h2>
          <p className={`${styles.subtitle} animate-fadeInUp stagger-2`}>
            We've configured your AI workspace with {tools.length} tools to solve your business problem.
          </p>
        </div>
      </div>

      <div className={`${styles.content} container`}>
        <div className={styles.mainColumn}>
          <section className={`${styles.section} animate-fadeInUp stagger-3`}>
            <h3 className={styles.sectionTitle}>Your Problem</h3>
            <div className={styles.problemBox}>
              <p>{problem}</p>
            </div>
          </section>

          <section className={`${styles.section} animate-fadeInUp stagger-4`}>
            <h3 className={styles.sectionTitle}>Selected Tools ({tools.length})</h3>
            <div className={styles.toolsList}>
              {selectedTools.map((tool: Tool) => (
                <div key={tool.id} className={styles.toolItem}>
                  <div className={styles.toolHeader}>
                    <h4 className={styles.toolName}>{tool.display_name}</h4>
                    <span className={`${styles.badge} ${styles[tool.integration_status]}`}>
                      {tool.integration_status}
                    </span>
                  </div>
                  <p className={styles.toolCategory}>{tool.category}</p>
                </div>
              ))}
            </div>
          </section>

          <section className={`${styles.section} animate-fadeInUp stagger-5`}>
            <h3 className={styles.sectionTitle}>Generator Command</h3>
            <div className={styles.codeBlock}>
              <code>{commandString}</code>
              <button
                onClick={() => handleCopy(commandString, 'command')}
                className={styles.copyButton}
              >
                {copiedSection === 'command' ? (
                  <>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <path
                        d="M13 4L6 11L3 8"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    Copied!
                  </>
                ) : (
                  <>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <rect x="5" y="5" width="9" height="9" rx="1" stroke="currentColor" strokeWidth="2" />
                      <path d="M3 11V3C3 2.44772 3.44772 2 4 2H12" stroke="currentColor" strokeWidth="2" />
                    </svg>
                    Copy
                  </>
                )}
              </button>
            </div>
          </section>
        </div>

        <div className={styles.sidebar}>
          <div className={`${styles.sidebarCard} animate-fadeInUp stagger-6`}>
            <h3 className={styles.sidebarTitle}>Next Steps</h3>
            <ol className={styles.stepsList}>
              <li>
                <strong>Clone the repository</strong>
                <p>Get the WorkspaceAlberta code from GitHub</p>
              </li>
              <li>
                <strong>Run the generator</strong>
                <p>Use the command above to generate your configuration files</p>
              </li>
              <li>
                <strong>Add your API keys</strong>
                <p>Fill in the generated .env file with your credentials</p>
              </li>
              <li>
                <strong>Open in Cursor</strong>
                <p>Launch Cursor IDE and start using your AI workspace</p>
              </li>
            </ol>

            <button
              onClick={handleDownload}
              className={`btn-primary ${styles.downloadButton}`}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path
                  d="M10 14L5 9L6.41 7.59L9 10.17V2H11V10.17L13.59 7.59L15 9L10 14ZM4 18C3.45 18 2.979 17.804 2.587 17.412C2.195 17.02 1.99933 16.5493 2 16V13H4V16H16V13H18V16C18 16.55 17.804 17.021 17.412 17.413C17.02 17.805 16.5493 18.0007 16 18H4Z"
                  fill="currentColor"
                />
              </svg>
              Download Configuration
            </button>

            <div className={styles.actions}>
              <button onClick={onBack} className={`btn-outline ${styles.actionButton}`}>
                ← Edit Problem
              </button>
              <button onClick={onRestart} className={`btn-outline ${styles.actionButton}`}>
                ⟳ Start Over
              </button>
            </div>
          </div>

          <div className={`${styles.sidebarCard} ${styles.helpCard} animate-fadeInUp stagger-7`}>
            <h3 className={styles.sidebarTitle}>Need Help?</h3>
            <p className={styles.helpText}>
              Check out the WorkspaceAlberta documentation on GitHub for detailed setup instructions
              and troubleshooting guides.
            </p>
            <a
              href="https://github.com/yourusername/WorkspaceAlberta"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.helpLink}
            >
              View Documentation →
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
