"use client";

import { useState, useEffect, useRef } from "react";

interface GenerationProgressCardProps {
    type: "video" | "long_video" | "image";
    duration?: string | number;
    progress?: number; // 0-100 real progress from parent (optional, will simulate if not provided)
    status: "generating" | "complete" | "error";
}

export function GenerationProgressCard({
    type,
    duration,
    progress: externalProgress,
    status,
}: GenerationProgressCardProps) {
    const icon = type === "image" ? "🖼️" : "🎬";
    const label = type === "image" ? "Görsel" : "Video";
    const durationText = duration ? `${duration}s` : "";

    // Simulated progress — eases towards 90% over estimated time
    const [simulatedProgress, setSimulatedProgress] = useState(0);
    const startTimeRef = useRef(Date.now());
    const intervalRef = useRef<NodeJS.Timeout | null>(null);

    // Estimated generation times (ms)
    const estimatedTime = type === "image" ? 18000 : type === "long_video" ? 180000 : 120000;

    useEffect(() => {
        if (status !== "generating") {
            if (status === "complete") setSimulatedProgress(100);
            return;
        }

        startTimeRef.current = Date.now();
        setSimulatedProgress(0);

        intervalRef.current = setInterval(() => {
            const elapsed = Date.now() - startTimeRef.current;
            const ratio = elapsed / estimatedTime;

            // Ease-out curve: fast start, slows down, never reaches 95% until complete
            // Formula: progress = 90 * (1 - e^(-3 * ratio))
            const simulated = Math.min(92, Math.floor(90 * (1 - Math.exp(-3 * ratio))));
            setSimulatedProgress(simulated);
        }, 500);

        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [status, estimatedTime]);

    // Use whichever is higher — simulated provides a smooth start, real progress takes over once it catches up
    const realProgress = (externalProgress && externalProgress > 0) ? externalProgress : 0;
    const displayProgress = Math.max(realProgress, simulatedProgress);

    // Status text based on progress
    const getStatusText = () => {
        if (status === "complete") return "Hazır!";
        if (displayProgress < 15) return "Başlatılıyor...";
        if (displayProgress < 40) return "Üretiliyor";
        if (displayProgress < 70) return type === "image" ? "Detaylar ekleniyor..." : "Sahneler oluşturuluyor...";
        if (displayProgress < 90) return type === "image" ? "Son rötuşlar..." : "Render ediliyor...";
        return "Neredeyse hazır...";
    };

    return (
        <div className="mt-3 mb-2 rounded-2xl overflow-hidden" style={{ maxWidth: "360px" }}>
            <div
                className="relative p-5"
                style={{
                    background: type === "image"
                        ? "linear-gradient(135deg, rgba(16,185,129,0.25) 0%, rgba(30,30,60,1) 50%, rgba(139,92,246,0.2) 100%)"
                        : "linear-gradient(135deg, rgba(99,102,241,0.25) 0%, rgba(20,20,40,1) 50%, rgba(139,92,246,0.25) 100%)",
                }}
            >
                {/* Header */}
                <div className="flex items-center gap-2.5 mb-4">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center"
                        style={{ background: "rgba(255,255,255,0.08)" }}>
                        <span className="text-lg">{icon}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-white/90 block">
                            {label} {getStatusText()}
                        </span>
                        {durationText && (
                            <span className="text-[11px] text-white/35">{durationText}</span>
                        )}
                    </div>
                </div>

                {/* Progress area */}
                {status === "generating" && (
                    <div className="flex flex-col items-center gap-3">
                        {/* Big percentage */}
                        <div className="text-4xl font-light text-white/90 tabular-nums tracking-tight" style={{ fontVariantNumeric: "tabular-nums" }}>
                            {displayProgress}<span className="text-xl text-white/40">%</span>
                        </div>

                        {/* Progress bar */}
                        <div className="w-full h-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.08)" }}>
                            <div
                                className="h-full rounded-full transition-all duration-700 ease-out"
                                style={{
                                    width: `${displayProgress}%`,
                                    background: type === "image"
                                        ? "linear-gradient(90deg, #10b981, #34d399)"
                                        : "linear-gradient(90deg, #6366f1, #a78bfa)",
                                }}
                            />
                        </div>
                    </div>
                )}

                {/* Complete state */}
                {status === "complete" && (
                    <div className="flex items-center justify-center gap-2 py-2">
                        <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center">
                            <span className="text-emerald-400 text-sm">✓</span>
                        </div>
                        <span className="text-sm text-emerald-400 font-medium">Tamamlandı!</span>
                    </div>
                )}

                {/* Error state */}
                {status === "error" && (
                    <div className="flex items-center justify-center gap-2 py-2">
                        <span className="text-sm text-red-400">⚠️ Üretim başarısız</span>
                    </div>
                )}
            </div>
        </div>
    );
}
