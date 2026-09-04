import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(amount)) return "₹0.00";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatPercent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined || isNaN(rate)) return "0.0%";
  return `${rate.toFixed(1)}%`;
}

export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return "-";
  try {
    const d = new Date(isoString);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return isoString;
  }
}

export function getActionBadgeClass(action: string): string {
  const act = action.toUpperCase();
  if (act.includes("APPROVE")) {
    return "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30";
  }
  if (act.includes("BLOCK") || act.includes("REJECT")) {
    return "bg-rose-500/15 text-rose-400 border border-rose-500/30";
  }
  if (act.includes("VERIFY") || act.includes("ESCALATE")) {
    return "bg-amber-500/15 text-amber-400 border border-amber-500/30";
  }
  return "bg-slate-500/15 text-slate-400 border border-slate-500/30";
}

export function getPriorityBadgeClass(priority: string): string {
  const p = priority.toUpperCase();
  if (p === "HIGH") {
    return "bg-rose-500/20 text-rose-300 font-semibold border border-rose-500/40";
  }
  if (p === "MEDIUM") {
    return "bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/40";
  }
  return "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40";
}
