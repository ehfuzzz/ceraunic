import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WI · weather cover",
  description:
    "Weather cover for small businesses, priced from their own sales. Testnet prototype.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
