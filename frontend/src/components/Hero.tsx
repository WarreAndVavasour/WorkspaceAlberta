'use client'

import styles from './Hero.module.css'

interface HeroProps {
  onStart: () => void
}

export default function Hero({ onStart }: HeroProps) {
  return (
    <div className={`${styles.hero} topo-background`}>
      <div className={styles.heroContent}>
        <div className={`${styles.badge} animate-fadeIn stagger-1`}>
          <span className={styles.badgeIcon}>🏔️</span>
          <span>Built for Alberta</span>
        </div>

        <h1 className={`${styles.title} animate-fadeInUp stagger-2`}>
          Your Business Tools,
          <br />
          <span className={styles.titleAccent}>One Smart Workspace</span>
        </h1>

        <p className={`${styles.subtitle} animate-fadeInUp stagger-3`}>
          Connect the tools you already use to an AI assistant that understands your business.
          <br />
          No technical knowledge required. Just two simple questions to get started.
        </p>

        <div className={`${styles.stats} animate-fadeInUp stagger-4`}>
          <div className={styles.stat}>
            <div className={styles.statNumber}>50+</div>
            <div className={styles.statLabel}>Business Tools</div>
          </div>
          <div className={styles.stat}>
            <div className={styles.statNumber}>2</div>
            <div className={styles.statLabel}>Questions</div>
          </div>
          <div className={styles.stat}>
            <div className={styles.statNumber}>5min</div>
            <div className={styles.statLabel}>Setup Time</div>
          </div>
        </div>

        <button
          onClick={onStart}
          className={`btn-accent ${styles.ctaButton} animate-fadeInUp stagger-5`}
        >
          Build Your Workspace
          <span className={styles.arrow}>→</span>
        </button>

        <div className={`${styles.trustBadge} animate-fadeIn stagger-5`}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path
              d="M8 0L10.163 5.837L16 8L10.163 10.163L8 16L5.837 10.163L0 8L5.837 5.837L8 0Z"
              fill="currentColor"
            />
          </svg>
          <span>No credit card • No API keys stored • Open source</span>
        </div>
      </div>

      <div className={styles.heroVisual}>
        <div className={styles.mountainLayer1}></div>
        <div className={styles.mountainLayer2}></div>
        <div className={styles.mountainLayer3}></div>
      </div>
    </div>
  )
}
