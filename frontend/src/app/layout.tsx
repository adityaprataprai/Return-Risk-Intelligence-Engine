import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Razorpay Return-Risk Intelligence Engine",
  description: "Real-time automated return abuse detection, TreeSHAP explainability, and risk investigation workbench.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="flex min-h-screen bg-[#080d1a] text-slate-100">
        {/* Left Navigation Sidebar */}
        <aside className="fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-800/80 bg-[#0c1324]/90 backdrop-blur-xl">
          {/* Brand Header */}
          <div className="flex h-16 items-center gap-3 border-b border-slate-800/80 px-6">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-blue-600 to-cyan-400 font-bold text-white shadow-md shadow-blue-500/20">
              ⚡
            </div>
            <div>
              <span className="text-sm font-bold tracking-tight text-white">Razorpay</span>
              <span className="block text-[10px] font-semibold uppercase tracking-wider text-blue-400">
                Return-Risk Engine
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 space-y-1.5 px-3 py-4 text-xs font-semibold">
            {[
              { href: "/overview", label: "Executive Overview", icon: "📊" },
              { href: "/review-queue", label: "Review Queue", icon: "📋" },
              { href: "/networks", label: "Network Explorer", icon: "🕸️" },
              { href: "/analytics", label: "Fraud & ROI Analytics", icon: "📈" },
              { href: "/policies", label: "Policy Simulator", icon: "⚖️" },
              { href: "/health", label: "System & Model Health", icon: "💚" },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-slate-400 transition hover:bg-slate-800/60 hover:text-white"
              >
                <span className="text-base">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            ))}
          </nav>

          {/* System Status Footer */}
          <div className="border-t border-slate-800/80 p-4">
            <div className="flex items-center justify-between rounded-lg bg-slate-900/80 p-2.5 border border-slate-800">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
                </span>
                <span className="text-[11px] font-medium text-slate-300">Engine Active</span>
              </div>
              <span className="text-[10px] font-mono text-slate-400">Port 8001</span>
            </div>
          </div>
        </aside>

        {/* Main Content Area */}
        <div className="flex flex-1 flex-col pl-64">
          {/* Top Bar */}
          <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-800/80 bg-[#080d1a]/80 px-8 backdrop-blur-md">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="rounded bg-blue-500/15 px-2 py-0.5 text-blue-400 font-mono font-semibold">
                Production Cluster
              </span>
              <span>•</span>
              <span>v1.0.0 (rr-lgbm-1.0.0)</span>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-400">Fraud Operations</span>
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-800 text-xs font-bold text-slate-200 border border-slate-700">
                FD
              </div>
            </div>
          </header>

          {/* Page Body */}
          <main className="flex-1 p-8">
            <div className="mx-auto max-w-7xl">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
