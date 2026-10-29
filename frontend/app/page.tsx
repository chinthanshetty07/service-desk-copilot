"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Citation = { id: string; title: string; score: number; cited: boolean };
type Result = {
  ticket_id: string;
  category: string;
  priority: "P1" | "P2" | "P3";
  confidence: number;
  abstained: boolean;
  reason: string;
  draft_reply: string;
  citations: Citation[];
  automation: { action: string; requires: string; status: string } | null;
  provider: string;
  redactions: number;
  usage: { input_tokens: number; output_tokens: number; cost_usd: number };
  timings: { retrieval_ms: number; generation_ms: number; total_ms: number };
};
type Metrics = {
  requests: number;
  latency_ms: { p50: number; p95: number };
  abstain_rate: number;
  automation_suggested: number;
  cost_usd: number;
};

const SAMPLES = [
  { subject: "Forgot my password", description: "My password expired this morning and I can't get into email." },
  { subject: "VPN down for everyone", description: "Nobody in the sales team can connect to the VPN." },
  { subject: "Clicked a phishing link", description: "I clicked a link in a suspicious email and entered my password. Reach me at ravi@example.com" },
  { subject: "Parking pass", description: "How do I get a parking sticker for the basement?" },
];

export default function Home() {
  const [subject, setSubject] = useState(SAMPLES[0].subject);
  const [description, setDescription] = useState(SAMPLES[0].description);
  const [result, setResult] = useState<Result | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function refreshMetrics() {
    try {
      setMetrics(await (await fetch(`${API}/metrics`)).json());
    } catch {
      /* metrics are optional on screen */
    }
  }

  useEffect(() => {
    refreshMetrics();
  }, []);

  async function triage(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/triage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, description }),
      });
      if (!res.ok) throw new Error(`API returned ${res.status}`);
      setResult(await res.json());
      refreshMetrics();
    } catch (err) {
      setError(`Could not reach the API at ${API}. Is it running? (${(err as Error).message})`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header>
        <h1>Service Desk Copilot</h1>
        <p className="muted">
          Independent prototype: retrieval-augmented triage and reply drafting for IT tickets. Synthetic knowledge base;
          not connected to any real service desk.
        </p>
      </header>

      <section className="grid">
        <form onSubmit={triage} className="card" aria-label="New ticket">
          <h2>New ticket</h2>
          <div className="samples" role="group" aria-label="Sample tickets">
            {SAMPLES.map((s) => (
              <button type="button" key={s.subject} onClick={() => { setSubject(s.subject); setDescription(s.description); }}>
                {s.subject}
              </button>
            ))}
          </div>
          <label>
            Subject
            <input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={200} required />
          </label>
          <label>
            Description
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={5} maxLength={5000} />
          </label>
          <button type="submit" className="primary" disabled={loading}>
            {loading ? "Triaging…" : "Triage ticket"}
          </button>
          {error && <p role="alert" className="error">{error}</p>}
        </form>

        <section className="card" aria-live="polite" aria-label="Triage result">
          <h2>Result</h2>
          {!result && <p className="muted">Submit a ticket to see the triage.</p>}
          {result && (
            <>
              <div className="badges">
                <span className={`badge ${result.priority.toLowerCase()}`}>{result.priority}</span>
                <span className="badge">{result.category}</span>
                <span className="badge">confidence {result.confidence.toFixed(2)}</span>
                {result.redactions > 0 && <span className="badge">{result.redactions} redacted</span>}
              </div>
              {result.abstained ? (
                <p className="notice">Routed to a human: {result.reason}</p>
              ) : (
                <p className="muted">{result.reason}</p>
              )}
              {result.automation && (
                <div className="automation">
                  <strong>Automation available: {result.automation.action.replace("_", " ")}</strong>
                  <span>Requires: {result.automation.requires}</span>
                  <span className="muted">Status: {result.automation.status}</span>
                </div>
              )}
              <h3>Draft reply</h3>
              <pre>{result.draft_reply}</pre>
              <h3>Knowledge base matches</h3>
              <ul className="citations">
                {result.citations.map((c) => (
                  <li key={c.id}>
                    <code>{c.id}</code> {c.title} <span className="muted">({c.score.toFixed(2)}{c.cited ? ", cited" : ""})</span>
                  </li>
                ))}
                {result.citations.length === 0 && <li className="muted">No close matches</li>}
              </ul>
              <p className="muted small">
                {result.provider} · retrieval {result.timings.retrieval_ms} ms · generation {result.timings.generation_ms} ms ·
                total {result.timings.total_ms} ms · {result.usage.input_tokens + result.usage.output_tokens} tokens · $
                {result.usage.cost_usd.toFixed(4)}
              </p>
            </>
          )}
        </section>
      </section>

      {metrics && (
        <section className="card metrics" aria-label="Service metrics">
          <h2>Live metrics</h2>
          <dl>
            <div><dt>Requests</dt><dd>{metrics.requests}</dd></div>
            <div><dt>Latency p50 / p95</dt><dd>{metrics.latency_ms.p50} / {metrics.latency_ms.p95} ms</dd></div>
            <div><dt>Routed to humans</dt><dd>{Math.round(metrics.abstain_rate * 100)}%</dd></div>
            <div><dt>Automations suggested</dt><dd>{metrics.automation_suggested}</dd></div>
            <div><dt>LLM cost</dt><dd>${metrics.cost_usd.toFixed(4)}</dd></div>
          </dl>
        </section>
      )}
    </main>
  );
}
