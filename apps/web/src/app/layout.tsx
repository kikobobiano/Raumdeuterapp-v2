import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import { Suspense } from "react";

import { Sidebar } from "@/components/shell/sidebar";
import { TopBar } from "@/components/shell/top-bar";
import { RouteProgress } from "@/components/ui/loading";
import { QueryProvider } from "@/lib/query-provider";
import { SeasonSync } from "@/lib/season-sync";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "RaumdeuterApp",
  description: "Elite football performance data",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${spaceGrotesk.variable} h-full antialiased`}
    >
      <body className="flex h-full">
        <QueryProvider>
          <Suspense fallback={null}>
            <RouteProgress />
          </Suspense>
          <SeasonSync>
            <Sidebar />
            <div className="flex flex-1 flex-col overflow-hidden">
              <Suspense
                fallback={
                  <header className="h-16 shrink-0 border-b border-outline-variant bg-surface px-8" />
                }
              >
                <TopBar />
              </Suspense>
              <main className="flex-1 overflow-y-auto p-8">{children}</main>
            </div>
          </SeasonSync>
        </QueryProvider>
      </body>
    </html>
  );
}
