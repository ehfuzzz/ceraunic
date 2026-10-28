import { Header } from "@/components/Header";
import { Providers } from "@/components/Providers";
import { SideNav } from "@/components/SideNav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <Header />
      <div className="flex min-h-[calc(100dvh-69px)] flex-col md:flex-row">
        <SideNav />
        <main className="flex-1 px-6 py-10 md:px-16 md:py-14">{children}</main>
      </div>
    </Providers>
  );
}
