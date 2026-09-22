import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import { Radar } from "lucide-react";

export const metadata: Metadata = {
  title: "Competitor Finder | Live Global Competitor Intelligence",
  description:
    "Discover, verify, and rank real competitors worldwide for any business with live search and zero hallucination.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen flex flex-col bg-slate-950 text-slate-100 antialiased selection:bg-emerald-500 selection:text-white">
        {/* Navigation Header */}
        <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2.5 font-bold text-lg text-white group">
              <div className="w-8 h-8 rounded-lg bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 group-hover:border-emerald-400 transition-colors">
                <Radar className="w-5 h-5" />
              </div>
              <span className="tracking-tight">
                CompFinder<span className="text-emerald-400">.ai</span>
              </span>
            </Link>

            <nav className="flex items-center gap-4 text-sm">
              <Link
                href="/login"
                className="px-3 py-1.5 rounded-lg text-slate-300 hover:text-white transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/register"
                className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-colors"
              >
                Get Started
              </Link>
            </nav>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8">
          {children}
        </main>

        {/* Footer */}
        <footer className="border-t border-slate-800/80 py-6 text-center text-xs text-slate-500">
          <p>CompFinder AI • Strict Live-Source Verification • Zero LLM Hallucination</p>
        </footer>
      </body>
    </html>
  );
}
