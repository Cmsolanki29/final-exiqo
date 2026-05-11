import React, { useEffect } from "react";
import { motion } from "framer-motion";

const SplashScreen = ({ onComplete, durationMs = 2800 }) => {
  useEffect(() => {
    const timer = window.setTimeout(() => {
      onComplete?.();
    }, durationMs);
    return () => window.clearTimeout(timer);
  }, [onComplete, durationMs]);

  return (
    <div className="relative min-h-screen overflow-hidden bg-exiqo-navy">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -right-16 -top-20 h-[560px] w-[560px] rounded-full bg-exiqo-purple/12 blur-[130px]" />
        <div className="absolute -bottom-20 -left-16 h-[520px] w-[520px] rounded-full bg-exiqo-pink/10 blur-[120px]" />
      </div>

      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <motion.img
          src="/smartspend-shield-logo.png"
          alt="SmartSpend"
          className="mb-6 h-40 w-40 rounded-2xl shadow-2xl shadow-exiqo-purple/30 sm:h-48 sm:w-48"
          initial={{ opacity: 0, scale: 0.85, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        />

        <motion.h1
          className="mb-2 text-3xl font-extrabold tracking-tight text-white sm:text-4xl"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
        >
          SmartSpend
        </motion.h1>
        <motion.p
          className="text-sm text-exiqo-glow/75 sm:text-base"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35, duration: 0.5 }}
        >
          AI-powered financial intelligence
        </motion.p>

        <motion.div
          className="mt-8 h-1.5 w-52 overflow-hidden rounded-full bg-white/10"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.45, duration: 0.4 }}
        >
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-exiqo-purple via-fuchsia-400 to-cyan-400"
            initial={{ width: "0%" }}
            animate={{ width: "100%" }}
            transition={{ duration: durationMs / 1000, ease: "linear" }}
          />
        </motion.div>
      </div>
    </div>
  );
};

export default SplashScreen;
