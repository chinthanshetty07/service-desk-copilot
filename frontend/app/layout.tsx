import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "Service Desk Copilot",
  description: "Independent prototype: RAG triage and reply drafting for IT service desks",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
