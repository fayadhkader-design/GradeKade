import type { Metadata, Viewport } from "next";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/dm-sans/700.css";
import "./globals.css";
import OCRMode from "@/components/OCRMode";
export const viewport: Viewport = {
  themeColor: "#1c5946",
  viewportFit: "cover",
};
export const metadata: Metadata = {
  appleWebApp: { capable: true, title: "GradeKade", statusBarStyle: "default" },
  title: "GradeKade · Grading workspace",
  description: "Local demo of assisted arithmetic worksheet grading.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <OCRMode />
        {children}
      </body>
    </html>
  );
}
