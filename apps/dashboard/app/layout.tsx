import type { Metadata } from "next";
import { Nav } from "./components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "ShortStack",
  description: "AI short-video pipeline",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-zinc-950 text-zinc-100 antialiased min-h-screen">
        <Nav />
        <div className="mx-auto max-w-5xl px-6 py-8">{children}</div>
      </body>
    </html>
  );
}
