import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Zomato AI · Restaurant Recommendations',
  description: 'AI-powered restaurant recommendations',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-50/50">
        {children}
      </body>
    </html>
  );
}
