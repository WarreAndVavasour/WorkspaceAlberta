'use client'

import { useState, useMemo } from 'react'
import styles from './ToolSelector.module.css'
import catalog from '@/data/catalog.json'

interface Tool {
  id: string
  display_name: string
  category: string
  description: string
  integration_status: string
}

interface ToolSelectorProps {
  onSelect: (tools: string[]) => void
  initialSelection: string[]
}

export default function ToolSelector({ onSelect, initialSelection }: ToolSelectorProps) {
  const [selected, setSelected] = useState<string[]>(initialSelection)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterCategory, setFilterCategory] = useState<string>('all')

  const categories = useMemo(() => {
    const cats = new Set(catalog.map((tool: Tool) => tool.category))
    return ['all', ...Array.from(cats).sort()]
  }, [])

  const filteredTools = useMemo(() => {
    return catalog.filter((tool: Tool) => {
      const matchesSearch =
        tool.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tool.description.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesCategory = filterCategory === 'all' || tool.category === filterCategory
      return matchesSearch && matchesCategory
    })
  }, [searchQuery, filterCategory])

  const toggleTool = (toolId: string) => {
    setSelected(prev =>
      prev.includes(toolId)
        ? prev.filter(id => id !== toolId)
        : [...prev, toolId]
    )
  }

  const handleContinue = () => {
    if (selected.length > 0) {
      onSelect(selected)
    }
  }

  const getStatusBadge = (status: string) => {
    const badges: { [key: string]: string } = {
      'native': 'Ready',
      'openapi': 'API',
      'proxy': 'Custom',
      'hosted': 'Cloud'
    }
    return badges[status] || status
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className="container">
          <h2 className={`${styles.title} animate-fadeInUp`}>
            Which tools do you use?
          </h2>
          <p className={`${styles.subtitle} animate-fadeInUp stagger-1`}>
            Select the business tools you already have. We'll connect them to your AI workspace.
          </p>

          <div className={`${styles.controls} animate-fadeInUp stagger-2`}>
            <input
              type="text"
              placeholder="Search tools..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={styles.searchInput}
            />

            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className={styles.categorySelect}
            >
              {categories.map(cat => (
                <option key={cat} value={cat}>
                  {cat === 'all' ? 'All Categories' : cat}
                </option>
              ))}
            </select>
          </div>

          <div className={`${styles.selectedCount} animate-fadeInUp stagger-3`}>
            <span className={styles.countNumber}>{selected.length}</span>
            <span className={styles.countLabel}>tools selected</span>
          </div>
        </div>
      </div>

      <div className={`${styles.toolGrid} container`}>
        {filteredTools.map((tool: Tool, index: number) => {
          const isSelected = selected.includes(tool.id)
          const animationDelay = Math.min(index * 0.03, 0.5)

          return (
            <div
              key={tool.id}
              className={`${styles.toolCard} ${isSelected ? styles.selected : ''} animate-fadeInUp`}
              style={{ animationDelay: `${animationDelay}s`, opacity: 0 }}
              onClick={() => toggleTool(tool.id)}
            >
              <div className={styles.cardHeader}>
                <h3 className={styles.toolName}>{tool.display_name}</h3>
                <span className={`${styles.statusBadge} ${styles[tool.integration_status]}`}>
                  {getStatusBadge(tool.integration_status)}
                </span>
              </div>
              <p className={styles.toolDescription}>{tool.description}</p>
              <div className={styles.toolCategory}>{tool.category}</div>

              {isSelected && (
                <div className={styles.checkmark}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M20 6L9 17L4 12"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className={styles.footer}>
        <button
          onClick={handleContinue}
          disabled={selected.length === 0}
          className={`btn-accent ${styles.continueButton}`}
        >
          Continue with {selected.length} tool{selected.length !== 1 ? 's' : ''}
          <span className={styles.arrow}>→</span>
        </button>
      </div>
    </div>
  )
}
