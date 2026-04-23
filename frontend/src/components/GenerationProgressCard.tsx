"use client";

import { useState, useEffect, useRef } from "react";

interface ProductionLog {
    id: string;
    message: string;
    timestamp: Date;
}

interface GenerationProgressCardProps {
    type: string;
    duration?: string | number;
    progress?: number;
    status: "generating" | "complete" | "error";
    productionLogs?: ProductionLog[];
    completedScenes?: number;
    totalScenes?: number;
    onCancel?: () => void;
}

export function GenerationProgressCard({
    type,
    progress: externalProgress,
    status,
    productionLogs = [],
    completedScenes = 0,
    totalScenes = 0,
    onCancel,
}: GenerationProgressCardProps) {
    const icon = type === "image" ? "🖼️" : type === "audio" ? "🎵" : "🎬";
    const label = type === "image"
        ? "Görsel Üretiliyor"
        : type === "audio"
            ? "Ses Üretiliyor"
            : type === "long_video"
                ? "Uzun Video Üretiliyor"
                : "Video Üretiliyor";

    const [simulatedProgress, setSimulatedProgress] = useState(0);
    const startTimeRef = useRef(0);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const logEndRef = useRef<HTMLDivElement>(null);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    const estimatedTime = type === "image" ? 18000 : type === "long_video" ? 180000 : 120000;

    useEffect(() => {
        if (status !== "generating") return;
        startTimeRef.current = Date.now();
        // Reset + simulate via interval only (no synchronous setState in effect body)
        intervalRef.current = setInterval(() => {
            const elapsed = Date.now() - startTimeRef.current;
            if (elapsed < 100) {
                setSimulatedProgress(0); // Reset on first tick
                return;
            }
            const ratio = elapsed / estimatedTime;
            const simulated = Math.min(92, Math.floor(90 * (1 - Math.exp(-3 * ratio))));
            setSimulatedProgress(simulated);
        }, 500);
        return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
    }, [status, estimatedTime]);

    // Elapsed timer
    useEffect(() => {
        if (status !== "generating") {
            if (timerRef.current) clearInterval(timerRef.current);
            return;
        }
        const start = Date.now();
        timerRef.current = setInterval(() => {
            setElapsedSeconds(Math.floor((Date.now() - start) / 1000));
        }, 1000);
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [status]);

    // Auto-scroll mini log
    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [productionLogs.length]);

    const realProgress = (externalProgress && externalProgress > 0) ? externalProgress : 0;
    const displayProgress = Math.max(realProgress, simulatedProgress);

    const hasScenes = type === "long_video" && totalScenes > 0;

    const elapsedMin = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
    const elapsedSec = String(elapsedSeconds % 60).padStart(2, "0");

    // Circular progress
    const radius = 38;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (displayProgress / 100) * circumference;

    return (
        <div
            className="mt-3 mb-2 rounded-2xl overflow-hidden"
            style={{
                maxWidth: "440px",
                width: "100%",
                ...(status === "generating" ? {
                    boxShadow: "0 0 20px rgba(16,185,129,0.15), 0 0 40px rgba(99,102,241,0.08)",
                    animation: "card-glow 3s ease-in-out infinite",
                } : {}),
            }}
        >
            <div
                className="relative p-4"
                style={{
                    background: "linear-gradient(135deg, rgba(16,185,129,0.15) 0%, rgba(20,20,40,1) 50%, rgba(99,102,241,0.15) 100%)",
                    border: "1px solid rgba(255,255,255,0.06)",
                }}
            >
                {/* Header */}
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">{icon}</span>
                    <span className="text-sm font-medium text-white/90">{label}</span>
                    {status === "generating" && (
                        <>
                            <div className="flex items-center gap-1 ml-1">
                                {[0, 1, 2].map(i => (
                                    <div
                                        key={i}
                                        className="w-1 h-1 rounded-full"
                                        style={{
                                            background: "#10b981",
                                            animation: `prod-dot 1.4s ease-in-out ${i * 0.2}s infinite`,
                                        }}
                                    />
                                ))}
                            </div>
                            <span
                                className="ml-auto text-[11px] font-mono tabular-nums"
                                style={{ color: "rgba(255,255,255,0.35)" }}
                            >
                                {elapsedMin}:{elapsedSec}
                            </span>
                            {onCancel && (
                                <button
                                    onClick={onCancel}
                                    className="ml-2 flex items-center justify-center rounded-full transition-all duration-200"
                                    style={{
                                        width: "24px",
                                        height: "24px",
                                        background: "rgba(239,68,68,0.15)",
                                        border: "1px solid rgba(239,68,68,0.3)",
                                        color: "rgba(239,68,68,0.7)",
                                        fontSize: "12px",
                                        cursor: "pointer",
                                    }}
                                    onMouseEnter={e => {
                                        e.currentTarget.style.background = "rgba(239,68,68,0.3)";
                                        e.currentTarget.style.color = "#ef4444";
                                        e.currentTarget.style.borderColor = "rgba(239,68,68,0.6)";
                                    }}
                                    onMouseLeave={e => {
                                        e.currentTarget.style.background = "rgba(239,68,68,0.15)";
                                        e.currentTarget.style.color = "rgba(239,68,68,0.7)";
                                        e.currentTarget.style.borderColor = "rgba(239,68,68,0.3)";
                                    }}
                                    title="İptal Et"
                                >
                                    ✕
                                </button>
                            )}
                        </>
                    )}
                </div>

                {/* Main content — two columns */}
                {status === "generating" && (
                    <div className="flex gap-3">
                        {/* Left: Mini log + scene status */}
                        <div className="flex-1 min-w-0">
                            {/* Scene indicators (only for long_video) */}
                            {hasScenes && (
                                <div className="flex gap-1.5 mb-2 flex-wrap">
                                    {Array.from({ length: totalScenes }, (_, i) => {
                                        const sceneNum = i + 1;
                                        const isDone = sceneNum <= completedScenes;
                                        const isActive = sceneNum === completedScenes + 1;
                                        return (
                                            <div
                                                key={i}
                                                className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
                                                style={{
                                                    background: isDone
                                                        ? "rgba(16,185,129,0.2)"
                                                        : isActive
                                                            ? "rgba(99,102,241,0.2)"
                                                            : "rgba(255,255,255,0.05)",
                                                    color: isDone
                                                        ? "#34d399"
                                                        : isActive
                                                            ? "#C9A84C"
                                                            : "rgba(255,255,255,0.3)",
                                                    border: isActive
                                                        ? "1px solid rgba(99,102,241,0.3)"
                                                        : "1px solid transparent",
                                                }}
                                            >
                                                {isDone ? "✓" : isActive ? "⏳" : "○"} S{sceneNum}
                                            </div>
                                        );
                                    })}
                                </div>
                            )}

                            {/* Mini log area */}
                            <div
                                className="overflow-y-auto pr-1"
                                style={{
                                    maxHeight: "80px",
                                    scrollbarWidth: "thin",
                                    scrollbarColor: "rgba(255,255,255,0.1) transparent",
                                }}
                            >
                                {productionLogs.length > 0 ? (
                                    productionLogs.map((log) => (
                                        <div
                                            key={log.id}
                                            className="text-[11px] leading-relaxed mb-1 last:mb-0"
                                            style={{
                                                color: "rgba(255,255,255,0.55)",
                                                animation: "fade-in 0.3s ease-out",
                                            }}
                                        >
                                            {log.message}
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-[11px]" style={{ color: "rgba(255,255,255,0.3)" }}>
                                        Üretim başlatıldı, ilerleme bekleniyor...
                                    </div>
                                )}
                                <div ref={logEndRef} />
                            </div>
                        </div>

                        {/* Right: Circular progress */}
                        <div className="flex flex-col items-center justify-center shrink-0" style={{ width: "90px" }}>
                            <div className="relative">
                                <svg width="86" height="86" viewBox="0 0 86 86">
                                    {/* Background circle */}
                                    <circle
                                        cx="43" cy="43" r={radius}
                                        fill="none"
                                        stroke="rgba(255,255,255,0.06)"
                                        strokeWidth="4"
                                    />
                                    {/* Progress circle */}
                                    <circle
                                        cx="43" cy="43" r={radius}
                                        fill="none"
                                        stroke="url(#progressGradient)"
                                        strokeWidth="4"
                                        strokeLinecap="round"
                                        strokeDasharray={circumference}
                                        strokeDashoffset={strokeDashoffset}
                                        transform="rotate(-90 43 43)"
                                        style={{ transition: "stroke-dashoffset 0.7s ease-out" }}
                                    />
                                    <defs>
                                        <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                            <stop offset="0%" stopColor="#10b981" />
                                            <stop offset="100%" stopColor="#6366f1" />
                                        </linearGradient>
                                    </defs>
                                </svg>
                                {/* Center text */}
                                <div className="absolute inset-0 flex flex-col items-center justify-center">
                                    <span className="text-xl font-light text-white/90 tabular-nums">
                                        {displayProgress}<span className="text-xs text-white/40">%</span>
                                    </span>
                                    {hasScenes && (
                                        <span className="text-[9px] text-white/40 mt-0.5">
                                            {completedScenes}/{totalScenes} sahne
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Complete state */}
                {status === "complete" && (
                    <div className="flex items-center justify-center gap-2 py-2">
                        <div className="w-6 h-6 rounded-full bg-[#C9A84C]/20 flex items-center justify-center">
                            <span className="text-[#C9A84C] text-sm">✓</span>
                        </div>
                        <span className="text-sm text-[#C9A84C] font-medium">Tamamlandı!</span>
                    </div>
                )}

                {/* Error state */}
                {status === "error" && (
                    <div className="flex items-center justify-center gap-2 py-2">
                        <span className="text-sm text-red-400">⚠️ Üretim başarısız</span>
                    </div>
                )}
            </div>

            {/* Animations */}
            <style>{`
                @keyframes prod-dot {
                    0%, 60%, 100% { opacity: 0.3; }
                    30% { opacity: 1; }
                }
                @keyframes fade-in {
                    from { opacity: 0; transform: translateY(4px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes card-glow {
                    0%, 100% { box-shadow: 0 0 15px rgba(16,185,129,0.12), 0 0 30px rgba(99,102,241,0.06); }
                    50% { box-shadow: 0 0 25px rgba(16,185,129,0.25), 0 0 50px rgba(99,102,241,0.15); }
                }
            `}</style>
        </div>
    );
}
