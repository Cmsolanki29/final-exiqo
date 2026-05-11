import React, { useEffect, useMemo, useState } from "react";
import { Bell, ChevronDown, Search, Settings } from "lucide-react";

const selectClass =
  "h-12 w-full appearance-none cursor-pointer rounded-xl border border-exiqo-purple/35 bg-exiqo-dark/50 " +
  "pl-3.5 pr-9 text-sm font-medium text-white transition-all duration-200 " +
  "hover:border-exiqo-purple/55 hover:bg-exiqo-dark/70 " +
  "focus:border-exiqo-purple focus:outline-none focus:ring-2 focus:ring-exiqo-purple/40";

const TopBar = ({
  userName = "User",
  month,
  year,
  onMonthChange,
  onYearChange,
}) => {
  const [greeting, setGreeting] = useState("Good Morning");

  useEffect(() => {
    const hour = new Date().getHours();
    if (hour < 12) setGreeting("Good Morning");
    else if (hour < 17) setGreeting("Good Afternoon");
    else setGreeting("Good Evening");
  }, []);

  const yearOptions = useMemo(() => {
    const y = new Date().getFullYear();
    return [y - 2, y - 1, y, y + 1];
  }, []);

  const displayName = userName?.trim() || "User";
  const initial = displayName.charAt(0).toUpperCase() || "U";

  return (
    <header className="sticky top-0 z-40 border-b border-exiqo-purple/15 bg-exiqo-navy/95 backdrop-blur-xl">
      <div className="mx-auto flex h-[4.75rem] max-w-[1920px] items-center gap-4 px-4 sm:gap-5 sm:px-6 lg:px-8">
        {/* Left — tighter copy, no cramped duplicate line */}
        <div className="min-w-0 shrink-0 lg:max-w-[min(18rem,28vw)]">
          <h1 className="truncate text-lg font-semibold leading-snug tracking-tight text-white sm:text-xl">
            <span className="bg-gradient-to-r from-white via-exiqo-glow to-exiqo-pink bg-clip-text text-transparent">
              {greeting}, {displayName}
            </span>
          </h1>
          <p className="mt-0.5 truncate text-[11px] font-medium text-exiqo-glow/45 sm:text-xs">
            Spend intelligence overview
          </p>
        </div>

        {/* Center: search — larger, no shortcut badge */}
        <div className="hidden min-w-0 flex-1 items-center justify-center md:flex">
          <div className="relative w-full max-w-2xl">
            <label htmlFor="topbar-search" className="sr-only">
              Search transactions and merchants
            </label>
            <div className="pointer-events-none absolute left-4 top-1/2 z-10 -translate-y-1/2">
              <Search className="h-5 w-5 text-exiqo-purple" strokeWidth={2.5} aria-hidden />
            </div>
            <input
              id="topbar-search"
              type="search"
              name="q"
              placeholder="Search transactions, merchants..."
              autoComplete="off"
              className="h-12 w-full rounded-xl border-2 border-exiqo-purple/40 bg-exiqo-dark/60 py-0 pl-12 pr-4 text-base font-medium text-white placeholder:text-exiqo-glow/40 transition-all duration-200 hover:border-exiqo-purple/60 hover:bg-exiqo-dark/80 focus:border-exiqo-purple focus:outline-none focus:ring-2 focus:ring-exiqo-purple/50"
            />
          </div>
        </div>

        {/* Right — same height (h-12) as search */}
        <div className="flex shrink-0 items-center gap-2 sm:gap-2.5">
          <div className="relative w-[6.5rem] sm:w-[7.25rem]">
            <select
              value={month}
              onChange={(e) => onMonthChange(Number(e.target.value))}
              className={selectClass}
            >
              {Array.from({ length: 12 }).map((_, idx) => (
                <option key={idx + 1} value={idx + 1} className="bg-exiqo-navy text-white">
                  {new Date(year, idx, 1).toLocaleDateString("en-IN", { month: "short" })}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-exiqo-purple/90" />
          </div>

          <div className="relative min-w-[100px]">
            <select
              value={year}
              onChange={(e) => onYearChange(Number(e.target.value))}
              className="h-12 min-w-[100px] w-full cursor-pointer appearance-none rounded-xl border-2 border-exiqo-purple/40 bg-exiqo-dark/60 pl-4 pr-10 text-base font-semibold text-white transition-all duration-200 hover:border-exiqo-purple/60 hover:bg-exiqo-dark/80 focus:border-exiqo-purple focus:outline-none focus:ring-2 focus:ring-exiqo-purple/50"
            >
              {yearOptions.map((y) => (
                <option key={y} value={y} className="bg-exiqo-navy text-white">
                  {y}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-exiqo-purple" />
          </div>

          <button
            type="button"
            className="group relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-exiqo-purple/35 bg-exiqo-dark/50 transition hover:border-exiqo-purple/55 hover:bg-exiqo-purple/15"
          >
            <Bell className="h-[18px] w-[18px] text-exiqo-glow transition-colors group-hover:text-exiqo-pink" strokeWidth={2} />
            <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-exiqo-pink ring-2 ring-exiqo-navy" />
          </button>

          <button
            type="button"
            className="group flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-exiqo-purple/35 bg-exiqo-dark/50 transition hover:border-exiqo-purple/55 hover:bg-exiqo-purple/15"
          >
            <Settings className="h-[18px] w-[18px] text-exiqo-glow transition-colors group-hover:text-exiqo-pink" strokeWidth={2} />
          </button>

          <button
            type="button"
            className="flex h-12 shrink-0 items-center gap-2 rounded-xl border border-exiqo-purple/40 bg-gradient-to-r from-exiqo-purple/12 to-exiqo-pink/12 px-2.5 transition hover:border-exiqo-purple/60 sm:pr-3"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-exiqo-purple to-exiqo-pink text-xs font-bold text-white shadow-md">
              {initial}
            </div>
            <div className="hidden min-w-0 max-w-[7rem] text-left md:block lg:max-w-[9rem]">
              <p className="truncate text-xs font-medium leading-tight text-white">{displayName}</p>
              <p className="text-[10px] font-medium leading-tight text-exiqo-pink/90">Premium</p>
            </div>
          </button>
        </div>
      </div>
    </header>
  );
};

export default TopBar;
