"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, ArrowUpRight, BookOpen, ChevronDown, Files, LayoutDashboard, LogOut, Menu, MessageSquareText, ShieldCheck, Sparkles, X } from "lucide-react";
import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { api, User } from "@/lib/api";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

const navigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/documents", label: "Documents", icon: Files },
  { href: "/chat", label: "Ask workspace", icon: MessageSquareText },
  { href: "/admin", label: "Observability", icon: Activity },
];

export function Workspace({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [mobileNav, setMobileNav] = useState(false);
  const pageContentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("vanco.access_token");
    if (!token) {
      setChecking(false);
      return;
    }
    api<User>("/auth/me").then(setUser).catch(() => localStorage.removeItem("vanco.access_token")).finally(() => setChecking(false));
  }, []);

  function signOut() {
    localStorage.removeItem("vanco.access_token");
    setUser(null);
    router.refresh();
  }

  useGSAP(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const root = pageContentRef.current;
    if (!root) return;

    const heading = root.querySelector(".page-heading");
    if (heading) gsap.fromTo(heading, { autoAlpha: 0, y: 8 }, { autoAlpha: 1, y: 0, duration: 0.38, ease: "power2.out" });

    gsap.utils.toArray<HTMLElement>(".metric-tile, .admin-metric, .health-panel, .pipeline-panel", root).forEach((item) => {
      gsap.fromTo(item, { autoAlpha: 0, y: 10, scale: 0.99 }, {
        autoAlpha: 1,
        y: 0,
        scale: 1,
        duration: 0.42,
        ease: "power2.out",
        scrollTrigger: { trigger: item, start: "top 96%", toggleActions: "play none none none" },
      });
    });

    const overviewTitle = root.querySelector(".welcome-copy h2");
    if (overviewTitle) gsap.fromTo(overviewTitle, { opacity: 0.72 }, {
      opacity: 1,
      ease: "none",
      scrollTrigger: { trigger: overviewTitle, start: "top 82%", end: "bottom 44%", scrub: 0.4 },
    });
  }, { scope: pageContentRef, dependencies: [pathname, user?.id], revertOnUpdate: true });

  if (checking) return <div className="app-loading"><span className="loading-mark"><Sparkles size={18} /></span>Opening your workspace</div>;
  if (!user) return <AccessScreen onAccess={setUser} />;

  return (
    <div className="workspace">
      <button aria-label="Open navigation" className="mobile-menu icon-button" onClick={() => setMobileNav(true)}><Menu size={19} /></button>
      {mobileNav && <button aria-label="Close navigation" className="nav-scrim" onClick={() => setMobileNav(false)} />}
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand"><span className="brand-mark"><Sparkles size={17} strokeWidth={2.3} /></span><span>vanco<span className="brand-light">.ai</span></span><button aria-label="Close navigation" className="icon-button close-nav" onClick={() => setMobileNav(false)}><X size={18} /></button></div>
        <div className="workspace-switch"><span className="workspace-avatar">V</span><span className="workspace-name"><strong>Vertex Partners</strong><small>Enterprise workspace</small></span><ChevronDown size={14} /></div>
        <p className="nav-label">WORKSPACE</p>
        <nav className="main-nav" aria-label="Workspace navigation">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} onClick={() => setMobileNav(false)} className={`nav-link ${pathname === href ? "nav-link-active" : ""}`}><Icon size={17} strokeWidth={1.8} /><span>{label}</span>{href === "/documents" && <span className="nav-count"><BookOpen size={12} /></span>}</Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="secure-note"><ShieldCheck size={15} /><span>Private by default</span><span className="secure-dot" /></div>
          <div className="account-row"><div className="account-avatar">{user.email.slice(0, 1).toUpperCase()}</div><div className="account-copy"><strong>{user.email.split("@")[0]}</strong><small>{user.email}</small></div><button title="Sign out" aria-label="Sign out" className="icon-button" onClick={signOut}><LogOut size={16} /></button></div>
        </div>
      </aside>
      <main className="main-area"><header className="topbar"><div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>{navigation.find((item) => item.href === pathname)?.label ?? "Overview"}</strong></div><div className="topbar-right"><span className="system-status"><span />All systems operational</span><div className="topbar-divider" /><span className="topbar-date">{new Intl.DateTimeFormat("en", { weekday: "short", month: "short", day: "numeric" }).format(new Date())}</span><button className="top-avatar" title={user.email}>{user.email.slice(0, 1).toUpperCase()}</button></div></header><div ref={pageContentRef} className="page-content">{children}</div><footer className="page-footer"><span>VANCO INTELLIGENCE</span><span>Secure document workspace <span className="footer-separator">·</span> v1.0</span></footer></main>
    </div>
  );
}

function AccessScreen({ onAccess }: { onAccess: (user: User) => void }) {
  const [registering, setRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<{ access_token: string; user: User }>(registering ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      localStorage.setItem("vanco.access_token", result.access_token);
      onAccess(result.user);
    } catch (cause) {
      setError(cause instanceof TypeError ? "Vanco API is unavailable. Start the services with docker compose up --build from the project folder, then retry." : cause instanceof Error ? cause.message : "Unable to authenticate");
    } finally {
      setBusy(false);
    }
  }

  return <main className="access-page"><div className="access-aside"><div className="access-brand"><span className="brand-mark"><Sparkles size={17} /></span><span>vanco<span className="brand-light">.ai</span></span></div><div className="access-message"><span className="eyebrow"><span className="eyebrow-dot" /> DOCUMENT INTELLIGENCE</span><h1>Knowledge that<br /><em>moves with you.</em></h1><p>One secure place to bring your documents into focus, find the details that matter, and move work forward.</p><div className="access-quote"><span>“</span><div><p>Your documents, connected to the decisions you make every day.</p><small>VANCO WORKSPACE</small></div></div></div><span className="aside-footer">BUILT FOR THE WORK BEHIND THE WORK</span></div><section className="access-panel"><div className="access-form-wrap"><span className="access-icon"><ArrowUpRight size={20} /></span><p className="eyebrow">YOUR PRIVATE WORKSPACE</p><h2>{registering ? "Create your account" : "Welcome back"}</h2><p className="access-subtitle">{registering ? "Start a secure document workspace." : "Sign in to continue to your workspace."}</p><form className="access-form" onSubmit={submit}><label htmlFor="email">Work email</label><input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /><label htmlFor="password">Password</label><input id="password" type="password" autoComplete={registering ? "new-password" : "current-password"} minLength={10} required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 10 characters" />{error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button access-submit" type="submit" disabled={busy}>{busy ? "Connecting…" : registering ? "Create secure account" : "Sign in to workspace"}<ArrowUpRight size={16} /></button></form><p className="access-toggle">{registering ? "Already have an account?" : "New to Vanco?"}<button onClick={() => { setRegistering(!registering); setError(""); }}>{registering ? "Sign in" : "Create an account"}</button></p><div className="access-security"><ShieldCheck size={15} /> Your workspace is private and encrypted in transit</div></div><span className="panel-footer">© 2026 VANCO AI <span>·</span> DOCUMENT INTELLIGENCE</span></section></main>;
}
