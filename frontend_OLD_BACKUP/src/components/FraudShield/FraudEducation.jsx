import React, { useEffect, useState } from "react";
import { getFraudShieldPatterns } from "../../services/api";
import { ErrorCard } from "../common/ErrorCard";
import { SkeletonCard } from "../common/SkeletonCard";

const typeTitle = (t) => {
  const map = {
    KYC_FRAUD: "KYC Fraud",
    LOTTERY_FRAUD: "Lottery Fraud",
    UPI_COLLECT: "UPI Collect Fraud",
    JOB_FRAUD: "Job / Task Fraud",
    BANK_OFFICIAL: "Fake Bank Official",
    MONEY_DOUBLING: "Money Doubling",
  };
  return map[t] || t?.replace(/_/g, " ") || "Fraud";
};

const FraudEducation = () => {
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState("");
  const [quiz, setQuiz] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoadErr("");
        const data = await getFraudShieldPatterns();
        if (!cancelled) setPatterns(data.patterns || []);
      } catch (e) {
        if (!cancelled) {
          setPatterns([]);
          setLoadErr(e.message || "Failed to load patterns");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const signsList = (signs) => {
    if (!signs) return [];
    if (Array.isArray(signs)) return signs;
    try {
      const j = typeof signs === "string" ? JSON.parse(signs) : signs;
      return Array.isArray(j) ? j : [];
    } catch {
      return [];
    }
  };

  return (
    <div className="fraud-education glass-card">
      <header className="fraud-edu-head">
        <h3>📚 Fraud Awareness Center</h3>
        <p className="muted">Stay informed — protect your finances</p>
      </header>

      <p className="fraud-edu-intro">The most common frauds in India:</p>

      {loading ? (
        <div>
          <p className="muted small" style={{ marginBottom: 12 }}>
            Loading fraud patterns…
          </p>
          <SkeletonCard lines={4} height={200} />
        </div>
      ) : loadErr ? (
        <ErrorCard
          message={loadErr}
          onRetry={() => {
            setLoading(true);
            setLoadErr("");
            (async () => {
              try {
                const data = await getFraudShieldPatterns();
                setPatterns(data.patterns || []);
              } catch (e) {
                setLoadErr(e.message || "Failed to load patterns");
              } finally {
                setLoading(false);
              }
            })();
          }}
        />
      ) : (
        <div className="fraud-edu-cards">
          {patterns.map((p) => (
            <article key={p.id} className="fraud-edu-card">
              <div className={`fraud-edu-sev ${(p.severity || "").toLowerCase()}`}>
                {p.severity === "CRITICAL" ? "🔴" : "🟡"} {typeTitle(p.pattern_type)}
              </div>
              <p className="muted small">{p.pattern_name}</p>
              <p className="fraud-edu-desc">{p.description}</p>
              <strong>How to identify</strong>
              <ul>
                {signsList(p.warning_signs).map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
              <strong>Sample alert wording</strong>
              <blockquote className="fraud-edu-ai-sample">{p.hinglish_warning}</blockquote>
              <button
                type="button"
                className="btn-outline btn-small"
                onClick={() => document.getElementById("fraud-quiz-anchor")?.scrollIntoView({ behavior: "smooth" })}
              >
                Learn more
              </button>
            </article>
          ))}
        </div>
      )}

      <section id="fraud-quiz-anchor" className="fraud-quiz glass-card">
        <h4>🎯 Quick quiz: &quot;Is this a fraud?&quot;</h4>
        <p>
          Scenario: You get a call from &quot;SBI&quot; saying your account is blocked. They ask you to send ₹1
          to verify…
        </p>
        <div className="fraud-quiz-btns">
          <button type="button" className="btn-outline" onClick={() => setQuiz("wrong")}>
            ✅ Legitimate
          </button>
          <button type="button" className="btn-danger" onClick={() => setQuiz("right")}>
            🚨 FRAUD!
          </button>
        </div>
        {quiz === "right" && (
          <p className="fraud-quiz-feedback ok">
            Correct! That is a classic KYC / verification scam — banks never ask you to send money over UPI to
            &quot;verify&quot; your account.
          </p>
        )}
        {quiz === "wrong" && (
          <p className="fraud-quiz-feedback bad">
            Incorrect — it is still fraud. Even a ₹1 &quot;test&quot; can be part of the scam; real verification happens
            through your branch or the bank&apos;s official app only.
          </p>
        )}
      </section>

      <p className="muted small fraud-edu-foot">
        Report:{" "}
        <a href="https://cybercrime.gov.in" target="_blank" rel="noreferrer">
          cybercrime.gov.in
        </a>{" "}
        · Helpline <strong>1930</strong>
      </p>
    </div>
  );
};

export default FraudEducation;
