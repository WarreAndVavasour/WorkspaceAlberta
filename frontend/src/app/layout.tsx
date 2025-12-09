import type { Metadata } from 'next'
import '../styles/globals.css'

export const metadata: Metadata = {
  title: 'WorkspaceAlberta - AI-Powered Business Tools for Alberta Entrepreneurs',
  description: 'Connect your business tools to an intelligent AI assistant. Built for Alberta small business owners.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
