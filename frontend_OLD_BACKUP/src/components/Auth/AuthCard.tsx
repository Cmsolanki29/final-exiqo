import type { ReactNode } from "react";

export type AuthCardProps = {
  title: string;
  lead: string;
  error: string;
  children: ReactNode;
  footer: ReactNode;
  formTopClass?: string;
};

export function AuthCard({ title, lead, error, children, footer, formTopClass }: AuthCardProps) {
  const formMargin = formTopClass ?? (error ? "mt-6" : "mt-9");

  return (
    <div className="relative w-full max-w-[460px] rounded-[28px] border border-white/[0.08] bg-white/[0.05] p-8 shadow-[0_28px_80px_rgba(0,0,0,0.5),0_0_0_1px_rgba(255,255,255,0.04)_inset,0_0_64px_rgba(139,92,246,0.07)] backdrop-blur-xl before:pointer-events-none before:absolute before:inset-0 before:rounded-[28px] before:bg-gradient-to-br before:from-white/[0.06] before:via-transparent before:to-violet-500/[0.03] before:opacity-60 before:content-[''] md:p-10">
      <h2 className="relative text-[1.7rem] font-bold leading-snug tracking-tight text-white md:text-[1.95rem]">
        {title}
      </h2>
      <p className="relative mt-3 text-[15px] font-normal leading-relaxed text-slate-400 md:text-[15.5px]">
        {lead}
      </p>

      {error ? (
        <div
          className="relative mt-6 rounded-xl border border-red-400/35 bg-red-500/[0.11] px-4 py-3.5 text-sm text-red-100"
          role="alert"
        >
          {error}
        </div>
      ) : null}

      <div className={`relative ${formMargin}`}>{children}</div>

      <div className="relative mt-8">{footer}</div>
    </div>
  );
}
