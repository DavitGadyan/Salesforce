import type { Metadata } from "next";
import { IBM_Plex_Mono, Poppins, Source_Sans_3 } from "next/font/google";
import { Shell } from "@/components/shell";
import "./globals.css";

// Open stand-ins for Salesforce Sans (body) and ITC Avant Garde (display), which are not licensed for reuse.
const body = Source_Sans_3({ variable: "--font-body", subsets: ["latin"], weight: ["400", "500", "600", "700"] });
const display = Poppins({ variable: "--font-poppins", subsets: ["latin"], weight: ["500", "600"] });
const mono = IBM_Plex_Mono({ variable: "--font-plex-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "SF Ops Copilot",
  description: "Sandbox refresh & migration, an AI revenue agent and Apex/Flow review for Salesforce, with human approval on every write.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${body.variable} ${display.variable} ${mono.variable}`}>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
