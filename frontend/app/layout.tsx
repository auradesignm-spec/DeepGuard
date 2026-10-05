import type { Metadata } from "next";
import { Chakra_Petch, IBM_Plex_Sans_Arabic, IBM_Plex_Mono } from "next/font/google";
import { LanguageProvider } from "@/lib/i18n";
import "./globals.css";

const chakra = Chakra_Petch({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-chakra",
  display: "swap",
});

const plexArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic", "latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-plex-arabic",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "DeepGuard — كشف التزييف العميق والفحوص الجنائية | Deepfake Detection",
  description:
    "منصة كشف التزوير العميق والفحوص الجنائية للصور — أربع إشارات كشف مستقلة وتحكيم موزون، محلياً بالكامل. Deepfake detection with four independent signals, weighted adjudication, fully local.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ar" dir="rtl" className={`dark ${chakra.variable} ${plexArabic.variable} ${plexMono.variable}`}>
      <body className="min-h-screen antialiased">
        <LanguageProvider>{children}</LanguageProvider>
      </body>
    </html>
  );
}
