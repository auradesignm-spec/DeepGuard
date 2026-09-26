import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DeepGuard - AI Deepfake Detection & Forensic Analysis",
  description: "Enterprise-grade deepfake detection and forensic analysis platform powered by deep learning and automated forensic reporting.",
  openGraph: {
    title: "DeepGuard - AI Deepfake Detection & Forensic Analysis",
    description: "Enterprise-grade deepfake detection and forensic analysis platform powered by deep learning and automated forensic reporting.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#060911] text-slate-100 antialiased selection:bg-cyan-500 selection:text-black">
        {children}
      </body>
    </html>
  );
}
