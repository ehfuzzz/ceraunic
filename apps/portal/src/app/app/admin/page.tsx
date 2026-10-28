import type { Metadata } from "next";
import { AdminBoard } from "@/components/AdminBoard";

export const metadata: Metadata = { title: "Admin | WI · weather cover" };

export default function AdminPage() {
  return <AdminBoard />;
}
