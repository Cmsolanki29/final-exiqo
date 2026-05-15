import { motion, useReducedMotion } from "framer-motion";

export interface BankCardProps {
  id: string;
  name: string;
  logo: string;
  onSelect: (id: string) => void;
  index?: number;
}

export function BankCard({ id, name, logo, onSelect, index = 0 }: BankCardProps) {
  const reduce = useReducedMotion();
  return (
    <motion.button
      type="button"
      layout
      initial={reduce ? undefined : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: reduce ? 0 : 0.06 * index, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      whileHover={reduce ? undefined : { scale: 1.03, y: -2 }}
      whileTap={reduce ? undefined : { scale: 0.99 }}
      onClick={() => onSelect(id)}
      aria-label={`Connect ${name} via Account Aggregator`}
      className="group relative flex w-full flex-col items-stretch rounded-2xl border border-slate-600/50 bg-slate-800/60 p-6 text-left shadow-[0_20px_50px_rgba(0,0,0,0.35)] backdrop-blur-xl transition-colors duration-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400/70 md:p-8"
    >
      <span
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          boxShadow: "inset 0 0 0 1px rgba(139,92,246,0.35), 0 0 40px rgba(139,92,246,0.15)",
        }}
        aria-hidden
      />
      <div className="mb-4 text-5xl md:text-6xl" aria-hidden>
        {logo}
      </div>
      <h3 className="mb-2 text-lg font-semibold text-white md:text-xl">{name}</h3>
      <div className="text-sm font-medium text-gray-300 transition group-hover:text-fuchsia-300">
        Connect via AA →
      </div>
    </motion.button>
  );
}
