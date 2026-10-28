export function PagePlaceholder({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="max-w-xl">
      <h1 className="font-display text-3xl tracking-tight">{title}</h1>
      <p className="mt-4 text-muted">{children}</p>
      <p className="mt-10 font-mono text-xs text-muted">Not built yet.</p>
    </section>
  );
}
