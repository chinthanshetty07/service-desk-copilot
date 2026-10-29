I built an independent prototype, a Service Desk Copilot, after reading your AI Engineer posting and your
Freshworks "AI Automation" work. It's a FastAPI service that retrieves knowledge-base articles from a FAISS
index, drafts a cited reply (offline or with Claude via structured outputs), sets priority, suggests safe
automations like password resets, and hands tickets to a human when retrieval isn't confident. It redacts
personal details before any model call and records latency, tokens and cost per request. There's a small
Next.js screen, Docker, CI, 30 tests and an evaluation gate. All data is synthetic; it isn't an official
Augustinnovate project.
