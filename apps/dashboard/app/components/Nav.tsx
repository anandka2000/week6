import Link from "next/link";

const links = [
  { href: "/", label: "Home" },
  { href: "/niches", label: "Niches" },
  { href: "/trends", label: "Trends" },
  { href: "/videos", label: "Videos" },
  { href: "/review", label: "Review" },
  { href: "/metrics", label: "Metrics" },
  { href: "/costs", label: "Costs" },
];

export function Nav() {
  return (
    <nav className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur sticky top-0 z-10">
      <div className="mx-auto max-w-5xl px-6 py-3 flex items-center gap-6">
        <span className="font-semibold tracking-tight">ShortStack</span>
        <ul className="flex gap-4 text-sm text-zinc-400">
          {links.map((l) => (
            <li key={l.href}>
              <Link href={l.href} className="hover:text-zinc-100 transition-colors">
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
