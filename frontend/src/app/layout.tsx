import type { Metadata } from "next";
import { Workspace } from "@/components/Workspace";
import "./globals.css";
import "./workspace.css";

export const metadata: Metadata = {
  title: "Vanco AI | Document Intelligence",
  description: "A secure multi-modal document intelligence workspace.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><Workspace>{children}</Workspace></body></html>;
}
