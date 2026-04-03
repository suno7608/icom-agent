import { useState, useEffect, useRef, useMemo, useCallback, createContext, useContext } from "react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, AreaChart, Area, Cell } from "recharts";
import { Search, Bell, Settings, LayoutDashboard, Megaphone, Users, Package, FileText, Sparkles, ChevronDown, TrendingUp, TrendingDown, AlertTriangle, Zap, ArrowRight, MoreVertical, Download, Filter, Plus, ExternalLink, Shield, Clock, Target, Bot, Send, Eye, Activity, BookOpen, ChevronRight, CheckCircle2, Play, Lightbulb, MousePointerClick, BarChart3, Globe, Lock, Rocket, HelpCircle, Info, MessageSquare, X, ThumbsUp, ThumbsDown, RefreshCw, CircleDot } from "lucide-react";

/* ═══════════════════════════════════════════════════
   ICOM Agent — "Neon-Glass Protocol" Design System
   Full SPA Implementation
   ═══════════════════════════════════════════════════ */

// ─── Design Tokens ───────────────────────────────
const T = {
  surface: "#111318",
  surfaceDim: "#0d0f14",
  surfaceContainerLowest: "#0c0e12",
  surfaceContainerLow: "#171a21",
  surfaceContainer: "#1b1e26",
  surfaceContainerHigh: "#22262f",
  surfaceContainerHighest: "#2a2e38",
  surfaceVariant: "#3a3f4b",
  surfaceTint: "#00f0ff",
  primary: "#00f0ff",
  primaryDim: "#00c4d4",
  primaryContainer: "#00f0ff",
  primaryFixed: "#dbfcff",
  primaryFixedDim: "#88e8f2",
  onPrimary: "#003738",
  onPrimaryContainer: "#002021",
  secondary: "#c77dff",
  secondaryContainer: "#7b2cbf",
  onSecondary: "#1a0033",
  onSecondaryContainer: "#e8d0ff",
  tertiary: "#00e676",
  tertiaryContainer: "#004d25",
  onTertiary: "#003314",
  error: "#ff6b6b",
  errorContainer: "#93000a",
  onSurface: "#e2e4ea",
  onSurfaceVariant: "#a0a4b0",
  outline: "#5a5e6a",
  outlineVariant: "#44484f",
};

const font = {
  display: "'Space Grotesk', sans-serif",
  body: "'Inter', sans-serif",
};

// ─── Global Styles (injected once) ───────────────
const GlobalStyles = () => {
  useEffect(() => {
    const id = "icom-global-styles";
    if (document.getElementById(id)) return;
    const style = document.createElement("style");
    style.id = id;
    style.textContent = `
      @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap');
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
      body { background: ${T.surface}; color: ${T.onSurface}; font-family: ${font.body}; overflow-x: hidden; }
      ::-webkit-scrollbar { width: 6px; }
      ::-webkit-scrollbar-track { background: ${T.surfaceContainerLow}; }
      ::-webkit-scrollbar-thumb { background: ${T.surfaceVariant}; border-radius: 3px; }
      @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
      @keyframes glow { 0%,100% { box-shadow: 0 0 8px ${T.primary}40; } 50% { box-shadow: 0 0 20px ${T.primary}60; } }
      @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
      @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
      @keyframes slideInRight { from { transform: translateX(100%); } to { transform: translateX(0); } }
      .animate-in { animation: slideUp 0.5s ease-out forwards; }
      .pulse-dot { animation: pulse 2s ease-in-out infinite; }
      .glow-border { animation: glow 3s ease-in-out infinite; }
    `;
    document.head.appendChild(style);
  }, []);
  return null;
};

// ─── App Context (navigation, hub, toast) ────────
const AppContext = createContext(null);
const useApp = () => useContext(AppContext);

// ─── Toast Notification System ───────────────────
const ToastContainer = ({ toasts, onRemove }) => (
  <div style={{ position: "fixed", bottom: 24, right: 24, zIndex: 300, display: "flex", flexDirection: "column", gap: 8 }}>
    {toasts.map(t => (
      <div
        key={t.id}
        className="animate-in"
        style={{
          background: T.surfaceContainerHigh,
          backdropFilter: "blur(12px)",
          borderRadius: 10,
          padding: "14px 20px",
          display: "flex", alignItems: "center", gap: 12,
          minWidth: 300, maxWidth: 440,
          boxShadow: `0 8px 32px #00000040, 0 0 12px ${(t.color || T.primary)}20`,
          borderLeft: `3px solid ${t.color || T.primary}`,
          cursor: "pointer",
        }}
        onClick={() => onRemove(t.id)}
      >
        {t.icon && <t.icon size={18} color={t.color || T.primary} />}
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.onSurface }}>{t.title}</div>
          {t.body && <div style={{ fontSize: 12, color: T.onSurfaceVariant, marginTop: 2 }}>{t.body}</div>}
        </div>
        <X size={14} color={T.onSurfaceVariant} />
      </div>
    ))}
  </div>
);

// ─── Notification Panel ──────────────────────────
const notificationData = [
  { id: 1, title: "재고 긴급 경고", body: "NEON-X1-PRO 재고 582개, 4시간 내 소진 예상", time: "방금", icon: AlertTriangle, color: T.error, read: false },
  { id: 2, title: "캠페인 성과 달성", body: "Summer Glow Skin ROI 6.2x 돌파", time: "12분 전", icon: TrendingUp, color: T.tertiary, read: false },
  { id: 3, title: "AI 매칭 완료", body: "아우라_미니멀리스트 × 루나 에코 헤드폰 98% 매칭", time: "28분 전", icon: Sparkles, color: T.secondary, read: false },
  { id: 4, title: "정산 완료", body: "Kim Jisu (@jisu_vibe) $4,200 정산 처리 완료", time: "1시간 전", icon: CheckCircle2, color: T.tertiary, read: true },
  { id: 5, title: "모델 재학습 완료", body: "XGBoost 수요 예측 모델 v3.2 학습 완료 (정확도 94.2%)", time: "2시간 전", icon: Bot, color: T.primary, read: true },
];

const NotificationPanel = ({ isOpen, onClose }) => {
  const app = useApp();
  const [notifications, setNotifications] = useState(notificationData);
  const unread = notifications.filter(n => !n.read).length;

  const markAllRead = () => setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  const markRead = (id) => setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));

  if (!isOpen) return null;
  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 190 }} />
      <div style={{
        position: "absolute", top: 52, right: 80, width: 380,
        background: T.surfaceContainerLow,
        borderRadius: 12, zIndex: 195,
        boxShadow: `0 12px 40px #00000050`,
        overflow: "hidden",
        animation: "slideUp 0.2s ease-out",
      }}>
        <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Bell size={18} color={T.primary} />
            <span style={{ fontFamily: font.display, fontSize: 15, fontWeight: 600 }}>알림</span>
            {unread > 0 && <span style={{ fontSize: 11, fontWeight: 700, color: T.error, background: `${T.error}20`, padding: "1px 7px", borderRadius: 10 }}>{unread} new</span>}
          </div>
          <button onClick={markAllRead} style={{ background: "none", border: "none", color: T.primary, fontSize: 11, fontWeight: 600, cursor: "pointer" }}>모두 읽음</button>
        </div>
        <div style={{ maxHeight: 400, overflowY: "auto" }}>
          {notifications.map(n => (
            <div
              key={n.id}
              onClick={() => { markRead(n.id); onClose(); if (n.color === T.error) app.navigate("inventory"); else if (n.color === T.secondary) app.navigate("influencers"); else app.navigate("dashboard"); }}
              style={{
                padding: "14px 20px",
                display: "flex", gap: 12, alignItems: "flex-start",
                background: n.read ? "transparent" : `${T.primary}05`,
                cursor: "pointer", transition: "background 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = T.surfaceContainerHigh}
              onMouseLeave={e => e.currentTarget.style.background = n.read ? "transparent" : `${T.primary}05`}
            >
              <div style={{
                width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                background: `${n.color}12`, display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <n.icon size={16} color={n.color} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: n.read ? 400 : 600, color: T.onSurface }}>{n.title}</div>
                <div style={{ fontSize: 12, color: T.onSurfaceVariant, marginTop: 2 }}>{n.body}</div>
                <div style={{ fontSize: 10, color: T.onSurfaceVariant, marginTop: 4 }}>{n.time}</div>
              </div>
              {!n.read && <div style={{ width: 8, height: 8, borderRadius: "50%", background: T.primary, flexShrink: 0, marginTop: 6 }} />}
            </div>
          ))}
        </div>
        <div style={{ padding: "12px 20px", textAlign: "center", borderTop: `1px solid ${T.surfaceVariant}15` }}>
          <button onClick={() => { onClose(); app.navigate("support"); }} style={{ background: "none", border: "none", color: T.primary, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
            모든 알림 보기 →
          </button>
        </div>
      </div>
    </>
  );
};

// ─── Functional SearchBar ────────────────────────
const searchIndex = [
  { label: "종합 대시보드", page: "dashboard", keywords: "dashboard 대시보드 현황 KPI 매출 주문" },
  { label: "캠페인 관리", page: "campaigns", keywords: "campaign 캠페인 생성 예산 ROI 진행" },
  { label: "인플루언서 관리", page: "influencers", keywords: "influencer 인플루언서 CRM 티어 매칭 팬" },
  { label: "재고 관리", page: "inventory", keywords: "inventory 재고 품절 발주 공급사 협상 SKU" },
  { label: "수익성 리포트", page: "reports", keywords: "report 리포트 수익 정산 매출 광고비 PDF" },
  { label: "User Guide", page: "guide", keywords: "guide 가이드 도움말 사용법 FAQ 튜토리얼" },
  { label: "설정", page: "settings", keywords: "settings 설정 API ROI 임계값 알림 자동화" },
  { label: "고객 지원", page: "support", keywords: "support 지원 상태 릴리즈 버전 문의" },
  { label: "AI Insight Hub", page: "__hub__", keywords: "AI insight hub 인사이트 예측 분석 추천" },
  { label: "실시간 주문 모니터링", page: "dashboard", keywords: "실시간 주문 속도 라이브 모니터링 차트" },
  { label: "광고 최적화 제안", page: "dashboard", keywords: "광고 최적화 CPC 예산 증액" },
  { label: "얼리 센싱 피드", page: "dashboard", keywords: "얼리 센싱 트렌드 소셜 잠재력" },
  { label: "AI 상품 매칭", page: "influencers", keywords: "AI 매칭 상품 추천 카테고리 점수" },
  { label: "공급사 자동 협상", page: "inventory", keywords: "공급사 협상 자동 발주 제안서" },
  { label: "인플루언서 정산", page: "reports", keywords: "정산 인플루언서 금액 상태 완료" },
  { label: "수요 예측 모델", page: "guide", keywords: "수요 예측 XGBoost 머신러닝 모델" },
  { label: "이상징후 감지", page: "guide", keywords: "이상징후 anomaly 감지 주문 급증 급감" },
];

const FunctionalSearchBar = ({ placeholder = "검색 또는 AI 질의..." }) => {
  const app = useApp();
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const ref = useRef(null);

  const results = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return searchIndex.filter(s => s.label.toLowerCase().includes(q) || s.keywords.includes(q)).slice(0, 6);
  }, [query]);

  const handleSelect = (item) => {
    if (item.page === "__hub__") app.openHub();
    else app.navigate(item.page);
    setQuery("");
    setFocused(false);
  };

  return (
    <div style={{ position: "relative", flex: 1, maxWidth: 480 }} ref={ref}>
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        background: focused ? T.surfaceContainerHighest : T.surfaceContainerHigh,
        borderRadius: 8, padding: "10px 16px",
        border: focused ? `1px solid ${T.primary}40` : `1px solid transparent`,
        boxShadow: focused ? `0 0 12px ${T.primary}15` : "none",
        transition: "all 0.2s",
      }}>
        <Search size={16} color={focused ? T.primary : T.onSurfaceVariant} />
        <input
          placeholder={placeholder}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 200)}
          onKeyDown={e => { if (e.key === "Escape") { setQuery(""); setFocused(false); } if (e.key === "Enter" && results.length > 0) handleSelect(results[0]); }}
          style={{
            background: "transparent", border: "none", outline: "none",
            color: T.onSurface, fontFamily: font.body, fontSize: 13, width: "100%",
          }}
        />
        {query && (
          <button onClick={() => setQuery("")} style={{ background: "none", border: "none", cursor: "pointer", color: T.onSurfaceVariant, padding: 0 }}>
            <X size={14} />
          </button>
        )}
      </div>
      {focused && results.length > 0 && (
        <div style={{
          position: "absolute", top: "calc(100% + 6px)", left: 0, right: 0,
          background: T.surfaceContainerLow, borderRadius: 10,
          boxShadow: `0 8px 32px #00000050`,
          overflow: "hidden", zIndex: 150,
        }}>
          <div style={{ padding: "8px 14px", fontSize: 10, fontWeight: 600, color: T.onSurfaceVariant, letterSpacing: "0.06em" }}>
            검색 결과 ({results.length})
          </div>
          {results.map((r, i) => {
            const PageIcon = r.page === "__hub__" ? Sparkles : navItems?.find?.(n => n.key === r.page)?.icon || FileText;
            return (
              <div
                key={i}
                onMouseDown={() => handleSelect(r)}
                style={{
                  padding: "10px 14px",
                  display: "flex", alignItems: "center", gap: 10,
                  cursor: "pointer", transition: "background 0.1s",
                }}
                onMouseEnter={e => e.currentTarget.style.background = T.surfaceContainerHigh}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <PageIcon size={16} color={T.primary} />
                <span style={{ fontSize: 13, color: T.onSurface }}>{r.label}</span>
                <span style={{ fontSize: 11, color: T.onSurfaceVariant, marginLeft: "auto" }}>{r.page === "__hub__" ? "Hub" : r.page}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ─── Reusable Components ─────────────────────────

const Glass = ({ children, style, className = "", glow, onClick }) => (
  <div
    onClick={onClick}
    className={className}
    style={{
      background: `${T.surfaceContainerHigh}99`,
      backdropFilter: "blur(16px)",
      WebkitBackdropFilter: "blur(16px)",
      borderRadius: "12px",
      border: `1px solid ${T.outlineVariant}26`,
      ...(glow ? { boxShadow: `0 0 12px ${glow}30` } : {}),
      ...style,
    }}
  >
    {children}
  </div>
);

const MetricCard = ({ label, value, unit, change, changeDir, icon: Icon, accentColor }) => (
  <div
    className="animate-in"
    style={{
      background: T.surfaceContainerLow,
      borderRadius: "12px",
      padding: "20px 24px",
      flex: 1,
      minWidth: 180,
      position: "relative",
      overflow: "hidden",
    }}
  >
    {accentColor && (
      <div style={{
        position: "absolute", top: 0, right: 0, width: 60, height: 60,
        background: `radial-gradient(circle at top right, ${accentColor}15, transparent 70%)`,
      }} />
    )}
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
      <div>
        <div style={{ fontFamily: font.body, fontSize: 12, color: T.onSurfaceVariant, letterSpacing: "0.05em", marginBottom: 8 }}>
          {label}
        </div>
        <div style={{ fontFamily: font.display, fontSize: 28, fontWeight: 700, color: T.onSurface, lineHeight: 1 }}>
          {value}
          {unit && <span style={{ fontSize: 14, color: T.onSurfaceVariant, marginLeft: 4, fontWeight: 400 }}>{unit}</span>}
        </div>
      </div>
      {Icon && <Icon size={20} color={accentColor || T.onSurfaceVariant} style={{ opacity: 0.7 }} />}
    </div>
    {change && (
      <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 4 }}>
        {changeDir === "up" ? <TrendingUp size={14} color={T.tertiary} /> : <TrendingDown size={14} color={T.error} />}
        <span style={{ fontSize: 12, fontWeight: 600, color: changeDir === "up" ? T.tertiary : T.error }}>
          {change}
        </span>
      </div>
    )}
  </div>
);

const PulseDot = ({ color = T.tertiary, size = 8 }) => (
  <span
    className="pulse-dot"
    style={{
      display: "inline-block",
      width: size,
      height: size,
      borderRadius: "50%",
      background: color,
      boxShadow: `0 0 6px ${color}80`,
    }}
  />
);

const Badge = ({ children, color = T.primary }) => (
  <span style={{
    display: "inline-flex", alignItems: "center", gap: 4,
    padding: "3px 10px", borderRadius: 4, fontSize: 11, fontWeight: 600,
    background: `${color}20`, color: color, letterSpacing: "0.02em",
  }}>
    {children}
  </span>
);

const SectionTitle = ({ children, sub, right }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
    <div>
      <h2 style={{ fontFamily: font.display, fontSize: 20, fontWeight: 600, color: T.onSurface }}>{children}</h2>
      {sub && <p style={{ fontSize: 13, color: T.onSurfaceVariant, marginTop: 4 }}>{sub}</p>}
    </div>
    {right}
  </div>
);

const BtnPrimary = ({ children, onClick, icon: Icon }) => (
  <button
    onClick={onClick}
    style={{
      display: "inline-flex", alignItems: "center", gap: 8,
      padding: "10px 20px", borderRadius: 6, border: "none", cursor: "pointer",
      background: `linear-gradient(135deg, ${T.primary}20, ${T.primary}40)`,
      color: T.primary, fontFamily: font.body, fontSize: 13, fontWeight: 600,
      transition: "all 0.2s",
      boxShadow: `0 0 12px ${T.primary}20`,
    }}
    onMouseEnter={e => e.target.style.boxShadow = `0 0 20px ${T.primary}40`}
    onMouseLeave={e => e.target.style.boxShadow = `0 0 12px ${T.primary}20`}
  >
    {Icon && <Icon size={16} />}
    {children}
  </button>
);

const BtnSecondary = ({ children, onClick, icon: Icon }) => (
  <button
    onClick={onClick}
    style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: "8px 16px", borderRadius: 6,
      border: `1px solid ${T.outlineVariant}33`,
      background: "transparent", color: T.onSurfaceVariant,
      fontFamily: font.body, fontSize: 12, fontWeight: 500, cursor: "pointer",
      transition: "all 0.2s",
    }}
  >
    {Icon && <Icon size={14} />}
    {children}
  </button>
);

const SearchBar = ({ placeholder = "검색 또는 AI 질의..." }) => (
  <div style={{
    display: "flex", alignItems: "center", gap: 10,
    background: T.surfaceContainerHigh, borderRadius: 8, padding: "10px 16px",
    flex: 1, maxWidth: 480,
  }}>
    <Search size={16} color={T.onSurfaceVariant} />
    <input
      placeholder={placeholder}
      style={{
        background: "transparent", border: "none", outline: "none",
        color: T.onSurface, fontFamily: font.body, fontSize: 13, width: "100%",
      }}
    />
  </div>
);

const ChartTooltipContent = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <Glass style={{ padding: "10px 14px" }}>
      <div style={{ fontSize: 11, color: T.onSurfaceVariant, marginBottom: 6 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize: 13, fontWeight: 600, color: p.color || T.primary }}>
          {p.name}: {typeof p.value === "number" ? p.value.toLocaleString() : p.value}
        </div>
      ))}
    </Glass>
  );
};

// ─── Mock Data ───────────────────────────────────

const hourlyOrders = Array.from({ length: 13 }, (_, i) => {
  const h = i + 6;
  const base = Math.floor(Math.random() * 80) + 30;
  const spike = h >= 16 && h <= 19 ? Math.floor(Math.random() * 120) + 80 : 0;
  return { time: `${String(h).padStart(2, "0")}:00`, orders: base + spike, predicted: base + spike + Math.floor(Math.random() * 30 - 10) };
});

const weeklyRevenue = [
  { week: "1주차", revenue: 8200, adCost: 2800 },
  { week: "2주차", revenue: 9400, adCost: 3100 },
  { week: "3주차", revenue: 14200, adCost: 3800 },
  { week: "4주차", revenue: 11800, adCost: 3200 },
  { week: "5주차", revenue: 12600, adCost: 2900 },
];

const conversionData = [
  { month: "01 MAY", rate: 3.2 },
  { month: "08 MAY", rate: 3.8 },
  { month: "15 MAY", rate: 4.1 },
  { month: "22 MAY", rate: 5.2 },
  { month: "30 MAY", rate: 5.8 },
];

const influencers = [
  { name: "아우라_미니멀리스트", handle: "@aura_minimal", tier: "S", tierColor: T.primary, categories: ["패션", "테크"], sales: "₩ 1.4억", roi: "12.4x", roiDir: "up", verified: true, avatar: "🌸" },
  { name: "테크뱅가드", handle: "@tech_vanguard_kr", tier: "A", tierColor: T.secondary, categories: ["가젯"], sales: "₩ 7,200만", roi: "8.1x", roiDir: "up", avatar: "⚡" },
  { name: "럭스라이프_채경", handle: "@luxe_style_ck", tier: "B", tierColor: T.tertiary, categories: ["뷰티", "명품"], sales: "₩ 3,150만", roi: "4.2x", roiDir: "right", avatar: "💎" },
  { name: "Kim Sora", handle: "@soratrend_official", tier: "A", tierColor: T.secondary, categories: ["라이프", "뷰티"], sales: "₩ 5,800만", roi: "9.2x", roiDir: "up", avatar: "🌟" },
  { name: "Park Jinwoo", handle: "@jinwoo_life", tier: "B", tierColor: T.tertiary, categories: ["푸드", "여행"], sales: "₩ 2,400만", roi: "5.1x", roiDir: "up", avatar: "🎯" },
];

const settlements = [
  { name: "Kim Jisu", handle: "@jisu_vibe", category: "Fashion & Life", campaign: "Summer Glow Skin", amount: "$4,200", status: "정산 완료", statusColor: T.tertiary },
  { name: "Lee Minho", handle: "@tech_min", category: "Tech Review", campaign: "Pro Mouse Launch", amount: "$2,850", status: "진행중", statusColor: T.primary },
  { name: "Park Sora", handle: "@travel_sora", category: "Travel & Nature", campaign: "Eco Backpack Series", amount: "$3,100", status: "대기중", statusColor: T.onSurfaceVariant },
  { name: "Jung Hoon", handle: "@hoon_fit", category: "Fitness", campaign: "Protein Shake Mix", amount: "$5,500", status: "정산 완료", statusColor: T.tertiary },
];

const stockAlerts = [
  { sku: "SKU-A892", name: "Premium Cream", remaining: 14, eta: "3시간 내" },
  { sku: "SKU-B120", name: "Silk Serum", remaining: 42, eta: "8시간 내" },
];

const sensingFeed = [
  { name: "Kim Sora", handle: "@soratrend_official", badge: "High Potential", badgeColor: T.tertiary, score: 88.4, predicted: "2,400+", avatar: "🌟" },
  { name: "Park Jinwoo", handle: "@jinwoo_life", badge: "Stable Growth", badgeColor: T.primary, score: 76.2, predicted: "1,150+", avatar: "🎯" },
  { name: "Lee Minah", handle: "@minah_daily", badge: "Early Sensing", badgeColor: T.secondary, score: 92.1, predicted: "5,800+", avatar: "✨" },
];


// ═══════════════════════════════════════════════════
//   PAGE: Dashboard (종합 대시보드)
// ═══════════════════════════════════════════════════

const DashboardPage = () => {
  const [liveCount, setLiveCount] = useState(142);
  useEffect(() => {
    const iv = setInterval(() => setLiveCount(c => c + Math.floor(Math.random() * 5 - 2)), 3000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 11, letterSpacing: "0.15em", color: T.onSurfaceVariant, textTransform: "uppercase", marginBottom: 4 }}>
            Real-Time Protocol Active
          </div>
          <h1 style={{ fontFamily: font.display, fontSize: 32, fontWeight: 700 }}>종합 대시보드</h1>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <BtnSecondary icon={Clock}>시간 범위: 최근 24시간</BtnSecondary>
          <BtnPrimary icon={Download}>보고서 추출</BtnPrimary>
        </div>
      </div>

      {/* KPI Row */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <MetricCard label="총 매출" value="1억 4,280" unit="만원" change="+12%" changeDir="up" icon={TrendingUp} accentColor={T.primary} />
        <MetricCard label="평균 ROI" value="4.2x" change="" icon={Target} accentColor={T.secondary} />
        <MetricCard label="수요 예측 정확도" value="94%" icon={Sparkles} accentColor={T.tertiary} />
        <MetricCard label="진행 중인 캠페인" value="8건" icon={Megaphone} accentColor={T.primary} />
      </div>

      {/* Main Content: Chart + Alerts */}
      <div style={{ display: "flex", gap: 20 }}>
        {/* Real-time Orders Chart */}
        <div style={{ flex: 2, background: T.surfaceContainerLow, borderRadius: 12, padding: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <div>
              <h3 style={{ fontFamily: font.display, fontSize: 18, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                <Activity size={18} color={T.primary} /> 실시간 주문 속도
              </h3>
              <p style={{ fontSize: 12, color: T.onSurfaceVariant, marginTop: 4 }}>시간당 주문 발생 빈도 추이</p>
            </div>
            <Badge color={T.tertiary}><PulseDot /> Live Streaming</Badge>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={hourlyOrders}>
              <defs>
                <linearGradient id="orderGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={T.primary} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={T.primary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={T.surfaceVariant + "30"} />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: T.onSurfaceVariant }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: T.onSurfaceVariant }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltipContent />} />
              <Area type="monotone" dataKey="orders" stroke={T.primary} fill="url(#orderGrad)" strokeWidth={2} name="실제 주문" />
              <Line type="monotone" dataKey="predicted" stroke={T.secondary} strokeWidth={1.5} strokeDasharray="5 5" dot={false} name="AI 예측" />
            </AreaChart>
          </ResponsiveContainer>
          {/* AI Prediction Overlay */}
          <Glass glow={T.secondary} style={{ padding: "14px 18px", marginTop: 12, display: "flex", alignItems: "flex-start", gap: 10 }}>
            <Sparkles size={18} color={T.secondary} style={{ marginTop: 2, flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 11, color: T.secondary, fontWeight: 600, letterSpacing: "0.05em", marginBottom: 4 }}>AI PREDICTION</div>
              <div style={{ fontSize: 13, color: T.onSurface, lineHeight: 1.5 }}>
                향후 <strong style={{ color: T.primary }}>45분 이내</strong>에 주문량이 평소 대비 <strong style={{ color: T.tertiary }}>24% 증가</strong>할 것으로 예상됩니다. 시스템 리소스가 자동 할당되었습니다.
              </div>
            </div>
          </Glass>
        </div>

        {/* Right Column: Alerts */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Stock Alerts */}
          <div style={{ background: T.surfaceContainerLow, borderRadius: 12, padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
              <AlertTriangle size={18} color={T.error} />
              <h3 style={{ fontFamily: font.display, fontSize: 16, fontWeight: 600 }}>재고 부족 경고</h3>
            </div>
            {stockAlerts.map((a, i) => (
              <div
                key={i}
                style={{
                  background: T.surfaceContainerHigh,
                  borderRadius: 8,
                  padding: "14px 16px",
                  marginBottom: i < stockAlerts.length - 1 ? 10 : 0,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.onSurface }}>{a.sku} ({a.name})</div>
                  <div style={{ fontSize: 11, color: T.onSurfaceVariant, marginTop: 2 }}>
                    남은 수량: <span style={{ color: T.error }}>{a.remaining}개</span> (예상 고갈: {a.eta})
                  </div>
                </div>
                <button style={{
                  background: `${T.error}20`, color: T.error, border: "none",
                  padding: "6px 12px", borderRadius: 4, fontSize: 11, fontWeight: 600, cursor: "pointer",
                }}>발주</button>
              </div>
            ))}
          </div>

          {/* Ad Optimization */}
          <div style={{ background: T.surfaceContainerLow, borderRadius: 12, padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <Target size={18} color={T.secondary} />
              <h3 style={{ fontFamily: font.display, fontSize: 16, fontWeight: 600, color: T.secondary }}>광고 최적화 제안</h3>
            </div>
            <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.6, marginBottom: 14 }}>
              고효율 인플루언서 3명의 CPC가 현재 15% 하락했습니다. 예산을 20% 증액 시 매출 8% 추가 상승이 예상됩니다.
            </p>
            <button style={{
              width: "100%", padding: "10px", borderRadius: 6, border: "none", cursor: "pointer",
              background: `linear-gradient(135deg, ${T.secondary}30, ${T.secondary}15)`,
              color: T.secondary, fontSize: 13, fontWeight: 600,
            }}>최적화 즉시 적용</button>
          </div>
        </div>
      </div>

      {/* Early Sensing Feed */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div>
            <h3 style={{ fontFamily: font.display, fontSize: 18, fontWeight: 600 }}>얼리 센싱 피드</h3>
            <p style={{ fontSize: 12, color: T.onSurfaceVariant, marginTop: 4 }}>AI 기반 소셜 트렌드 및 인플루언서 성과 분석</p>
          </div>
          <BtnSecondary>전체보기 <ArrowRight size={14} /></BtnSecondary>
        </div>
        <div style={{ display: "flex", gap: 16 }}>
          {sensingFeed.map((s, i) => (
            <div
              key={i}
              className="animate-in"
              style={{
                flex: 1, background: T.surfaceContainerLow, borderRadius: 12, padding: 20,
                animationDelay: `${i * 0.1}s`,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                  background: T.surfaceContainerHigh, fontSize: 24,
                }}>{s.avatar}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{s.name}</div>
                  <div style={{ fontSize: 12, color: T.onSurfaceVariant }}>{s.handle}</div>
                </div>
                <Badge color={s.badgeColor}>{s.badge}</Badge>
              </div>
              <div style={{ display: "flex", gap: 24 }}>
                <div>
                  <div style={{ fontSize: 11, color: T.onSurfaceVariant }}>반응 지수</div>
                  <div style={{ fontFamily: font.display, fontSize: 24, fontWeight: 700, marginTop: 4 }}>{s.score}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: T.onSurfaceVariant }}>예측 판매량</div>
                  <div style={{ fontFamily: font.display, fontSize: 24, fontWeight: 700, marginTop: 4, color: T.tertiary }}>{s.predicted}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════
//   PAGE: Influencers (인플루언서 관리)
// ═══════════════════════════════════════════════════

const InfluencersPage = () => {
  const [activeFilter, setActiveFilter] = useState("ROI순");
  const filters = ["ROI순", "카테고리별", "티어별"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ fontFamily: font.display, fontSize: 32, fontWeight: 700 }}>인플루언서 관리</h1>
          <p style={{ fontSize: 14, color: T.onSurfaceVariant, marginTop: 4 }}>통합 CRM 및 성과 분석 시스템</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <BtnSecondary icon={Download}>내보내기</BtnSecondary>
          <BtnPrimary icon={Plus}>신규 추가</BtnPrimary>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: T.primary, marginRight: 8 }}>FILTERS</span>
          {filters.map(f => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              style={{
                padding: "7px 16px", borderRadius: 6, border: "none", cursor: "pointer", fontSize: 13,
                background: activeFilter === f ? T.surfaceContainerHighest : "transparent",
                color: activeFilter === f ? T.onSurface : T.onSurfaceVariant,
                fontWeight: activeFilter === f ? 600 : 400,
              }}
            >
              {f}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 13, color: T.onSurfaceVariant }}>
          <PulseDot color={T.tertiary} /> Live Syncing
          <span style={{ marginLeft: 8 }}>Total: <strong style={{ color: T.onSurface }}>1,284명</strong></span>
        </div>
      </div>

      <div style={{ display: "flex", gap: 20 }}>
        {/* Influencer Table */}
        <div style={{ flex: 2 }}>
          <div style={{ background: T.surfaceContainerLow, borderRadius: 12, overflow: "hidden" }}>
            {/* Table Header */}
            <div style={{
              display: "grid", gridTemplateColumns: "2fr 0.7fr 1fr 1fr 1fr",
              padding: "14px 20px", background: T.surfaceContainer,
              fontSize: 12, color: T.onSurfaceVariant, fontWeight: 600, letterSpacing: "0.03em",
            }}>
              <span>인플루언서</span><span>티어</span><span>카테고리</span><span>총 매출</span><span>ROI</span>
            </div>
            {/* Table Rows */}
            {influencers.slice(0, 4).map((inf, i) => (
              <div
                key={i}
                className="animate-in"
                style={{
                  display: "grid", gridTemplateColumns: "2fr 0.7fr 1fr 1fr 1fr",
                  padding: "16px 20px", alignItems: "center",
                  background: i % 2 === 0 ? T.surfaceContainerLow : `${T.surfaceContainer}80`,
                  cursor: "pointer", transition: "background 0.15s",
                  animationDelay: `${i * 0.08}s`,
                }}
                onMouseEnter={e => e.currentTarget.style.background = T.surfaceContainerHigh}
                onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? T.surfaceContainerLow : `${T.surfaceContainer}80`}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                    background: T.surfaceContainerHighest, fontSize: 18,
                  }}>{inf.avatar}</div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
                      {inf.name}
                      {inf.verified && <Shield size={14} color={T.tertiary} />}
                    </div>
                    <div style={{ fontSize: 12, color: T.onSurfaceVariant }}>{inf.handle}</div>
                  </div>
                </div>
                <Badge color={inf.tierColor}>{inf.tier} TIER</Badge>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {inf.categories.map((c, j) => (
                    <span key={j} style={{ fontSize: 11, color: T.primaryFixedDim, background: `${T.primary}10`, padding: "2px 8px", borderRadius: 3 }}>{c}</span>
                  ))}
                </div>
                <div style={{ fontFamily: font.display, fontSize: 15, fontWeight: 600 }}>{inf.sales}</div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontFamily: font.display, fontSize: 15, fontWeight: 600, color: T.tertiary }}>{inf.roi}</span>
                  <TrendingUp size={14} color={T.tertiary} />
                </div>
              </div>
            ))}
          </div>

          {/* Bottom Charts */}
          <div style={{ display: "flex", gap: 16, marginTop: 20 }}>
            <div style={{ flex: 1, background: T.surfaceContainerLow, borderRadius: 12, padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <h3 style={{ fontFamily: font.display, fontSize: 16, fontWeight: 600 }}>최근 캠페인 전환율</h3>
                <ExternalLink size={16} color={T.onSurfaceVariant} />
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={conversionData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={T.surfaceVariant + "20"} />
                  <XAxis dataKey="month" tick={{ fontSize: 10, fill: T.onSurfaceVariant }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: T.onSurfaceVariant }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="rate" name="전환율 %" radius={[4, 4, 0, 0]}>
                    {conversionData.map((_, i) => (
                      <Cell key={i} fill={i === conversionData.length - 1 ? T.primary : T.surfaceVariant} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div style={{ fontSize: 12, color: T.tertiary, fontWeight: 600, marginTop: 8, textAlign: "center" }}>
                WEEKLY GROWTH +14.2%
              </div>
            </div>
            <div style={{ flex: 1, background: T.surfaceContainerLow, borderRadius: 12, padding: 20 }}>
              <h3 style={{ fontFamily: font.display, fontSize: 16, fontWeight: 600, marginBottom: 20 }}>팬 베이스 분포</h3>
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 13, color: T.onSurface }}>MZ세대 (18-34)</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: T.error }}>72%</span>
                </div>
                <div style={{ height: 6, background: T.surfaceContainerHighest, borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ width: "72%", height: "100%", background: T.primary, borderRadius: 3 }} />
                </div>
              </div>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 13, color: T.onSurface }}>관심사: 테크/미니멀</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: T.primary }}>88%</span>
                </div>
                <div style={{ height: 6, background: T.surfaceContainerHighest, borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ width: "88%", height: "100%", background: T.primary, borderRadius: 3 }} />
                </div>
              </div>
              <div style={{ marginTop: 20, textAlign: "center" }}>
                <BtnSecondary>자세한 오디언스 리포트 보기 <ArrowRight size={14} /></BtnSecondary>
              </div>
            </div>
          </div>
        </div>

        {/* AI Matching Panel */}
        <div style={{ flex: 1 }}>
          <Glass glow={T.secondary} style={{ padding: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
              <Sparkles size={22} color={T.secondary} />
              <h3 style={{ fontFamily: font.display, fontSize: 18, fontWeight: 600 }}>AI 상품 매칭 제안</h3>
            </div>

            <div style={{ textAlign: "center", marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: T.onSurfaceVariant }}>대상 인플루언서</div>
              <div style={{
                width: 64, height: 64, borderRadius: "50%", margin: "10px auto",
                background: T.surfaceContainerHighest, display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 28, border: `2px solid ${T.primary}40`,
              }}>🌸</div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>아우라_미니멀리스트</div>
              <Badge color={T.tertiary}>Active</Badge>
            </div>

            {/* Match Score */}
            <div style={{
              display: "flex", justifyContent: "center", alignItems: "center", margin: "20px 0",
              height: 2, background: T.surfaceVariant, position: "relative",
            }}>
              <div style={{
                position: "absolute",
                background: `linear-gradient(135deg, ${T.primary}, ${T.tertiary})`,
                color: T.surface, fontSize: 13, fontWeight: 700,
                padding: "8px 16px", borderRadius: 20,
                boxShadow: `0 0 16px ${T.tertiary}50`,
              }}>
                98% MATCH
              </div>
            </div>

            <div style={{
              display: "flex", alignItems: "center", gap: 14, padding: 16, marginTop: 24,
              background: T.surfaceContainerLow, borderRadius: 10,
            }}>
              <div style={{
                width: 48, height: 48, borderRadius: 8,
                background: T.surfaceContainerHighest, display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 22,
              }}>🎧</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: T.onSurfaceVariant }}>추천 상품</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>루나 에코 헤드폰</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 11, color: T.onSurfaceVariant }}>재고 보유</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>821 Units</div>
              </div>
            </div>

            {/* AI Reasoning */}
            <div style={{
              marginTop: 16, padding: 16, borderRadius: 10,
              borderLeft: `3px solid ${T.secondary}`,
              background: `${T.secondary}08`,
            }}>
              <div style={{ fontSize: 11, color: T.secondary, fontWeight: 600, marginBottom: 6 }}>AI REASONING</div>
              <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.6 }}>
                미니멀리스트 타겟층의 '친환경' 키워드와 인플루언서의 최근 테크 리뷰 전환율을 분석한 결과, 루나 에코 시리즈의 디자인 언어가 오디언스 선호도와 일치합니다.
              </p>
            </div>

            <button style={{
              width: "100%", marginTop: 20, padding: "12px", borderRadius: 8, border: "none", cursor: "pointer",
              background: `linear-gradient(135deg, ${T.primary}20, ${T.secondary}20)`,
              color: T.primary, fontFamily: font.body, fontSize: 14, fontWeight: 600,
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            }}>
              <Send size={16} /> 캠페인 제안 발송하기
            </button>
          </Glass>
        </div>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════
//   PAGE: Inventory (재고 관리)
// ═══════════════════════════════════════════════════

const InventoryPage = () => {
  const salesData = Array.from({ length: 8 }, (_, i) => {
    const h = (i + 1) * 3 + 5;
    return { time: `${String(h).padStart(2, "0")}:00`, sales: Math.floor(Math.random() * 140) + 40 };
  });
  const peakIdx = salesData.reduce((max, d, i, arr) => d.sales > arr[max].sales ? i : max, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Urgent Alert Banner */}
      <div
        className="glow-border"
        style={{
          background: `linear-gradient(135deg, ${T.error}20, ${T.surfaceContainerLow})`,
          borderRadius: 12, padding: "20px 28px",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          position: "relative", overflow: "hidden",
        }}
      >
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, background: `linear-gradient(90deg, ${T.error}10, transparent)` }} />
        <div style={{ display: "flex", alignItems: "center", gap: 16, position: "relative" }}>
          <div style={{
            width: 48, height: 48, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
            background: `${T.error}20`,
          }}>
            <AlertTriangle size={24} color={T.error} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
              <Badge color={T.error}>URGENT</Badge>
              <h2 style={{ fontFamily: font.display, fontSize: 22, fontWeight: 700 }}>긴급 재고 소진 경고</h2>
            </div>
            <div style={{ fontSize: 13, color: T.onSurfaceVariant }}>
              SKU: <strong style={{ color: T.onSurface }}>NEON-X1-PRO</strong>
            </div>
            <div style={{ fontSize: 12, color: T.error, marginTop: 4, display: "flex", alignItems: "center", gap: 4 }}>
              <PulseDot color={T.error} /> 4시간 내 품절 예상
            </div>
          </div>
        </div>
        <div style={{ textAlign: "right", position: "relative" }}>
          <div style={{ fontSize: 12, color: T.onSurfaceVariant }}>현재 재고 수준</div>
          <div style={{ fontFamily: font.display, fontSize: 48, fontWeight: 700, color: T.onSurface }}>582 <span style={{ fontSize: 16, color: T.onSurfaceVariant }}>pcs</span></div>
          <div style={{ height: 4, background: T.surfaceVariant, borderRadius: 2, marginTop: 8, width: 160 }}>
            <div style={{ width: "15%", height: "100%", background: T.error, borderRadius: 2 }} />
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 20 }}>
        {/* Sales Analysis Chart */}
        <div style={{ flex: 2, background: T.surfaceContainerLow, borderRadius: 12, padding: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
            <div>
              <h3 style={{ fontFamily: font.display, fontSize: 18, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                <Activity size={18} color={T.primary} /> 실시간 판매량 분석
              </h3>
              <p style={{ fontSize: 12, color: T.onSurfaceVariant, marginTop: 4 }}>지난 24시간 동향 및 AI 예측 모델</p>
            </div>
            <Badge color={T.primary}>LIVE STREAM</Badge>
          </div>
          <div style={{ display: "flex", gap: 24, marginBottom: 20 }}>
            <div style={{ background: T.surfaceContainer, borderRadius: 8, padding: "14px 20px" }}>
              <div style={{ fontSize: 11, color: T.onSurfaceVariant }}>평균 판매 속도</div>
              <div style={{ fontFamily: font.display, fontSize: 32, fontWeight: 700, marginTop: 4 }}>142 <span style={{ fontSize: 14, color: T.onSurfaceVariant, fontWeight: 400 }}>units/hr</span></div>
            </div>
            <div style={{ background: T.surfaceContainer, borderRadius: 8, padding: "14px 20px" }}>
              <div style={{ fontSize: 11, color: T.onSurfaceVariant }}>AI 변동 예측</div>
              <div style={{ fontFamily: font.display, fontSize: 32, fontWeight: 700, color: T.tertiary, marginTop: 4 }}>+24.8% <TrendingUp size={20} style={{ verticalAlign: "middle" }} /></div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={salesData}>
              <CartesianGrid strokeDasharray="3 3" stroke={T.surfaceVariant + "20"} />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: T.onSurfaceVariant }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: T.onSurfaceVariant }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltipContent />} />
              <Bar dataKey="sales" name="판매량" radius={[4, 4, 0, 0]}>
                {salesData.map((_, i) => (
                  <Cell key={i} fill={i === peakIdx ? T.primary : T.surfaceVariant} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Profitability Simulation */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ background: T.surfaceContainerLow, borderRadius: 12, padding: 20 }}>
            <h3 style={{ fontFamily: font.display, fontSize: 16, fontWeight: 600, marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
              <Target size={18} color={T.secondary} /> 수익성 시뮬레이션
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <TrendingUp size={16} color={T.onSurfaceVariant} />
                  <span style={{ fontSize: 13 }}>단위 마진 변화<br /><span style={{ fontSize: 11, color: T.onSurfaceVariant }}>Unit Margin</span></span>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontFamily: font.display, fontSize: 20, fontWeight: 700, color: T.tertiary }}>+12%</div>
                  <div style={{ fontSize: 10, color: T.tertiary }}>Optimized Target</div>
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Clock size={16} color={T.onSurfaceVariant} />
                  <span style={{ fontSize: 13 }}>리드 타임 단축<br /><span style={{ fontSize: 11, color: T.onSurfaceVariant }}>Lead Time</span></span>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontFamily: font.display, fontSize: 20, fontWeight: 700, color: T.primary }}>-18h</div>
                  <div style={{ fontSize: 10, color: T.primary }}>Express Logistics</div>
                </div>
              </div>
            </div>
          </div>

          {/* AI Recommendation */}
          <Glass glow={T.secondary} style={{ padding: 18 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <Sparkles size={16} color={T.secondary} />
              <span style={{ fontSize: 12, fontWeight: 600, color: T.secondary, letterSpacing: "0.05em" }}>AI RECOMMENDATION</span>
            </div>
            <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.6 }}>
              "현재의 구매 전환율과 경쟁사 가격 동향을 분석했을 때, 대량 매입을 통한 12% 마진 확보가 시장 점유율 4.2% 추가 상승으로 이어질 것입니다."
            </p>
          </Glass>
        </div>
      </div>

      {/* Supplier Negotiation */}
      <div style={{ background: T.surfaceContainerLow, borderRadius: 12, padding: 28 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Bot size={22} color={T.primary} />
            <h3 style={{ fontFamily: font.display, fontSize: 20, fontWeight: 600 }}>공급사 자동 협상 제안서</h3>
          </div>
          <span style={{ fontSize: 11, color: T.onSurfaceVariant, fontFamily: "monospace" }}>DRAFT_ID: ICOM-NEG-2024-X1</span>
        </div>
        <div style={{ display: "flex", gap: 24 }}>
          <div style={{ flex: 2 }}>
            <div style={{ fontSize: 13, color: T.onSurfaceVariant, marginBottom: 12 }}>
              [수신: Global Tech Logistics 마케팅/영업팀]
            </div>
            <p style={{ fontSize: 14, color: T.onSurface, lineHeight: 1.7, marginBottom: 16 }}>
              안녕하세요, ICOM Agent 프로토콜에 의해 생성된 자동 협상 제안입니다.
            </p>
            <p style={{ fontSize: 14, color: T.onSurface, lineHeight: 1.7, marginBottom: 16 }}>
              당사의 <strong style={{ color: T.primary }}>NEON-X1-PRO</strong> 제품 재고가 예상보다 빠른 속도로 소진되고 있으며, 향후 4시간 내에 품절이 확실시됩니다. 이에 따라 당사는 다음과 같은 조건으로 긴급 추가 발주를 제안합니다:
            </p>
            <div style={{ padding: "16px 20px", background: T.surfaceContainer, borderRadius: 8, marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: T.onSurface, lineHeight: 2 }}>
                • 긴급 재고 확보 수량: <strong>2,000 units</strong><br />
                • 협상 제안 사항: <strong>커미션 50% 조정 (현행 대비)</strong><br />
                • 조건: 즉시 출고 및 18시간 이내 물류 센터 입고
              </div>
            </div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ background: T.surfaceContainerHigh, borderRadius: 10, padding: 20 }}>
              <div style={{ fontSize: 11, color: T.onSurfaceVariant, letterSpacing: "0.05em", marginBottom: 12 }}>TARGET SUPPLIER</div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: 8,
                  background: T.surfaceContainerHighest, display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 18,
                }}>🏭</div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>Global Tech Logistics</div>
                  <div style={{ fontSize: 11, color: T.tertiary }}>● 신뢰도 A+</div>
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: T.onSurfaceVariant }}>최근 협상 성공률</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: T.tertiary }}>92%</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 12, color: T.onSurfaceVariant }}>평균 응답 속도</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: T.primary }}>14분</span>
              </div>
            </div>
          </div>
        </div>
        <div style={{ textAlign: "center", marginTop: 24 }}>
          <button style={{
            padding: "14px 40px", borderRadius: 8, border: "none", cursor: "pointer",
            background: `linear-gradient(135deg, ${T.primary}30, ${T.tertiary}20)`,
            color: T.primary, fontSize: 15, fontWeight: 600,
            display: "inline-flex", alignItems: "center", gap: 10,
            boxShadow: `0 0 20px ${T.primary}20`,
          }}>
            <Send size={18} /> 자동 알림 전송 및 협상 시작
          </button>
        </div>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════
//   PAGE: Reports (수익성 리포트)
// ═══════════════════════════════════════════════════

const ReportsPage = () => (
  <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
      <div>
        <div style={{ fontSize: 11, letterSpacing: "0.12em", color: T.onSurfaceVariant, textTransform: "uppercase", marginBottom: 4 }}>
          REPORTS › PROFITABILITY
        </div>
        <h1 style={{ fontFamily: font.display, fontSize: 32, fontWeight: 700 }}>수익성 리포트</h1>
        <p style={{ fontSize: 14, color: T.onSurfaceVariant, marginTop: 6 }}>
          실시간 캠페인 정산 현황 및 수익성 분석 데이터입니다. AI 알고리즘이 분석한 주차별 성과 트렌드를 확인하세요.
        </p>
      </div>
      <BtnPrimary icon={FileText}>PDF 리포트 생성</BtnPrimary>
    </div>

    {/* KPI Row */}
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
      <MetricCard label="총 매출액" value="$142,850" change="+12.4%" changeDir="up" icon={TrendingUp} accentColor={T.primary} />
      <MetricCard label="총 광고 집행비" value="$38,200" change="-4.2%" changeDir="down" icon={Megaphone} accentColor={T.error} />
      <MetricCard label="최종 순수익" value="$104,650" change="+15.8%" changeDir="up" icon={TrendingUp} accentColor={T.tertiary} />
      <MetricCard label="전체 ROI" value="374%" icon={Target} accentColor={T.secondary} />
    </div>

    <div style={{ display: "flex", gap: 20 }}>
      {/* Revenue Chart */}
      <div style={{ flex: 2, background: T.surfaceContainerLow, borderRadius: 12, padding: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
          <h3 style={{ fontFamily: font.display, fontSize: 18, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
            <Activity size={18} color={T.primary} /> 주차별 수익 추이
          </h3>
          <div style={{ display: "flex", gap: 16, fontSize: 12, color: T.onSurfaceVariant }}>
            <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: T.primary, display: "inline-block" }} /> 매출액
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: T.error, display: "inline-block" }} /> 광고비
            </span>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={weeklyRevenue} barGap={4}>
            <CartesianGrid strokeDasharray="3 3" stroke={T.surfaceVariant + "20"} />
            <XAxis dataKey="week" tick={{ fontSize: 11, fill: T.onSurfaceVariant }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: T.onSurfaceVariant }} axisLine={false} tickLine={false} />
            <Tooltip content={<ChartTooltipContent />} />
            <Bar dataKey="revenue" name="매출액" fill={T.surfaceVariant} radius={[4, 4, 0, 0]}>
              {weeklyRevenue.map((_, i) => (
                <Cell key={i} fill={i === 2 ? T.primary : `${T.surfaceVariant}cc`} />
              ))}
            </Bar>
            <Bar dataKey="adCost" name="광고비" fill={`${T.error}60`} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* AI Insight */}
      <div style={{ flex: 1 }}>
        <Glass glow={T.secondary} style={{ padding: 24, height: "100%", display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <Sparkles size={18} color={T.secondary} />
            <h3 style={{ fontFamily: font.display, fontSize: 16, fontWeight: 600 }}>AI 분석 인사이트</h3>
          </div>
          <div style={{ marginBottom: 12 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: T.secondary }}>수익 최적화</span>
          </div>
          <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.7, flex: 1 }}>
            3주차 인플루언서 정산 완료 후 순수익률이 15% 이상 상승했습니다. 마이크로 인플루언서 비중을 20% 늘리는 것을 추천합니다.
          </p>
          <div style={{ background: T.surfaceContainerLow, borderRadius: 8, padding: "14px 18px", marginTop: 16 }}>
            <div style={{ fontSize: 11, color: T.onSurfaceVariant }}>예상 수익(다음 달)</div>
            <div style={{ fontFamily: font.display, fontSize: 28, fontWeight: 700, color: T.tertiary, marginTop: 4 }}>$165,000</div>
          </div>
        </Glass>
      </div>
    </div>

    {/* Settlement Table */}
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 style={{ fontFamily: font.display, fontSize: 20, fontWeight: 600 }}>인플루언서 정산 현황</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <BtnSecondary>전체보기</BtnSecondary>
          <BtnSecondary icon={Filter}>필터링</BtnSecondary>
        </div>
      </div>
      <div style={{ background: T.surfaceContainerLow, borderRadius: 12, overflow: "hidden" }}>
        <div style={{
          display: "grid", gridTemplateColumns: "2fr 1.5fr 1fr 1fr 0.5fr",
          padding: "14px 24px", background: T.surfaceContainer,
          fontSize: 12, color: T.onSurfaceVariant, fontWeight: 600,
        }}>
          <span>인플루언서</span><span>캠페인명</span><span>정산 금액</span><span>정산 상태</span><span>관리</span>
        </div>
        {settlements.map((s, i) => (
          <div
            key={i}
            className="animate-in"
            style={{
              display: "grid", gridTemplateColumns: "2fr 1.5fr 1fr 1fr 0.5fr",
              padding: "16px 24px", alignItems: "center",
              background: i % 2 === 0 ? T.surfaceContainerLow : `${T.surfaceContainer}60`,
              animationDelay: `${i * 0.06}s`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{
                width: 38, height: 38, borderRadius: "50%", background: T.surfaceContainerHighest,
                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
              }}>👤</div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{s.name} ({s.handle})</div>
                <div style={{ fontSize: 11, color: T.onSurfaceVariant }}>{s.category}</div>
              </div>
            </div>
            <div style={{ fontSize: 13, color: T.onSurface }}>{s.campaign}</div>
            <div style={{ fontFamily: font.display, fontSize: 14, fontWeight: 600 }}>{s.amount}</div>
            <Badge color={s.statusColor}>{s.status}</Badge>
            <MoreVertical size={16} color={T.onSurfaceVariant} style={{ cursor: "pointer" }} />
          </div>
        ))}
      </div>
      <div style={{ textAlign: "center", marginTop: 16 }}>
        <BtnSecondary icon={ChevronDown}>데이터 더보기</BtnSecondary>
      </div>
    </div>
  </div>
);


// ═══════════════════════════════════════════════════
//   PAGE: Campaigns (캠페인)
// ═══════════════════════════════════════════════════

const CampaignsPage = () => {
  const campaigns = [
    { name: "Summer Glow Skin", status: "진행중", statusColor: T.tertiary, influencer: "Kim Jisu", budget: "₩2,500만", spent: "₩1,800만", roi: "6.2x", progress: 72 },
    { name: "Pro Mouse Launch", status: "진행중", statusColor: T.primary, influencer: "Lee Minho", budget: "₩1,200만", spent: "₩950만", roi: "4.8x", progress: 79 },
    { name: "Eco Backpack Series", status: "준비중", statusColor: T.onSurfaceVariant, influencer: "Park Sora", budget: "₩800만", spent: "₩0", roi: "-", progress: 0 },
    { name: "Protein Shake Mix", status: "완료", statusColor: T.secondary, influencer: "Jung Hoon", budget: "₩3,000만", spent: "₩2,900만", roi: "8.4x", progress: 100 },
    { name: "NEON-X1-PRO Launch", status: "진행중", statusColor: T.tertiary, influencer: "아우라_미니멀리스트", budget: "₩5,000만", spent: "₩3,200만", roi: "12.4x", progress: 64 },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ fontFamily: font.display, fontSize: 32, fontWeight: 700 }}>캠페인 관리</h1>
          <p style={{ fontSize: 14, color: T.onSurfaceVariant, marginTop: 4 }}>활성 캠페인 현황 및 성과 추적</p>
        </div>
        <BtnPrimary icon={Plus}>새 캠페인 생성</BtnPrimary>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <MetricCard label="활성 캠페인" value="5" icon={Megaphone} accentColor={T.primary} />
        <MetricCard label="총 예산" value="₩1.25억" icon={Target} accentColor={T.secondary} />
        <MetricCard label="평균 ROI" value="7.9x" change="+18%" changeDir="up" icon={TrendingUp} accentColor={T.tertiary} />
        <MetricCard label="총 도달" value="2.4M" change="+32%" changeDir="up" icon={Eye} accentColor={T.primary} />
      </div>

      <div style={{ background: T.surfaceContainerLow, borderRadius: 12, overflow: "hidden" }}>
        <div style={{
          display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1.5fr",
          padding: "14px 24px", background: T.surfaceContainer,
          fontSize: 12, color: T.onSurfaceVariant, fontWeight: 600,
        }}>
          <span>캠페인</span><span>상태</span><span>예산</span><span>집행</span><span>ROI</span><span>진행률</span>
        </div>
        {campaigns.map((c, i) => (
          <div
            key={i}
            className="animate-in"
            style={{
              display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1.5fr",
              padding: "18px 24px", alignItems: "center",
              background: i % 2 === 0 ? T.surfaceContainerLow : `${T.surfaceContainer}60`,
              cursor: "pointer", transition: "background 0.15s",
              animationDelay: `${i * 0.06}s`,
            }}
            onMouseEnter={e => e.currentTarget.style.background = T.surfaceContainerHigh}
            onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? T.surfaceContainerLow : `${T.surfaceContainer}60`}
          >
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{c.name}</div>
              <div style={{ fontSize: 12, color: T.onSurfaceVariant }}>{c.influencer}</div>
            </div>
            <Badge color={c.statusColor}>{c.status}</Badge>
            <div style={{ fontSize: 13 }}>{c.budget}</div>
            <div style={{ fontSize: 13 }}>{c.spent}</div>
            <div style={{ fontFamily: font.display, fontWeight: 600, color: c.roi === "-" ? T.onSurfaceVariant : T.tertiary }}>{c.roi}</div>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: T.onSurfaceVariant }}>{c.progress}%</span>
              </div>
              <div style={{ height: 6, background: T.surfaceContainerHighest, borderRadius: 3, overflow: "hidden" }}>
                <div style={{
                  width: `${c.progress}%`, height: "100%", borderRadius: 3,
                  background: c.progress === 100 ? T.secondary : c.progress > 0 ? `linear-gradient(90deg, ${T.primary}, ${T.tertiary})` : T.surfaceVariant,
                }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════
//   COMPONENT: AI Insight Hub (Slide Panel)
// ═══════════════════════════════════════════════════

const insightData = [
  {
    id: 1, type: "prediction", priority: "high", time: "방금",
    title: "주문량 급증 예측",
    body: "NEON-X1-PRO의 주문량이 향후 45분 내 평소 대비 24% 증가할 것으로 예측됩니다. 현재 재고 582개로 4시간 내 소진 가능성이 있습니다.",
    action: "재고 확보 프로세스 시작",
    confidence: 94,
    source: "수요 예측 모델 (XGBoost)",
    icon: TrendingUp, color: T.primary,
  },
  {
    id: 2, type: "matching", priority: "high", time: "12분 전",
    title: "인플루언서 매칭 발견",
    body: "아우라_미니멀리스트(@aura_minimal)와 루나 에코 헤드폰의 매칭 점수가 98%로 산출되었습니다. 카테고리 적합성, 과거 전환율, 오디언스 분포 모두 최상위입니다.",
    action: "캠페인 제안 발송",
    confidence: 98,
    source: "매칭 엔진 (3-Signal Score)",
    icon: Users, color: T.secondary,
  },
  {
    id: 3, type: "anomaly", priority: "critical", time: "28분 전",
    title: "재고 소진 긴급 경고",
    body: "SKU-A892 (Premium Cream) 재고가 14개 남았습니다. 현재 판매 속도 기준 3시간 내 품절 예상. 공급사 Global Tech Logistics에 긴급 발주 제안서가 준비되었습니다.",
    action: "자동 협상 제안서 전송",
    confidence: 99,
    source: "이상징후 감지 (stock_alert)",
    icon: AlertTriangle, color: T.error,
  },
  {
    id: 4, type: "optimization", priority: "medium", time: "1시간 전",
    title: "광고 예산 최적화 제안",
    body: "고효율 인플루언서 3명(Kim Sora, 테크뱅가드, 아우라_미니멀리스트)의 CPC가 15% 하락 중입니다. 예산을 20% 증액 시 매출 8% 추가 상승 예상 (ROI 6.8x → 7.4x).",
    action: "광고 최적화 적용",
    confidence: 87,
    source: "ROI 엔진 (Ad Optimizer)",
    icon: Target, color: T.tertiary,
  },
  {
    id: 5, type: "sentiment", priority: "medium", time: "2시간 전",
    title: "소셜 감성 트렌드 변화",
    body: "Summer Glow Skin 캠페인의 인스타 댓글 긍정도가 지난 6시간 동안 72% → 89%로 상승했습니다. '피부결 개선', '발림성 좋음' 키워드가 급증하고 있습니다.",
    action: "캠페인 예산 증액 검토",
    confidence: 82,
    source: "텍스트 감성 분석 (Korean NLP)",
    icon: MessageSquare, color: T.primary,
  },
  {
    id: 6, type: "revenue", priority: "low", time: "3시간 전",
    title: "수익 최적화 리포트",
    body: "3주차 인플루언서 정산 완료 후 순수익률이 15.8% 상승했습니다. 마이크로 인플루언서(B티어) 비중을 현재 30%에서 50%로 늘리면 다음 달 예상 수익이 $165,000까지 증가합니다.",
    action: "마이크로 인플루언서 풀 확대",
    confidence: 79,
    source: "수익성 분석 AI",
    icon: BarChart3, color: T.tertiary,
  },
];

const priorityConfig = {
  critical: { label: "CRITICAL", bg: `${T.error}20`, color: T.error },
  high: { label: "HIGH", bg: `${T.primary}15`, color: T.primary },
  medium: { label: "MEDIUM", bg: `${T.secondary}15`, color: T.secondary },
  low: { label: "LOW", bg: `${T.surfaceVariant}30`, color: T.onSurfaceVariant },
};

const AIInsightHub = ({ isOpen, onClose }) => {
  const [filter, setFilter] = useState("all");
  const [dismissed, setDismissed] = useState(new Set());
  const [actioned, setActioned] = useState(new Set());

  const filters = [
    { key: "all", label: "전체", count: insightData.length },
    { key: "critical", label: "긴급", count: insightData.filter(i => i.priority === "critical").length },
    { key: "high", label: "높음", count: insightData.filter(i => i.priority === "high").length },
    { key: "medium", label: "보통", count: insightData.filter(i => i.priority === "medium").length },
  ];

  const filtered = insightData
    .filter(i => !dismissed.has(i.id))
    .filter(i => filter === "all" || i.priority === filter);

  const handleAction = (id) => {
    setActioned(prev => new Set([...prev, id]));
  };

  const handleDismiss = (id) => {
    setDismissed(prev => new Set([...prev, id]));
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0,
          background: "#00000050",
          backdropFilter: "blur(4px)",
          zIndex: 200,
          animation: "fadeIn 0.2s ease-out",
        }}
      />
      {/* Panel */}
      <div
        style={{
          position: "fixed", top: 0, right: 0,
          width: Math.min(460, window?.innerWidth || 460),
          height: "100vh",
          background: T.surfaceDim,
          zIndex: 201,
          display: "flex", flexDirection: "column",
          boxShadow: `-8px 0 40px ${T.secondary}15`,
          animation: "slideInRight 0.3s ease-out",
        }}
      >
        {/* Header */}
        <div style={{
          padding: "20px 24px",
          borderBottom: `1px solid ${T.surfaceVariant}20`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 38, height: 38, borderRadius: 10,
                background: `linear-gradient(135deg, ${T.secondary}30, ${T.primary}20)`,
                display: "flex", alignItems: "center", justifyContent: "center",
                boxShadow: `0 0 16px ${T.secondary}25`,
              }}>
                <Sparkles size={20} color={T.secondary} />
              </div>
              <div>
                <h2 style={{ fontFamily: font.display, fontSize: 18, fontWeight: 700, color: T.onSurface }}>AI Insight Hub</h2>
                <div style={{ fontSize: 11, color: T.onSurfaceVariant, display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
                  <PulseDot color={T.tertiary} size={6} /> 실시간 업데이트 활성
                </div>
              </div>
            </div>
            <button
              onClick={onClose}
              style={{
                background: T.surfaceContainerHigh, border: "none", cursor: "pointer",
                width: 32, height: 32, borderRadius: 8,
                display: "flex", alignItems: "center", justifyContent: "center",
                color: T.onSurfaceVariant,
              }}
            >
              <X size={18} />
            </button>
          </div>

          {/* Summary Bar */}
          <div style={{
            display: "flex", gap: 12, padding: "12px 16px",
            background: T.surfaceContainerLow, borderRadius: 10,
            marginBottom: 14,
          }}>
            {[
              { label: "총 인사이트", value: insightData.length - dismissed.size, color: T.onSurface },
              { label: "실행 완료", value: actioned.size, color: T.tertiary },
              { label: "평균 신뢰도", value: "89%", color: T.primary },
            ].map((s, i) => (
              <div key={i} style={{ flex: 1, textAlign: "center" }}>
                <div style={{ fontFamily: font.display, fontSize: 20, fontWeight: 700, color: s.color }}>{s.value}</div>
                <div style={{ fontSize: 10, color: T.onSurfaceVariant, marginTop: 2 }}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Filter Tabs */}
          <div style={{ display: "flex", gap: 6 }}>
            {filters.map(f => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                style={{
                  padding: "5px 12px", borderRadius: 6, border: "none", cursor: "pointer",
                  fontSize: 11, fontWeight: filter === f.key ? 600 : 400,
                  background: filter === f.key ? `${T.primary}15` : T.surfaceContainerHigh,
                  color: filter === f.key ? T.primary : T.onSurfaceVariant,
                  display: "flex", alignItems: "center", gap: 4,
                }}
              >
                {f.label}
                <span style={{
                  fontSize: 10, padding: "1px 5px", borderRadius: 4,
                  background: filter === f.key ? `${T.primary}20` : `${T.surfaceVariant}40`,
                }}>{f.count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Insight Cards (scrollable) */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          {filtered.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: T.onSurfaceVariant }}>
              <CheckCircle2 size={32} style={{ marginBottom: 12, opacity: 0.4 }} />
              <div style={{ fontSize: 14 }}>모든 인사이트를 처리했습니다</div>
            </div>
          ) : (
            filtered.map((insight, idx) => {
              const p = priorityConfig[insight.priority];
              const done = actioned.has(insight.id);
              return (
                <div
                  key={insight.id}
                  className="animate-in"
                  style={{
                    background: T.surfaceContainerLow,
                    borderRadius: 12,
                    padding: "18px 20px",
                    marginBottom: 12,
                    opacity: done ? 0.6 : 1,
                    transition: "all 0.3s",
                    animationDelay: `${idx * 0.05}s`,
                  }}
                >
                  {/* Top row: priority + time */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{
                        width: 30, height: 30, borderRadius: 8,
                        background: `${insight.color}15`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        <insight.icon size={16} color={insight.color} />
                      </div>
                      <span style={{
                        fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                        padding: "2px 8px", borderRadius: 4,
                        background: p.bg, color: p.color,
                      }}>{p.label}</span>
                    </div>
                    <span style={{ fontSize: 11, color: T.onSurfaceVariant }}>{insight.time}</span>
                  </div>

                  {/* Title + Body */}
                  <div style={{ fontFamily: font.display, fontSize: 15, fontWeight: 600, color: T.onSurface, marginBottom: 8 }}>
                    {insight.title}
                  </div>
                  <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.6, marginBottom: 14 }}>
                    {insight.body}
                  </p>

                  {/* Confidence + Source */}
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ fontSize: 11, color: T.onSurfaceVariant }}>신뢰도</span>
                        <span style={{ fontSize: 11, fontWeight: 600, color: insight.confidence >= 90 ? T.tertiary : T.primary }}>{insight.confidence}%</span>
                      </div>
                      <div style={{ height: 4, background: T.surfaceContainerHighest, borderRadius: 2, overflow: "hidden" }}>
                        <div style={{
                          width: `${insight.confidence}%`, height: "100%", borderRadius: 2,
                          background: insight.confidence >= 90
                            ? `linear-gradient(90deg, ${T.tertiary}, ${T.primary})`
                            : `linear-gradient(90deg, ${T.primary}, ${T.secondary})`,
                        }} />
                      </div>
                    </div>
                    <div style={{
                      fontSize: 10, color: T.onSurfaceVariant, padding: "3px 8px",
                      background: T.surfaceContainerHighest, borderRadius: 4,
                      whiteSpace: "nowrap",
                    }}>
                      {insight.source}
                    </div>
                  </div>

                  {/* Actions */}
                  <div style={{ display: "flex", gap: 8 }}>
                    {done ? (
                      <div style={{
                        flex: 1, padding: "8px", borderRadius: 6, textAlign: "center",
                        background: `${T.tertiary}15`, color: T.tertiary,
                        fontSize: 12, fontWeight: 600,
                        display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                      }}>
                        <CheckCircle2 size={14} /> 실행 완료
                      </div>
                    ) : (
                      <>
                        <button
                          onClick={() => handleAction(insight.id)}
                          style={{
                            flex: 1, padding: "8px 12px", borderRadius: 6, border: "none", cursor: "pointer",
                            background: `${insight.color}15`, color: insight.color,
                            fontSize: 12, fontWeight: 600,
                            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                          }}
                        >
                          <Play size={12} /> {insight.action}
                        </button>
                        <button
                          onClick={() => handleDismiss(insight.id)}
                          style={{
                            padding: "8px 12px", borderRadius: 6, border: "none", cursor: "pointer",
                            background: T.surfaceContainerHigh, color: T.onSurfaceVariant,
                            fontSize: 12,
                          }}
                        >
                          무시
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Bottom */}
        <div style={{
          padding: "16px 20px",
          borderTop: `1px solid ${T.surfaceVariant}20`,
          display: "flex", gap: 10,
        }}>
          <button
            onClick={() => { setDismissed(new Set()); setActioned(new Set()); setFilter("all"); }}
            style={{
              flex: 1, padding: "10px", borderRadius: 8, border: "none", cursor: "pointer",
              background: T.surfaceContainerHigh, color: T.onSurfaceVariant,
              fontSize: 12, fontWeight: 500,
              display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
            }}
          >
            <RefreshCw size={14} /> 초기화
          </button>
          <button style={{
            flex: 2, padding: "10px", borderRadius: 8, border: "none", cursor: "pointer",
            background: `linear-gradient(135deg, ${T.secondary}25, ${T.primary}15)`,
            color: T.primary, fontSize: 12, fontWeight: 600,
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
            boxShadow: `0 0 12px ${T.secondary}15`,
          }}>
            <Bot size={14} /> AI에게 종합 분석 요청
          </button>
        </div>
      </div>
    </>
  );
};


// ═══════════════════════════════════════════════════
//   PAGE: User Guide (사용자 가이드)
// ═══════════════════════════════════════════════════

const GuideSection = ({ icon: Icon, iconColor, number, title, subtitle, children, defaultOpen = false }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      className="animate-in"
      style={{
        background: T.surfaceContainerLow,
        borderRadius: 12,
        overflow: "hidden",
        transition: "all 0.3s",
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%", padding: "20px 24px",
          display: "flex", alignItems: "center", gap: 16,
          background: "transparent", border: "none", cursor: "pointer",
          textAlign: "left",
        }}
      >
        <div style={{
          width: 44, height: 44, borderRadius: 10, flexShrink: 0,
          background: `${iconColor}15`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Icon size={22} color={iconColor} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: iconColor, letterSpacing: "0.08em" }}>STEP {number}</span>
            <h3 style={{ fontFamily: font.display, fontSize: 17, fontWeight: 600, color: T.onSurface }}>{title}</h3>
          </div>
          {subtitle && <p style={{ fontSize: 12, color: T.onSurfaceVariant, marginTop: 3 }}>{subtitle}</p>}
        </div>
        <ChevronRight
          size={20}
          color={T.onSurfaceVariant}
          style={{ transition: "transform 0.2s", transform: open ? "rotate(90deg)" : "rotate(0deg)" }}
        />
      </button>
      {open && (
        <div style={{ padding: "0 24px 24px 24px" }}>
          <div style={{ height: 1, background: `${T.surfaceVariant}30`, marginBottom: 20 }} />
          {children}
        </div>
      )}
    </div>
  );
};

const FeatureCard = ({ icon: Icon, iconColor, title, desc }) => (
  <div style={{
    background: T.surfaceContainerHigh,
    borderRadius: 10,
    padding: "18px 20px",
    display: "flex", gap: 14, alignItems: "flex-start",
  }}>
    <div style={{
      width: 36, height: 36, borderRadius: 8, flexShrink: 0,
      background: `${iconColor}12`,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <Icon size={18} color={iconColor} />
    </div>
    <div>
      <div style={{ fontSize: 14, fontWeight: 600, color: T.onSurface, marginBottom: 4 }}>{title}</div>
      <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.6 }}>{desc}</p>
    </div>
  </div>
);

const StepItem = ({ num, text, highlight }) => (
  <div style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 14 }}>
    <div style={{
      width: 26, height: 26, borderRadius: "50%", flexShrink: 0,
      background: `${T.primary}15`, color: T.primary,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 12, fontWeight: 700,
    }}>{num}</div>
    <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.6, paddingTop: 3 }}>
      {text}
      {highlight && <span style={{ color: T.primary, fontWeight: 600 }}> {highlight}</span>}
    </p>
  </div>
);

const TipBox = ({ type = "tip", children }) => {
  const config = {
    tip: { icon: Lightbulb, color: T.tertiary, label: "TIP" },
    info: { icon: Info, color: T.primary, label: "INFO" },
    warning: { icon: AlertTriangle, color: "#ffb74d", label: "WARNING" },
    ai: { icon: Sparkles, color: T.secondary, label: "AI FEATURE" },
  };
  const c = config[type];
  return (
    <div style={{
      background: `${c.color}08`,
      borderLeft: `3px solid ${c.color}`,
      borderRadius: "0 8px 8px 0",
      padding: "14px 18px",
      marginTop: 12, marginBottom: 12,
      display: "flex", gap: 12, alignItems: "flex-start",
    }}>
      <c.icon size={16} color={c.color} style={{ marginTop: 2, flexShrink: 0 }} />
      <div>
        <span style={{ fontSize: 10, fontWeight: 700, color: c.color, letterSpacing: "0.08em" }}>{c.label}</span>
        <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.6, marginTop: 4 }}>{children}</p>
      </div>
    </div>
  );
};

const ColorToken = ({ color, label, desc }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
    <div style={{
      width: 32, height: 32, borderRadius: 6, background: color,
      boxShadow: `0 0 10px ${color}40`,
    }} />
    <div>
      <span style={{ fontSize: 13, fontWeight: 600, color: T.onSurface }}>{label}</span>
      <span style={{ fontSize: 12, color: T.onSurfaceVariant, marginLeft: 8 }}>{desc}</span>
    </div>
  </div>
);

const UserGuidePage = () => {
  const [activeQuickNav, setActiveQuickNav] = useState(null);

  const quickNavItems = [
    { label: "시작하기", icon: Rocket, color: T.tertiary },
    { label: "대시보드", icon: LayoutDashboard, color: T.primary },
    { label: "캠페인", icon: Megaphone, color: T.secondary },
    { label: "인플루언서", icon: Users, color: T.primary },
    { label: "재고", icon: Package, color: "#ffb74d" },
    { label: "리포트", icon: FileText, color: T.tertiary },
    { label: "AI 기능", icon: Sparkles, color: T.secondary },
    { label: "FAQ", icon: HelpCircle, color: T.onSurfaceVariant },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Hero Header */}
      <div style={{
        background: `linear-gradient(135deg, ${T.surfaceContainerLow}, ${T.primary}08, ${T.secondary}06)`,
        borderRadius: 16, padding: "36px 40px",
        position: "relative", overflow: "hidden",
      }}>
        <div style={{
          position: "absolute", top: -40, right: -40, width: 200, height: 200,
          background: `radial-gradient(circle, ${T.primary}10, transparent 70%)`,
        }} />
        <div style={{
          position: "absolute", bottom: -60, right: 80, width: 160, height: 160,
          background: `radial-gradient(circle, ${T.secondary}08, transparent 70%)`,
        }} />
        <div style={{ position: "relative" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <div style={{
              width: 48, height: 48, borderRadius: 12,
              background: `linear-gradient(135deg, ${T.primary}30, ${T.secondary}20)`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <BookOpen size={26} color={T.primary} />
            </div>
            <div>
              <h1 style={{ fontFamily: font.display, fontSize: 30, fontWeight: 700 }}>User Guide</h1>
              <p style={{ fontSize: 12, color: T.onSurfaceVariant, letterSpacing: "0.05em" }}>ICOM AGENT PROTOCOL v1.0.4</p>
            </div>
          </div>
          <p style={{ fontSize: 15, color: T.onSurfaceVariant, lineHeight: 1.7, maxWidth: 640, marginTop: 12 }}>
            ICOM Agent는 인플루언서 커머스의 전 과정을 AI로 자동화하는 지능형 플랫폼입니다.
            수요 예측부터 재고 관리, 광고 최적화, 공급사 협상까지 — 이 가이드를 통해 플랫폼의 모든 기능을 빠르게 익혀보세요.
          </p>
          <div style={{ display: "flex", gap: 12, marginTop: 20 }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "6px 14px", borderRadius: 20,
              background: `${T.tertiary}15`, fontSize: 12, color: T.tertiary, fontWeight: 600,
            }}>
              <CheckCircle2 size={14} /> 예상 소요 시간: 10분
            </div>
            <div style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "6px 14px", borderRadius: 20,
              background: `${T.primary}15`, fontSize: 12, color: T.primary, fontWeight: 600,
            }}>
              <Sparkles size={14} /> AI 기능 포함
            </div>
          </div>
        </div>
      </div>

      {/* Quick Navigation */}
      <div>
        <div style={{ fontSize: 11, color: T.onSurfaceVariant, fontWeight: 600, letterSpacing: "0.08em", marginBottom: 12 }}>
          QUICK NAVIGATION
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {quickNavItems.map((q, i) => (
            <button
              key={i}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "8px 16px", borderRadius: 8, border: "none", cursor: "pointer",
                background: T.surfaceContainerLow,
                color: T.onSurfaceVariant, fontSize: 12, fontWeight: 500,
                transition: "all 0.15s",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = `${q.color}15`; e.currentTarget.style.color = q.color; }}
              onMouseLeave={e => { e.currentTarget.style.background = T.surfaceContainerLow; e.currentTarget.style.color = T.onSurfaceVariant; }}
            >
              <q.icon size={14} /> {q.label}
            </button>
          ))}
        </div>
      </div>

      {/* ─── Section 1: Getting Started ─── */}
      <GuideSection
        icon={Rocket} iconColor={T.tertiary} number="01"
        title="시작하기" subtitle="ICOM Agent에 처음 오신 것을 환영합니다"
        defaultOpen={true}
      >
        <p style={{ fontSize: 14, color: T.onSurface, lineHeight: 1.7, marginBottom: 20 }}>
          ICOM Agent는 <strong style={{ color: T.primary }}>'돈 되는 AI'</strong> 4단계 프레임워크를 기반으로 설계되었습니다.
          각 단계는 순차적으로 연결되어 인플루언서 커머스의 전체 워크플로우를 자동화합니다.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
          {[
            { phase: "Phase 0", label: "자동화", desc: "데이터 수집 파이프라인", color: T.onSurfaceVariant, icon: Globe },
            { phase: "Phase 1", label: "예측", desc: "XGBoost 수요 예측", color: T.primary, icon: BarChart3 },
            { phase: "Phase 2", label: "시뮬레이션", desc: "광고/딜/ROI 최적화", color: T.secondary, icon: Target },
            { phase: "Phase 3", label: "고도화", desc: "자율 에이전트 운영", color: T.tertiary, icon: Bot },
          ].map((p, i) => (
            <div
              key={i}
              style={{
                background: T.surfaceContainerHigh,
                borderRadius: 10,
                padding: 16,
                textAlign: "center",
                position: "relative",
              }}
            >
              {i < 3 && (
                <div style={{
                  position: "absolute", right: -10, top: "50%", transform: "translateY(-50%)",
                  color: T.surfaceVariant, fontSize: 18, zIndex: 1,
                }}>→</div>
              )}
              <p.icon size={24} color={p.color} style={{ marginBottom: 8 }} />
              <div style={{ fontSize: 10, fontWeight: 700, color: p.color, letterSpacing: "0.06em", marginBottom: 4 }}>{p.phase}</div>
              <div style={{ fontFamily: font.display, fontSize: 16, fontWeight: 600, color: T.onSurface }}>{p.label}</div>
              <div style={{ fontSize: 11, color: T.onSurfaceVariant, marginTop: 4 }}>{p.desc}</div>
            </div>
          ))}
        </div>

        <div style={{ fontSize: 14, fontWeight: 600, color: T.onSurface, marginBottom: 14 }}>인터페이스 색상 가이드</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16 }}>
          <ColorToken color={T.primary} label="Cyan (시안)" desc="— 실시간 데이터, 핵심 지표" />
          <ColorToken color={T.secondary} label="Purple (퍼플)" desc="— AI 추천 및 인사이트" />
          <ColorToken color={T.tertiary} label="Green (그린)" desc="— 수익 증가, 긍정 지표" />
          <ColorToken color={T.error} label="Red (레드)" desc="— 경고, 재고 부족, 감소" />
        </div>

        <TipBox type="tip">
          인터페이스 곳곳에서 보이는 <strong>녹색 점멸 인디케이터</strong>는 해당 데이터가 실시간으로 업데이트되고 있음을 의미합니다. 차트와 지표는 자동 갱신되며, 수동 새로고침이 필요 없습니다.
        </TipBox>
      </GuideSection>

      {/* ─── Section 2: Dashboard ─── */}
      <GuideSection
        icon={LayoutDashboard} iconColor={T.primary} number="02"
        title="종합 대시보드" subtitle="전체 비즈니스 현황을 한눈에 파악하세요"
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
          <FeatureCard
            icon={Activity} iconColor={T.primary}
            title="실시간 주문 속도 모니터"
            desc="시간당 주문 발생 빈도를 라이브 차트로 추적합니다. AI 예측선(보라색 점선)과 비교하여 이상 패턴을 즉시 감지할 수 있습니다."
          />
          <FeatureCard
            icon={TrendingUp} iconColor={T.tertiary}
            title="KPI 메트릭 카드"
            desc="총 매출, 평균 ROI, 수요 예측 정확도, 활성 캠페인 수를 상단에 표시합니다. 화살표 색상으로 증감 추세를 직관적으로 확인합니다."
          />
          <FeatureCard
            icon={AlertTriangle} iconColor={T.error}
            title="재고 부족 경고"
            desc="재고 수준이 임계점 이하로 내려간 상품이 자동 감지됩니다. '발주' 버튼 클릭 시 공급사에 긴급 발주 프로세스가 시작됩니다."
          />
          <FeatureCard
            icon={Sparkles} iconColor={T.secondary}
            title="얼리 센싱 피드"
            desc="AI가 소셜 트렌드를 분석하여 잠재력 높은 인플루언서를 자동 발견합니다. 반응 지수와 예측 판매량을 기반으로 우선순위를 제안합니다."
          />
        </div>

        <div style={{ fontSize: 14, fontWeight: 600, color: T.onSurface, marginBottom: 12 }}>대시보드 활용 워크플로우</div>
        <StepItem num="1" text="상단 KPI 카드에서 전체 비즈니스 건강도를 확인합니다." highlight="(빨간색 하락 지표 우선 확인)" />
        <StepItem num="2" text="실시간 주문 차트에서 AI 예측(보라 점선)과 실제 주문(시안 영역)의 차이를 모니터링합니다." />
        <StepItem num="3" text="재고 부족 경고가 있다면, '발주' 버튼을 눌러 자동 협상 프로세스를 시작합니다." />
        <StepItem num="4" text="얼리 센싱 피드에서 High Potential 태그가 붙은 인플루언서를 클릭하여 캠페인 기회를 탐색합니다." />

        <TipBox type="ai">
          AI PREDICTION 패널은 향후 45분 내 주문량 변동을 예측합니다. 예측 정확도가 90% 이상일 때 자동으로 시스템 리소스(서버 스케일링, 재고 예약)가 할당됩니다.
        </TipBox>
      </GuideSection>

      {/* ─── Section 3: Campaigns ─── */}
      <GuideSection
        icon={Megaphone} iconColor={T.secondary} number="03"
        title="캠페인 관리" subtitle="인플루언서 캠페인의 생성부터 정산까지"
      >
        <div style={{ fontSize: 14, color: T.onSurface, lineHeight: 1.7, marginBottom: 16 }}>
          캠페인 페이지에서는 모든 인플루언서 협업 프로젝트를 관리합니다. 각 캠페인의 예산 집행률, ROI, 진행 상태를 실시간으로 추적할 수 있습니다.
        </div>

        <div style={{ fontSize: 14, fontWeight: 600, color: T.onSurface, marginBottom: 12 }}>캠페인 상태 분류</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
          {[
            { label: "준비중", color: T.onSurfaceVariant, desc: "캠페인 설정 완료, 론칭 대기" },
            { label: "진행중", color: T.tertiary, desc: "활성 상태, 실시간 성과 추적" },
            { label: "완료", color: T.secondary, desc: "캠페인 종료, 정산 진행" },
          ].map((s, i) => (
            <div
              key={i}
              style={{
                flex: 1, minWidth: 160,
                background: T.surfaceContainerHigh, borderRadius: 8, padding: 14,
              }}
            >
              <Badge color={s.color}>{s.label}</Badge>
              <p style={{ fontSize: 12, color: T.onSurfaceVariant, marginTop: 8, lineHeight: 1.5 }}>{s.desc}</p>
            </div>
          ))}
        </div>

        <div style={{ fontSize: 14, fontWeight: 600, color: T.onSurface, marginBottom: 12 }}>새 캠페인 생성하기</div>
        <StepItem num="1" text="우측 상단의" highlight="'새 캠페인 생성' 버튼을 클릭합니다." />
        <StepItem num="2" text="캠페인명, 대상 상품, 예산, 기간을 입력합니다." />
        <StepItem num="3" text="AI 매칭 엔진이 자동으로 최적 인플루언서 후보를 추천합니다." />
        <StepItem num="4" text="인플루언서 선정 후 캠페인 제안서를 자동 발송합니다." />
        <StepItem num="5" text="수락 시 캠페인이 활성화되고, 실시간 ROI 추적이 시작됩니다." />

        <TipBox type="info">
          진행률 바의 색상은 캠페인 건강도를 나타냅니다. 시안→그린 그라데이션은 정상 진행, 보라색은 완료, 회색은 미시작 상태입니다.
        </TipBox>

        <div style={{ fontSize: 14, fontWeight: 600, color: T.onSurface, marginBottom: 12, marginTop: 16 }}>핵심 지표 이해하기</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <FeatureCard icon={Target} iconColor={T.secondary} title="ROI (투자 수익률)" desc="캠페인 수익 / 총 투자비용. ICOM Agent는 ROI 5.0x 이상을 '투자 적격'으로 분류합니다." />
          <FeatureCard icon={Eye} iconColor={T.primary} title="도달 (Reach)" desc="캠페인 콘텐츠가 노출된 고유 사용자 수. 인플루언서의 팔로워 수 + 바이럴 확산 포함." />
        </div>
      </GuideSection>

      {/* ─── Section 4: Influencers ─── */}
      <GuideSection
        icon={Users} iconColor={T.primary} number="04"
        title="인플루언서 관리" subtitle="CRM, 성과 분석, AI 매칭을 한 곳에서"
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
          <FeatureCard
            icon={Shield} iconColor={T.tertiary}
            title="티어 시스템 (S/A/B/C)"
            desc="과거 캠페인 성과, 총 매출, ROI를 종합하여 인플루언서를 자동 등급화합니다. S티어는 ROI 10x 이상의 최상위 파트너입니다."
          />
          <FeatureCard
            icon={Sparkles} iconColor={T.secondary}
            title="AI 상품 매칭 제안"
            desc="인플루언서의 카테고리, 팬 베이스, 과거 전환율을 분석하여 최적 상품을 자동 추천합니다. 매칭 점수 90% 이상이면 성공 확률이 매우 높습니다."
          />
          <FeatureCard
            icon={BarChart3} iconColor={T.primary}
            title="전환율 추적"
            desc="주별 전환율 트렌드를 차트로 시각화합니다. 전환율 상승 추세의 인플루언서를 우선 캠페인에 배정하세요."
          />
          <FeatureCard
            icon={Users} iconColor={T.primary}
            title="팬 베이스 분포"
            desc="인플루언서 오디언스의 연령대, 관심사, 지역 분포를 분석합니다. 타겟 고객과의 일치도가 높을수록 캠페인 효과가 극대화됩니다."
          />
        </div>

        <div style={{ fontSize: 14, fontWeight: 600, color: T.onSurface, marginBottom: 12 }}>필터링 & 정렬</div>
        <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.6, marginBottom: 12 }}>
          상단 필터 탭으로 인플루언서를 다양한 기준으로 정렬할 수 있습니다.
        </p>
        <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
          {["ROI순 — 수익성 높은 순", "카테고리별 — 패션, 테크, 뷰티 등", "티어별 — S → A → B → C"].map((f, i) => (
            <div
              key={i}
              style={{
                flex: 1, background: T.surfaceContainerHigh, borderRadius: 8, padding: "10px 14px",
                fontSize: 12, color: T.onSurfaceVariant,
              }}
            >
              {f}
            </div>
          ))}
        </div>

        <TipBox type="ai">
          AI 매칭 패널에서 <strong>"98% MATCH"</strong>와 같은 매칭 점수가 표시됩니다. 이 점수는 카테고리 적합성(30%), 과거 성과(40%), 협업 이력(30%)의 가중 평균으로 산출됩니다. "캠페인 제안 발송하기" 버튼으로 즉시 제안서를 보낼 수 있습니다.
        </TipBox>
      </GuideSection>

      {/* ─── Section 5: Inventory ─── */}
      <GuideSection
        icon={Package} iconColor="#ffb74d" number="05"
        title="재고 관리 & 공급사 협상" subtitle="품절을 예방하고, AI가 자동으로 발주합니다"
      >
        <div style={{ fontSize: 14, color: T.onSurface, lineHeight: 1.7, marginBottom: 20 }}>
          재고 관리 페이지는 실시간 판매 속도를 모니터링하고, 품절 위험을 사전 감지하여 자동으로 공급사에 협상 제안서를 생성합니다.
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
          <FeatureCard
            icon={AlertTriangle} iconColor={T.error}
            title="긴급 재고 경고 배너"
            desc="품절 예상 시간이 4시간 이내인 상품은 페이지 상단에 빨간 배너로 표시됩니다. 현재 재고 수준과 소진 예상 시간을 실시간 제공합니다."
          />
          <FeatureCard
            icon={Activity} iconColor={T.primary}
            title="판매 속도 분석"
            desc="시간대별 판매량 바 차트를 통해 피크 타임을 식별합니다. 시안색 바가 가장 높은 판매량을 기록한 시간대입니다."
          />
          <FeatureCard
            icon={TrendingUp} iconColor={T.tertiary}
            title="수익성 시뮬레이션"
            desc="단위 마진 변화, 리드 타임 단축 등의 시뮬레이션 결과를 우측 패널에 표시합니다. 대량 매입 시 예상 마진 개선율을 확인하세요."
          />
          <FeatureCard
            icon={Bot} iconColor={T.primary}
            title="자동 협상 제안서"
            desc="AI가 공급사에 보낼 협상 제안서를 자동 생성합니다. 재고 확보 수량, 커미션 조건, 납기 조건이 포함되며, 원클릭으로 전송할 수 있습니다."
          />
        </div>

        <TipBox type="warning">
          재고 경고 배너가 나타나면 즉시 대응이 필요합니다. "자동 알림 전송 및 협상 시작" 버튼을 클릭하면 AI가 과거 협상 이력(성공률 92%, 평균 응답 14분)을 기반으로 최적 조건을 제안합니다.
        </TipBox>

        <div style={{ fontSize: 14, fontWeight: 600, color: T.onSurface, marginBottom: 12, marginTop: 8 }}>협상 프로세스 흐름</div>
        <StepItem num="1" text="AI가 재고 소진 속도를 감지하고 긴급 경고를 발생시킵니다." />
        <StepItem num="2" text="공급사 신뢰도(A+ 등급)와 과거 성공률을 기반으로 최적 협상 대상을 선정합니다." />
        <StepItem num="3" text="자동 생성된 협상 제안서를 검토하고 필요 시 수정합니다." />
        <StepItem num="4" text="'자동 알림 전송' 버튼 클릭 시 제안서가 발송되고 응답 추적이 시작됩니다." />
        <StepItem num="5" text="공급사 수락 시 자동 결제 및 물류 프로세스가 실행됩니다." />
      </GuideSection>

      {/* ─── Section 6: Reports ─── */}
      <GuideSection
        icon={FileText} iconColor={T.tertiary} number="06"
        title="수익성 리포트" subtitle="캠페인 성과와 정산을 체계적으로 분석하세요"
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
          <FeatureCard
            icon={BarChart3} iconColor={T.primary}
            title="주차별 수익 추이 차트"
            desc="매출액(시안)과 광고비(레드)를 주차별로 비교합니다. 하이라이트된 주차(시안색 바)는 최고 성과 기간입니다."
          />
          <FeatureCard
            icon={Sparkles} iconColor={T.secondary}
            title="AI 분석 인사이트"
            desc="AI가 수익 트렌드를 분석하여 구체적인 개선 방안을 제안합니다. 예: '마이크로 인플루언서 비중을 20% 늘리세요.'"
          />
          <FeatureCard
            icon={Users} iconColor={T.onSurfaceVariant}
            title="인플루언서 정산 현황"
            desc="각 인플루언서의 캠페인별 정산 금액과 상태(완료/진행중/대기중)를 테이블로 관리합니다."
          />
          <FeatureCard
            icon={FileText} iconColor={T.tertiary}
            title="PDF 리포트 생성"
            desc="'PDF 리포트 생성' 버튼으로 현재 화면의 모든 데이터를 포함한 전문 보고서를 다운로드합니다."
          />
        </div>

        <div style={{ fontSize: 14, fontWeight: 600, color: T.onSurface, marginBottom: 12 }}>핵심 수익 지표</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 16 }}>
          {[
            { label: "총 매출액", desc: "전체 캠페인 매출 합산", color: T.primary },
            { label: "광고 집행비", desc: "인플루언서 수수료 + 광고비", color: T.error },
            { label: "순수익", desc: "매출 - 집행비 = 실제 수익", color: T.tertiary },
            { label: "전체 ROI", desc: "순수익 / 집행비 × 100", color: T.secondary },
          ].map((m, i) => (
            <div key={i} style={{ background: T.surfaceContainerHigh, borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: m.color, marginBottom: 4 }}>{m.label}</div>
              <div style={{ fontSize: 12, color: T.onSurfaceVariant, lineHeight: 1.5 }}>{m.desc}</div>
            </div>
          ))}
        </div>

        <TipBox type="tip">
          정산 상태가 "대기중"인 항목은 인플루언서의 성과 데이터 수집이 완료된 후 자동으로 "진행중"으로 변경됩니다. 정산 완료까지 평균 3-5영업일이 소요됩니다.
        </TipBox>
      </GuideSection>

      {/* ─── Section 7: AI Features ─── */}
      <GuideSection
        icon={Sparkles} iconColor={T.secondary} number="07"
        title="AI 핵심 기능 가이드" subtitle="ICOM Agent의 인공지능이 하는 일들"
      >
        <p style={{ fontSize: 14, color: T.onSurface, lineHeight: 1.7, marginBottom: 20 }}>
          ICOM Agent의 모든 AI 기능은 <strong style={{ color: T.secondary }}>보라색(Purple)</strong> 컬러로 표시됩니다. 보라색 글로우가 있는 패널은 AI가 생성한 인사이트입니다.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 20 }}>
          {[
            {
              icon: BarChart3, title: "수요 예측 (Phase 1)",
              desc: "XGBoost 머신러닝 모델이 18개 피처(좋아요 속도, 참여율, 시간대 등)를 분석하여 상품별 판매량을 예측합니다. 예측 정확도 94%.",
              phase: "PREDICTION",
            },
            {
              icon: Target, title: "광고/딜 시뮬레이션 (Phase 2)",
              desc: "광고 예산별 예상 ROI를 CPM→CTR→CVR 퍼널 모델로 시뮬레이션합니다. 5가지 딜 조건 시나리오를 비교 분석합니다.",
              phase: "SIMULATION",
            },
            {
              icon: Bot, title: "자율 에이전트 (Phase 3)",
              desc: "LangGraph 기반 자율 워크플로우가 감지→예측→분류→최적화→모니터링 전체 과정을 자동 실행합니다.",
              phase: "AUTONOMOUS",
            },
          ].map((f, i) => (
            <div
              key={i}
              style={{
                background: T.surfaceContainerHigh, borderRadius: 10, padding: 20,
                borderTop: `2px solid ${T.secondary}40`,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <f.icon size={20} color={T.secondary} />
                <span style={{ fontSize: 10, fontWeight: 700, color: T.secondary, letterSpacing: "0.06em" }}>{f.phase}</span>
              </div>
              <div style={{ fontFamily: font.display, fontSize: 15, fontWeight: 600, marginBottom: 8 }}>{f.title}</div>
              <p style={{ fontSize: 12, color: T.onSurfaceVariant, lineHeight: 1.6 }}>{f.desc}</p>
            </div>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <FeatureCard
            icon={MessageSquare} iconColor={T.secondary}
            title="텍스트 감성 분석"
            desc="인스타그램 댓글과 게시물의 긍정/부정, 긴급도, 구매 의도, 진정성을 한국어 키워드 기반으로 분석합니다."
          />
          <FeatureCard
            icon={AlertTriangle} iconColor={T.error}
            title="이상징후 감지"
            desc="주문 급증/급감, 참여도 불일치, ROI 악화, 가짜 참여 등 5가지 이상 유형을 실시간 감시합니다."
          />
        </div>

        <TipBox type="ai">
          AI Insight Hub 버튼(사이드바 하단)을 클릭하면 모든 AI 인사이트를 한 곳에서 모아볼 수 있습니다. 각 인사이트에는 신뢰도 점수가 함께 표시되어, 높은 신뢰도의 제안부터 우선 실행할 수 있습니다.
        </TipBox>
      </GuideSection>

      {/* ─── Section 8: FAQ ─── */}
      <GuideSection
        icon={HelpCircle} iconColor={T.onSurfaceVariant} number="08"
        title="자주 묻는 질문 (FAQ)" subtitle="궁금한 점이 있으신가요?"
      >
        {[
          {
            q: "데이터는 얼마나 자주 업데이트되나요?",
            a: "실시간 데이터(주문 속도, 재고)는 3초 간격으로 갱신됩니다. AI 예측 모델은 1시간마다 재학습되며, 일간 리포트는 매일 자정에 생성됩니다.",
          },
          {
            q: "AI 추천을 무시하고 수동으로 결정해도 되나요?",
            a: "물론입니다. 모든 AI 추천은 제안 사항이며, 최종 의사결정은 운영자가 합니다. 자동 실행 기능(광고 최적화, 공급사 협상)도 '최종 승인 필요' 모드로 설정할 수 있습니다.",
          },
          {
            q: "인플루언서 데이터는 어디서 가져오나요?",
            a: "Instagram Graph API를 통해 공식 비즈니스 계정 데이터를 수집합니다. 인플루언서가 OAuth 로그인으로 권한을 부여해야 데이터 수집이 시작됩니다.",
          },
          {
            q: "ROI 5.0x 기준은 변경할 수 있나요?",
            a: "Settings 페이지에서 ROI 임계값, 경고 기준, 자동 실행 조건 등을 커스터마이즈할 수 있습니다. 업종과 마진 구조에 맞게 조정하세요.",
          },
          {
            q: "모바일에서도 사용할 수 있나요?",
            a: "네, 모바일 반응형 레이아웃이 적용되어 있습니다. 768px 미만에서는 사이드바가 오버레이 방식으로 전환되고, 핵심 지표가 세로로 재배치됩니다.",
          },
        ].map((faq, i) => (
          <div
            key={i}
            style={{
              background: T.surfaceContainerHigh, borderRadius: 8,
              padding: "16px 20px", marginBottom: 10,
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
              <div style={{
                width: 22, height: 22, borderRadius: "50%", flexShrink: 0,
                background: `${T.primary}15`, color: T.primary,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 12, fontWeight: 700,
              }}>Q</div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: T.onSurface, marginBottom: 8 }}>{faq.q}</div>
                <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.6 }}>{faq.a}</p>
              </div>
            </div>
          </div>
        ))}
      </GuideSection>

      {/* Bottom CTA */}
      <div style={{
        background: `linear-gradient(135deg, ${T.surfaceContainerLow}, ${T.secondary}08)`,
        borderRadius: 12, padding: "32px 36px",
        textAlign: "center",
      }}>
        <Sparkles size={28} color={T.secondary} style={{ marginBottom: 12 }} />
        <h3 style={{ fontFamily: font.display, fontSize: 20, fontWeight: 600, marginBottom: 8 }}>
          더 궁금한 점이 있으신가요?
        </h3>
        <p style={{ fontSize: 14, color: T.onSurfaceVariant, marginBottom: 20 }}>
          사이드바의 Support 메뉴에서 기술 지원 팀에 문의하거나, AI Insight Hub에서 실시간 도움을 받으세요.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          <BtnPrimary icon={MessageSquare}>기술 지원 문의</BtnPrimary>
          <BtnSecondary icon={Sparkles}>AI Insight Hub 열기</BtnSecondary>
        </div>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════
//   PAGE: Settings (설정)
// ═══════════════════════════════════════════════════

const ToggleSwitch = ({ on, onToggle, label, desc }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 0" }}>
    <div>
      <div style={{ fontSize: 14, fontWeight: 500, color: T.onSurface }}>{label}</div>
      {desc && <div style={{ fontSize: 12, color: T.onSurfaceVariant, marginTop: 2 }}>{desc}</div>}
    </div>
    <button
      onClick={onToggle}
      style={{
        width: 44, height: 24, borderRadius: 12, border: "none", cursor: "pointer",
        background: on ? T.primary : T.surfaceVariant,
        position: "relative", transition: "background 0.2s",
      }}
    >
      <div style={{
        width: 18, height: 18, borderRadius: "50%",
        background: on ? T.surface : T.onSurfaceVariant,
        position: "absolute", top: 3,
        left: on ? 23 : 3,
        transition: "left 0.2s",
      }} />
    </button>
  </div>
);

const SettingsGroup = ({ title, children }) => (
  <div style={{ background: T.surfaceContainerLow, borderRadius: 12, padding: "8px 24px", marginBottom: 16 }}>
    <div style={{ fontSize: 11, fontWeight: 700, color: T.onSurfaceVariant, letterSpacing: "0.08em", padding: "14px 0 4px 0" }}>{title}</div>
    {children}
  </div>
);

const SettingsSlider = ({ label, value, unit, min, max, color = T.primary }) => {
  const [val, setVal] = useState(value);
  return (
    <div style={{ padding: "14px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 14, color: T.onSurface }}>{label}</span>
        <span style={{ fontFamily: font.display, fontSize: 14, fontWeight: 600, color }}>{val}{unit}</span>
      </div>
      <input
        type="range" min={min} max={max} value={val}
        onChange={e => setVal(Number(e.target.value))}
        style={{
          width: "100%", height: 4, appearance: "none", background: T.surfaceContainerHighest,
          borderRadius: 2, outline: "none", cursor: "pointer",
          accentColor: color,
        }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 10, color: T.onSurfaceVariant }}>
        <span>{min}{unit}</span><span>{max}{unit}</span>
      </div>
    </div>
  );
};

const SettingsPage = () => {
  const [autoNegotiate, setAutoNegotiate] = useState(true);
  const [autoAdOptimize, setAutoAdOptimize] = useState(false);
  const [realtimeAlerts, setRealtimeAlerts] = useState(true);
  const [emailNotif, setEmailNotif] = useState(true);
  const [slackNotif, setSlackNotif] = useState(false);
  const [darkMode, setDarkMode] = useState(true);
  const [dataRetention, setDataRetention] = useState(true);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 780 }}>
      <div>
        <h1 style={{ fontFamily: font.display, fontSize: 32, fontWeight: 700 }}>설정</h1>
        <p style={{ fontSize: 14, color: T.onSurfaceVariant, marginTop: 4 }}>ICOM Agent 시스템 환경 및 AI 동작을 커스터마이즈합니다</p>
      </div>

      {/* AI Engine */}
      <SettingsGroup title="AI ENGINE CONFIGURATION">
        <SettingsSlider label="ROI 투자 임계값" value={5} unit="x" min={1} max={15} color={T.tertiary} />
        <SettingsSlider label="재고 경고 기준 (잔여 시간)" value={4} unit="h" min={1} max={24} color={T.error} />
        <SettingsSlider label="캠페인 HIT 판정 기준 (주문수)" value={500} unit="건" min={100} max={2000} color={T.primary} />
        <SettingsSlider label="AI 신뢰도 최소 기준" value={80} unit="%" min={50} max={99} color={T.secondary} />
      </SettingsGroup>

      {/* Automation */}
      <SettingsGroup title="AUTOMATION (자동화)">
        <ToggleSwitch on={autoNegotiate} onToggle={() => setAutoNegotiate(!autoNegotiate)}
          label="공급사 자동 협상" desc="재고 부족 감지 시 AI가 자동으로 협상 제안서를 생성합니다" />
        <ToggleSwitch on={autoAdOptimize} onToggle={() => setAutoAdOptimize(!autoAdOptimize)}
          label="광고 자동 최적화" desc="ROI 기반으로 광고 예산을 자동 재배분합니다 (승인 필요)" />
        <ToggleSwitch on={realtimeAlerts} onToggle={() => setRealtimeAlerts(!realtimeAlerts)}
          label="실시간 이상징후 감지" desc="주문 급증/급감, 가짜 참여 등 5가지 이상 유형을 모니터링합니다" />
      </SettingsGroup>

      {/* Notifications */}
      <SettingsGroup title="NOTIFICATIONS (알림)">
        <ToggleSwitch on={emailNotif} onToggle={() => setEmailNotif(!emailNotif)}
          label="이메일 알림" desc="긴급 경고 및 일간 리포트를 이메일로 전송합니다" />
        <ToggleSwitch on={slackNotif} onToggle={() => setSlackNotif(!slackNotif)}
          label="Slack 연동" desc="Slack 채널로 실시간 알림을 전송합니다" />
      </SettingsGroup>

      {/* API Connections */}
      <SettingsGroup title="API CONNECTIONS (데이터 연동)">
        {[
          { name: "Instagram Graph API", status: "연결됨", statusColor: T.tertiary, key: "META_APP_ID" },
          { name: "Naver SmartStore API", status: "연결됨", statusColor: T.tertiary, key: "SMARTSTORE_CLIENT_ID" },
          { name: "PostgreSQL Database", status: "미연결", statusColor: T.onSurfaceVariant, key: "DATABASE_URL" },
        ].map((api, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 0" }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 500, color: T.onSurface }}>{api.name}</div>
              <div style={{ fontSize: 11, color: T.onSurfaceVariant, fontFamily: "monospace" }}>{api.key}</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 12, color: api.statusColor, fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}>
                <CircleDot size={12} /> {api.status}
              </span>
              <button style={{
                padding: "5px 12px", borderRadius: 6, border: "none", cursor: "pointer",
                background: T.surfaceContainerHigh, color: T.onSurfaceVariant, fontSize: 11,
              }}>
                {api.status === "연결됨" ? "재설정" : "연결"}
              </button>
            </div>
          </div>
        ))}
      </SettingsGroup>

      {/* Appearance & Data */}
      <SettingsGroup title="SYSTEM">
        <ToggleSwitch on={darkMode} onToggle={() => setDarkMode(!darkMode)}
          label="다크 모드" desc="Neon-Glass Protocol 테마를 적용합니다" />
        <ToggleSwitch on={dataRetention} onToggle={() => setDataRetention(!dataRetention)}
          label="데이터 보존 (90일)" desc="90일 경과 데이터를 자동 아카이빙합니다" />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 0" }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, color: T.onSurface }}>데이터베이스 마이그레이션</div>
            <div style={{ fontSize: 12, color: T.onSurfaceVariant }}>SQLite → PostgreSQL 전환</div>
          </div>
          <button style={{
            padding: "6px 16px", borderRadius: 6, border: "none", cursor: "pointer",
            background: `${T.primary}15`, color: T.primary, fontSize: 12, fontWeight: 600,
          }}>마이그레이션 시작</button>
        </div>
      </SettingsGroup>

      {/* Save */}
      <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
        <BtnSecondary>변경 취소</BtnSecondary>
        <BtnPrimary icon={CheckCircle2}>설정 저장</BtnPrimary>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════
//   PAGE: Support (지원)
// ═══════════════════════════════════════════════════

const SupportPage = () => {
  const [expandedFaq, setExpandedFaq] = useState(null);

  const systemStatus = [
    { name: "FastAPI Server", status: "정상", uptime: "99.97%", color: T.tertiary },
    { name: "AI Prediction Engine", status: "정상", uptime: "99.94%", color: T.tertiary },
    { name: "Instagram Data Sync", status: "정상", uptime: "99.89%", color: T.tertiary },
    { name: "SmartStore Order Sync", status: "점검중", uptime: "98.12%", color: "#ffb74d" },
    { name: "Anomaly Detector", status: "정상", uptime: "99.99%", color: T.tertiary },
  ];

  const recentUpdates = [
    { version: "v2.0.0", date: "2024-12-15", desc: "Phase 2/3 통합: 시뮬레이터, 자율 에이전트, 텍스트 분석, 이상징후 감지" },
    { version: "v1.5.0", date: "2024-11-20", desc: "Phase 2 추가: 광고 시뮬레이터, 딜 시뮬레이터, ROI 엔진, 매칭 엔진" },
    { version: "v1.0.0", date: "2024-10-01", desc: "Phase 0/1 출시: 데이터 수집, XGBoost 수요 예측, FastAPI 서버" },
  ];

  const contactItems = [
    { icon: MessageSquare, title: "기술 지원", desc: "시스템 오류, 버그 리포트, 기능 요청", action: "티켓 생성", color: T.primary },
    { icon: BookOpen, title: "API 문서", desc: "FastAPI Swagger UI (20+ 엔드포인트)", action: "문서 열기", color: T.secondary },
    { icon: Users, title: "커뮤니티", desc: "ICOM Agent 사용자 포럼 및 베스트 프랙티스", action: "포럼 이동", color: T.tertiary },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div>
        <h1 style={{ fontFamily: font.display, fontSize: 32, fontWeight: 700 }}>고객 지원</h1>
        <p style={{ fontSize: 14, color: T.onSurfaceVariant, marginTop: 4 }}>시스템 상태 모니터링, 기술 지원, 릴리즈 노트</p>
      </div>

      {/* Contact Cards */}
      <div style={{ display: "flex", gap: 16 }}>
        {contactItems.map((c, i) => (
          <div
            key={i}
            style={{
              flex: 1, background: T.surfaceContainerLow, borderRadius: 12, padding: 24,
              display: "flex", flexDirection: "column", gap: 14,
            }}
          >
            <div style={{
              width: 44, height: 44, borderRadius: 10,
              background: `${c.color}15`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <c.icon size={22} color={c.color} />
            </div>
            <div>
              <div style={{ fontFamily: font.display, fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{c.title}</div>
              <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.5 }}>{c.desc}</p>
            </div>
            <button style={{
              marginTop: "auto", padding: "8px 16px", borderRadius: 6, border: "none", cursor: "pointer",
              background: `${c.color}15`, color: c.color, fontSize: 12, fontWeight: 600,
              display: "flex", alignItems: "center", gap: 6,
            }}>
              {c.action} <ArrowRight size={14} />
            </button>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 20 }}>
        {/* System Status */}
        <div style={{ flex: 1 }}>
          <div style={{ background: T.surfaceContainerLow, borderRadius: 12, padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <h3 style={{ fontFamily: font.display, fontSize: 18, fontWeight: 600 }}>시스템 상태</h3>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: T.tertiary }}>
                <PulseDot color={T.tertiary} /> 실시간 모니터링
              </div>
            </div>
            {systemStatus.map((s, i) => (
              <div
                key={i}
                style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "14px 0",
                  borderBottom: i < systemStatus.length - 1 ? `1px solid ${T.surfaceVariant}15` : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{
                    width: 8, height: 8, borderRadius: "50%", background: s.color,
                    boxShadow: `0 0 6px ${s.color}60`,
                  }} />
                  <span style={{ fontSize: 14, color: T.onSurface }}>{s.name}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <span style={{ fontSize: 12, color: T.onSurfaceVariant }}>Uptime: {s.uptime}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: s.color }}>{s.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Release Notes */}
        <div style={{ flex: 1 }}>
          <div style={{ background: T.surfaceContainerLow, borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontFamily: font.display, fontSize: 18, fontWeight: 600, marginBottom: 20 }}>릴리즈 노트</h3>
            {recentUpdates.map((u, i) => (
              <div
                key={i}
                style={{
                  padding: "16px 0",
                  borderBottom: i < recentUpdates.length - 1 ? `1px solid ${T.surfaceVariant}15` : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <span style={{
                    fontSize: 12, fontWeight: 700, color: i === 0 ? T.primary : T.onSurfaceVariant,
                    background: i === 0 ? `${T.primary}15` : T.surfaceContainerHigh,
                    padding: "2px 8px", borderRadius: 4, fontFamily: "monospace",
                  }}>{u.version}</span>
                  <span style={{ fontSize: 11, color: T.onSurfaceVariant }}>{u.date}</span>
                  {i === 0 && <Badge color={T.tertiary}>LATEST</Badge>}
                </div>
                <p style={{ fontSize: 13, color: T.onSurfaceVariant, lineHeight: 1.5 }}>{u.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tech Specs */}
      <div style={{ background: T.surfaceContainerLow, borderRadius: 12, padding: 24 }}>
        <h3 style={{ fontFamily: font.display, fontSize: 18, fontWeight: 600, marginBottom: 20 }}>기술 사양</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          {[
            { label: "Backend", value: "FastAPI v2.0", sub: "Python 3.10+" },
            { label: "ML Model", value: "XGBoost", sub: "18 Features" },
            { label: "Agent", value: "LangGraph", sub: "StateGraph" },
            { label: "Database", value: "SQLAlchemy", sub: "SQLite / PostgreSQL" },
            { label: "Frontend", value: "React SPA", sub: "Recharts + Lucide" },
            { label: "API Endpoints", value: "20+", sub: "REST API" },
            { label: "Test Coverage", value: "132/132", sub: "100% Pass" },
            { label: "Total Code", value: "8,547", sub: "Lines of Python" },
          ].map((spec, i) => (
            <div key={i} style={{ background: T.surfaceContainerHigh, borderRadius: 8, padding: 16, textAlign: "center" }}>
              <div style={{ fontSize: 11, color: T.onSurfaceVariant, marginBottom: 4 }}>{spec.label}</div>
              <div style={{ fontFamily: font.display, fontSize: 18, fontWeight: 700, color: T.primary }}>{spec.value}</div>
              <div style={{ fontSize: 11, color: T.onSurfaceVariant, marginTop: 2 }}>{spec.sub}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Contact */}
      <div style={{
        background: `linear-gradient(135deg, ${T.surfaceContainerLow}, ${T.primary}06)`,
        borderRadius: 12, padding: "28px 32px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div>
          <h3 style={{ fontFamily: font.display, fontSize: 18, fontWeight: 600, marginBottom: 6 }}>
            즉각적인 도움이 필요하신가요?
          </h3>
          <p style={{ fontSize: 13, color: T.onSurfaceVariant }}>
            AI Insight Hub를 열어 실시간 분석을 확인하거나, User Guide에서 기능별 사용법을 알아보세요.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <BtnSecondary icon={BookOpen}>User Guide</BtnSecondary>
          <BtnPrimary icon={Sparkles}>AI Insight Hub</BtnPrimary>
        </div>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════
//   LAYOUT: Sidebar + TopBar + Main
// ═══════════════════════════════════════════════════

const navItems = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "campaigns", label: "Campaigns", icon: Megaphone },
  { key: "influencers", label: "Influencers", icon: Users },
  { key: "inventory", label: "Inventory", icon: Package },
  { key: "reports", label: "Reports", icon: FileText },
  { key: "guide", label: "User Guide", icon: BookOpen },
];

const pages = {
  dashboard: DashboardPage,
  campaigns: CampaignsPage,
  influencers: InfluencersPage,
  inventory: InventoryPage,
  reports: ReportsPage,
  guide: UserGuidePage,
  settings: SettingsPage,
  support: SupportPage,
};

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [isMobile, setIsMobile] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [hubOpen, setHubOpen] = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const PageComponent = pages[activePage];

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: T.surface }}>
      <GlobalStyles />
      <AIInsightHub isOpen={hubOpen} onClose={() => setHubOpen(false)} />

      {/* ── Sidebar ── */}
      {(!isMobile || sidebarOpen) && (
        <nav
          style={{
            width: isMobile ? 240 : 200,
            background: T.surfaceDim,
            padding: "24px 0",
            display: "flex",
            flexDirection: "column",
            position: isMobile ? "fixed" : "relative",
            top: 0,
            left: 0,
            height: "100vh",
            zIndex: 100,
            transition: "all 0.3s",
          }}
        >
          {/* Logo */}
          <div style={{ padding: "0 20px", marginBottom: 32 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8,
                background: `linear-gradient(135deg, ${T.primary}40, ${T.secondary}40)`,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Zap size={18} color={T.primary} />
              </div>
              <div>
                <div style={{ fontFamily: font.display, fontSize: 16, fontWeight: 700, color: T.primary, letterSpacing: "0.05em" }}>
                  ICOM AGENT
                </div>
                <div style={{ fontSize: 9, color: T.onSurfaceVariant, letterSpacing: "0.1em", fontFamily: "monospace" }}>
                  Protocol v1.0.4
                </div>
              </div>
            </div>
          </div>

          {/* Nav Items */}
          <div style={{ flex: 1, padding: "0 12px" }}>
            {navItems.map(item => {
              const active = activePage === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => { setActivePage(item.key); if (isMobile) setSidebarOpen(false); }}
                  style={{
                    display: "flex", alignItems: "center", gap: 12,
                    width: "100%", padding: "10px 12px", marginBottom: 4,
                    borderRadius: 8, border: "none", cursor: "pointer",
                    background: active ? `${T.primary}15` : "transparent",
                    color: active ? T.primary : T.onSurfaceVariant,
                    fontFamily: font.body, fontSize: 13, fontWeight: active ? 600 : 400,
                    transition: "all 0.15s",
                    textAlign: "left",
                  }}
                  onMouseEnter={e => { if (!active) e.target.style.background = `${T.surfaceContainerHigh}`; }}
                  onMouseLeave={e => { if (!active) e.target.style.background = "transparent"; }}
                >
                  <item.icon size={18} />
                  {item.label}
                </button>
              );
            })}
          </div>

          {/* AI Insight Hub Button */}
          <div style={{ padding: "0 16px", marginBottom: 20 }}>
            <button
              onClick={() => setHubOpen(true)}
              style={{
                width: "100%", padding: "10px", borderRadius: 8, border: "none", cursor: "pointer",
                background: `linear-gradient(135deg, ${T.secondary}40, ${T.primary}20)`,
                color: T.primary, fontSize: 13, fontWeight: 600,
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                boxShadow: `0 0 16px ${T.secondary}20`,
                position: "relative",
              }}
            >
              <Sparkles size={16} /> AI Insight Hub
              <span style={{
                position: "absolute", top: -4, right: -4,
                width: 18, height: 18, borderRadius: "50%",
                background: T.error, color: "#fff",
                fontSize: 10, fontWeight: 700,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>6</span>
            </button>
          </div>

          {/* Bottom */}
          <div style={{ padding: "0 16px", display: "flex", flexDirection: "column", gap: 4 }}>
            {[
              { key: "settings", label: "Settings", icon: Settings },
              { key: "support", label: "Support", icon: Shield },
            ].map(item => {
              const active = activePage === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => { setActivePage(item.key); if (isMobile) setSidebarOpen(false); }}
                  style={{
                    background: active ? `${T.primary}15` : "none",
                    border: "none",
                    color: active ? T.primary : T.onSurfaceVariant,
                    fontSize: 13, fontWeight: active ? 600 : 400,
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "8px 8px", borderRadius: 8, cursor: "pointer",
                    width: "100%", textAlign: "left",
                    transition: "all 0.15s",
                  }}
                >
                  <item.icon size={16} /> {item.label}
                </button>
              );
            })}
          </div>
        </nav>
      )}

      {/* Mobile overlay */}
      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{ position: "fixed", inset: 0, background: "#00000060", zIndex: 99 }}
        />
      )}

      {/* ── Main Content ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Top Bar */}
        <header style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "16px 28px",
          background: T.surfaceDim,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            {isMobile && (
              <button
                onClick={() => setSidebarOpen(true)}
                style={{ background: "none", border: "none", color: T.onSurface, cursor: "pointer" }}
              >
                <LayoutDashboard size={20} />
              </button>
            )}
            <SearchBar />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <button style={{ background: "none", border: "none", color: T.onSurfaceVariant, cursor: "pointer", position: "relative" }}>
              <Bell size={20} />
              <span style={{ position: "absolute", top: -2, right: -2, width: 8, height: 8, borderRadius: "50%", background: T.error }} />
            </button>
            <button style={{ background: "none", border: "none", color: T.onSurfaceVariant, cursor: "pointer" }}>
              <Settings size={20} />
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginLeft: 8 }}>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.primary }}>ICOM Agent Admin</div>
                <div style={{ fontSize: 10, color: T.onSurfaceVariant }}>Verified Agent</div>
              </div>
              <div style={{
                width: 36, height: 36, borderRadius: "50%",
                background: `linear-gradient(135deg, ${T.primary}40, ${T.secondary}40)`,
                display: "flex", alignItems: "center", justifyContent: "center",
                border: `2px solid ${T.primary}40`,
              }}>
                <Bot size={18} color={T.primary} />
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main style={{ flex: 1, padding: "28px", overflowY: "auto" }}>
          <PageComponent />
        </main>
      </div>
    </div>
  );
}
