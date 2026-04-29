"use client";

import { useState, useRef } from "react";
import {
    X,
    Upload,
    Loader2,
    Grid3x3,
    Film,
    Zap,
    Download,
    Check,
    RefreshCw,
    Sparkles,
    PenLine,
    ArrowRight,
    MessageSquarePlus,
} from "lucide-react";
import { generateGrid as apiGenerateGrid } from "@/lib/api";

interface GridGeneratorModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSendToChat?: (imageUrl: string) => void;
}

type ModeTop = "angles" | "storyboard";
type Aspect = "16:9" | "9:16" | "1:1";
type PromptMode = "auto" | "custom";
type Scale = 1 | 2 | 4;

export function GridGeneratorModal({ isOpen, onClose, onSendToChat }: GridGeneratorModalProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Core states
    const [image, setImage] = useState<string | null>(null);
    const [gridImage, setGridImage] = useState<string | null>(null);
    const [aspect, setAspect] = useState<Aspect>("16:9");
    const [topMode, setTopMode] = useState<ModeTop>("angles");
    const [promptMode, setPromptMode] = useState<PromptMode>("auto");
    const [customPrompt, setCustomPrompt] = useState("");
    const [scale, setScale] = useState<Scale>(2);

    // UI states
    const [loading, setLoading] = useState(false);
    const [loadingProgress, setLoadingProgress] = useState(0);
    const [loadingStatus, setLoadingStatus] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [gridGenerated, setGridGenerated] = useState(false);
    const [selected, setSelected] = useState<number[]>([]);
    const [isDragging, setIsDragging] = useState(false);

    // Extraction states
    const [extracting, setExtracting] = useState(false);
    const [extractedImages, setExtractedImages] = useState<{ index: number; url: string; status: "extracting" | "ready" }[]>([]);

    if (!isOpen) return null;

    // ============================================
    // FILE HANDLING
    // ============================================
    const handleFile = (file: File) => {
        if (!file.type.startsWith("image/")) {
            setError("Lütfen geçerli bir görsel dosyası yükleyin");
            return;
        }
        const reader = new FileReader();
        reader.onload = () => setImage(reader.result as string);
        reader.readAsDataURL(file);
        resetGridState();
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    };

    // ============================================
    // GRID SELECTION
    // ============================================
    const toggleCell = (index: number) => {
        if (extractedImages.some(img => img.index === index)) return;
        setSelected((prev) =>
            prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
        );
    };

    const selectAll = () => {
        if (selected.length === 9) {
            setSelected([]);
        } else {
            const notExtracted = Array.from({ length: 9 }, (_, i) => i)
                .filter(i => !extractedImages.some(img => img.index === i && img.status === "ready"));
            setSelected(notExtracted);
        }
    };

    // ============================================
    // PROGRESS STAGES
    // ============================================
    const PROGRESS_STAGES = [
        { percent: 5, message: "GÖRSEL ANALİZ EDİLİYOR" },
        { percent: 15, message: "SAHNE İNCELENİYOR" },
        { percent: 25, message: "ÖZELLİKLER TESPİT EDİLİYOR" },
        { percent: 40, message: "VARYASYONLAR ÜRETİLİYOR" },
        { percent: 55, message: "GRID OLUŞTURULUYOR" },
        { percent: 70, message: "DETAYLAR İYİLEŞTİRİLİYOR" },
        { percent: 85, message: "SON DOKUNUŞLAR" },
        { percent: 95, message: "NEREDEYSE BITTI..." },
    ];

    const getStatusMessage = (progress: number): string => {
        for (let i = PROGRESS_STAGES.length - 1; i >= 0; i--) {
            if (progress >= PROGRESS_STAGES[i].percent) {
                return PROGRESS_STAGES[i].message;
            }
        }
        return "BAŞLIYOR...";
    };

    // ============================================
    // PROMPT BUILDER
    // ============================================
    const buildPrompt = () => {
        if (promptMode === "custom" && customPrompt.trim()) {
            return `Generate a 3x3 grid with 9 COMPLETELY DIFFERENT panels. NO TEXT, NO LABELS, NO BORDERS. ${customPrompt}`;
        }

        const baseInstructions = `Generate a 3x3 grid with 9 COMPLETELY DIFFERENT panels. NO TEXT, NO LABELS, NO BORDERS.`;

        switch (topMode) {
            case "angles":
                return `${baseInstructions}
Create 9 different camera angles of the same subject:
Wide shot, medium shot, close-up, extreme close-up, low angle, high angle, dutch angle, profile, three-quarter view.
Cinematic, photorealistic, professional photography.`;

            case "storyboard":
                return `${baseInstructions}
Create 9 sequential story moments showing action progression.
Cinematic storyboard quality, consistent character.`;

            default:
                return baseInstructions;
        }
    };

    // ============================================
    // GENERATE GRID
    // ============================================
    const generateGrid = async () => {
        if (!image) return;

        setLoading(true);
        setLoadingProgress(0);
        setLoadingStatus("BAŞLIYOR...");
        setError(null);
        setSelected([]);
        setExtractedImages([]);

        let progressInterval: NodeJS.Timeout | null = null;

        const startProgress = () => {
            progressInterval = setInterval(() => {
                setLoadingProgress((prev) => {
                    if (prev < 95) {
                        const newProgress = prev + 1;
                        setLoadingStatus(getStatusMessage(newProgress));
                        return newProgress;
                    }
                    return prev;
                });
            }, 600);
        };

        startProgress();

        try {
            const gridPrompt = buildPrompt();

            const data = await apiGenerateGrid({
                image,
                aspect,
                mode: topMode,
                prompt: gridPrompt,
            });

            if (data.success && data.gridImage) {
                if (progressInterval) clearInterval(progressInterval);
                setLoadingProgress(90);
                setLoadingStatus("GÖRSEL YÜKLENİYOR...");

                // Görseli tarayıcıda preload et — yüklenene kadar loading devam eder
                await new Promise<void>((resolve) => {
                    const img = new window.Image();
                    img.onload = () => resolve();
                    img.onerror = () => resolve(); // Hata olsa da devam et
                    img.src = data.gridImage!;
                });

                setLoadingProgress(100);
                setLoadingStatus("TAMAMLANDI!");
                setGridImage(data.gridImage);
                setGridGenerated(true);
            } else {
                throw new Error("Görsel oluşturma başarısız oldu");
            }
        } catch (err) {
            console.error("Grid generation error:", err);
            setError(err instanceof Error ? err.message : "Bir hata oluştu");
        } finally {
            if (progressInterval) clearInterval(progressInterval);
            setLoading(false);
            setLoadingProgress(0);
        }
    };

    // ============================================
    // CROP GRID CELL
    // ============================================
    const cropGridCell = async (cellIndex: number): Promise<string> => {
        if (!gridImage) {
            throw new Error("No grid image");
        }

        const loadImage = (src: string, useCors: boolean): Promise<HTMLImageElement> => {
            return new Promise((resolve, reject) => {
                const img = new window.Image();
                if (useCors) img.crossOrigin = "anonymous";

                const timeout = setTimeout(() => reject(new Error("Timeout")), 10000);
                img.onload = () => { clearTimeout(timeout); resolve(img); };
                img.onerror = () => { clearTimeout(timeout); reject(new Error("Load failed")); };
                img.src = src;
            });
        };

        const cropFromImage = (img: HTMLImageElement): string => {
            const canvas = document.createElement("canvas");
            const ctx = canvas.getContext("2d");
            if (!ctx) throw new Error("Canvas context error");

            const cellWidth = img.width / 3;
            const cellHeight = img.height / 3;
            const col = cellIndex % 3;
            const row = Math.floor(cellIndex / 3);

            canvas.width = cellWidth * scale;
            canvas.height = cellHeight * scale;
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = "high";
            ctx.drawImage(img, col * cellWidth, row * cellHeight, cellWidth, cellHeight, 0, 0, cellWidth * scale, cellHeight * scale);
            return canvas.toDataURL("image/png");
        };

        // Data URL ise direkt kullan (en hızlı)
        if (gridImage.startsWith("data:")) {
            const img = await loadImage(gridImage, false);
            return cropFromImage(img);
        }

        // Strateji 1: Browser cache'ten Image + CORS (en hızlı — görsel zaten yüklü)
        try {
            const img = await loadImage(gridImage, true);
            return cropFromImage(img);
        } catch {
            console.warn("Direct CORS load failed, trying fetch...");
        }

        // Strateji 2: fetch → blob → data URL (CORS sorununu aşar)
        try {
            const response = await fetch(gridImage);
            if (response.ok) {
                const blob = await response.blob();
                const dataUrl = await new Promise<string>((resolve) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result as string);
                    reader.readAsDataURL(blob);
                });
                const img = await loadImage(dataUrl, false);
                return cropFromImage(img);
            }
        } catch {
            console.warn("Fetch strategy failed, trying no-CORS...");
        }

        // Strateji 3: CORS olmadan + backend proxy fallback
        try {
            const img = await loadImage(gridImage, false);
            return cropFromImage(img);
        } catch {
            // Son çare: Backend proxy
            const proxyUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/proxy-image?url=${encodeURIComponent(gridImage)}`;
            const proxyResponse = await fetch(proxyUrl);
            if (proxyResponse.ok) {
                const blob = await proxyResponse.blob();
                const dataUrl = await new Promise<string>((resolve) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result as string);
                    reader.readAsDataURL(blob);
                });
                const img = await loadImage(dataUrl, false);
                return cropFromImage(img);
            }
            throw new Error("Görsel çıkarma başarısız — lütfen tekrar deneyin");
        }
    };

    // ============================================
    // EXTRACT
    // ============================================
    const handleExtract = async () => {
        if (selected.length === 0) return;

        setExtracting(true);
        setError(null);

        const cellsToExtract = [...selected];
        const initialImages = cellsToExtract.map((index) => ({
            index,
            url: "",
            status: "extracting" as const,
        }));
        setExtractedImages((prev) => [...prev, ...initialImages]);

        try {
            for (let i = 0; i < cellsToExtract.length; i++) {
                const cellIndex = cellsToExtract[i];
                const croppedImage = await cropGridCell(cellIndex);

                if (scale > 1) {
                    await new Promise((resolve) => setTimeout(resolve, 300));
                }

                setExtractedImages((prev) =>
                    prev.map((img) =>
                        img.index === cellIndex
                            ? { index: img.index, url: croppedImage, status: "ready" as const }
                            : img
                    )
                );
            }
            setSelected([]);
        } catch (err) {
            console.error("Extract error:", err);
            setError(err instanceof Error ? err.message : "Çıkarma başarısız oldu");
            // Hata durumunda stuck "extracting" öğeleri temizle
            setExtractedImages((prev) =>
                prev.filter((img) => img.status !== "extracting")
            );
        } finally {
            setExtracting(false);
        }
    };

    // ============================================
    // DOWNLOAD
    // ============================================
    const downloadSingleImage = async (img: { index: number; url: string }) => {
        const link = document.createElement("a");
        link.href = img.url;
        link.download = `panel_${img.index + 1}_${scale}x.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const downloadAllExtracted = async () => {
        const readyImages = extractedImages.filter((img) => img.status === "ready");
        for (const img of readyImages) {
            await downloadSingleImage(img);
            await new Promise((resolve) => setTimeout(resolve, 300));
        }
    };

    const downloadGrid = async () => {
        if (!gridImage) return;

        try {
            let blobUrl: string;

            if (gridImage.startsWith("data:")) {
                blobUrl = gridImage;
            } else {
                // External URL — fetch as blob for proper download
                const response = await fetch(gridImage);
                const blob = await response.blob();
                blobUrl = URL.createObjectURL(blob);
            }

            const link = document.createElement("a");
            link.href = blobUrl;
            link.download = `grid_${topMode}_${Date.now()}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            // Clean up blob URL if we created one
            if (!gridImage.startsWith("data:")) {
                URL.revokeObjectURL(blobUrl);
            }
        } catch (error) {
            console.error("Download failed:", error);
            // Fallback: open in new tab
            window.open(gridImage, "_blank");
        }
    };

    // ============================================
    // UTILITIES
    // ============================================
    const resetGridState = () => {
        setGridGenerated(false);
        setGridImage(null);
        setSelected([]);
        setExtractedImages([]);
        setError(null);
    };

    const resetAll = () => {
        setImage(null);
        resetGridState();
    };

    const handleClose = () => {
        resetAll();
        setAspect("16:9");
        setTopMode("angles");
        setPromptMode("auto");
        setCustomPrompt("");
        setScale(2);
        setLoading(false);
        setLoadingProgress(0);
        setLoadingStatus("");
        onClose();
    };

    // ============================================
    // RENDER
    // ============================================
    return (
        <div
            className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto"
            style={{ backgroundColor: "rgba(0,0,0,0.95)" }}
            onClick={handleClose}
        >
            <div
                className="relative w-full max-w-5xl my-8 mx-4"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Close Button - Fixed */}
                <button
                    onClick={handleClose}
                    className="fixed top-4 right-4 z-50 p-2 rounded-full bg-black/50 hover:bg-white/10 transition-colors"
                >
                    <X size={24} className="text-white" />
                </button>

                {/* Main Content - Vertical Stack */}
                <div className="flex flex-col items-center gap-8 py-8">
                    {/* Header */}
                    <div className="flex flex-col items-center gap-4">
                        <div className="flex flex-col items-center gap-0">
                            <h1 className="text-3xl font-bold tracking-wide">
                                <span className="text-white" style={{ fontFamily: "var(--font-cormorant, 'Cormorant Garamond', serif)" }}>Nero Panthero</span>
                                <span className="text-[#C9A84C]">.</span>
                            </h1>
                            <span className="text-sm font-light tracking-[0.2em] text-gray-500">Grids</span>
                        </div>

                        {/* Mode Selector */}
                        <div className="flex bg-[#111] border border-[#222] rounded-xl p-1 gap-1">
                            {[
                                { key: "angles", label: "AÇILAR", icon: Film },
                                { key: "storyboard", label: "HİKAYE TAHTASI", icon: Grid3x3 },
                            ].map((item) => {
                                const active = topMode === item.key;
                                const Icon = item.icon;
                                return (
                                    <button
                                        key={item.key}
                                        onClick={() => setTopMode(item.key as ModeTop)}
                                        className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium tracking-wider transition-all ${active
                                            ? "bg-[#C9A84C] text-black"
                                            : "text-gray-500 hover:text-white hover:bg-white/5"
                                            }`}
                                    >
                                        <Icon size={16} />
                                        {item.label}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* ==================== SECTION 1: UPLOAD ==================== */}
                    <div
                        className={`relative w-full max-w-2xl rounded-xl overflow-hidden transition-all cursor-pointer ${isDragging ? "scale-[1.02] border-[#C9A84C]" : ""}`}
                        style={{
                            aspectRatio: "16/9",
                            border: isDragging ? "2px dashed #C9A84C" : "2px dashed #333",
                            background: "#0a0a0a"
                        }}
                        onClick={() => !loading && fileInputRef.current?.click()}
                        onDrop={handleDrop}
                        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                        onDragLeave={() => setIsDragging(false)}
                    >
                        {!image ? (
                            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 hover:bg-white/5 transition-colors">
                                <Upload size={48} className="text-gray-600" />
                                <span className="text-xl font-bold tracking-wider text-white">
                                    GÖRSELİ BURAYA BIRAKIN
                                </span>
                                <span className="text-sm text-gray-600">
                                    veya seçmek için tıklayın
                                </span>
                            </div>
                        ) : (
                            <>
                                <img
                                    src={image}
                                    alt="yüklenen"
                                    className="absolute inset-0 w-full h-full object-contain"
                                />
                                {loading && (
                                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-4"
                                        style={{ background: "rgba(0,0,0,0.9)" }}>
                                        <div className="relative w-20 h-20">
                                            <svg className="w-20 h-20 -rotate-90">
                                                <circle cx="40" cy="40" r="35" stroke="#333" strokeWidth="5" fill="none" />
                                                <circle
                                                    cx="40" cy="40" r="35"
                                                    stroke="#C9A84C"
                                                    strokeWidth="5"
                                                    fill="none"
                                                    strokeLinecap="round"
                                                    strokeDasharray={220}
                                                    strokeDashoffset={220 - (220 * loadingProgress) / 100}
                                                    className="transition-all duration-300"
                                                />
                                            </svg>
                                            <div className="absolute inset-0 flex items-center justify-center">
                                                <span className="text-white font-bold">{Math.round(loadingProgress)}%</span>
                                            </div>
                                        </div>
                                        <p className="text-white font-bold tracking-wider">{loadingStatus}</p>
                                    </div>
                                )}
                                {/* Change image overlay */}
                                {!loading && !gridGenerated && (
                                    <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity bg-black/50">
                                        <span className="text-white font-bold tracking-wider">GÖRSELİ DEĞİŞTİR</span>
                                    </div>
                                )}
                            </>
                        )}
                    </div>

                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        hidden
                        onChange={(e) => e.target.files && handleFile(e.target.files[0])}
                    />

                    {/* Controls - Shown after image upload, before generation */}
                    {image && !loading && (
                        <div className="flex flex-col items-center gap-5">
                            <div className="flex items-center gap-6">
                                {/* Aspect Ratio */}
                                <div className="flex flex-col items-center gap-2">
                                    <span className="text-[10px] tracking-[0.3em] text-gray-600 font-medium">EN BOY ORANI</span>
                                    <div className="flex bg-[#111] border border-[#222] rounded-xl p-1 gap-1">
                                        {(["16:9", "9:16", "1:1"] as Aspect[]).map((a) => (
                                            <button
                                                key={a}
                                                onClick={() => setAspect(a)}
                                                className={`px-4 py-2 rounded-lg text-xs font-medium tracking-wider transition-all duration-200 ${aspect === a
                                                    ? "bg-white text-black"
                                                    : "text-gray-500 hover:text-white hover:bg-white/5"
                                                    }`}
                                            >
                                                {a}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="w-px h-12 bg-[#222]" />

                                {/* Prompt Mode */}
                                <div className="flex flex-col items-center gap-2">
                                    <span className="text-[10px] tracking-[0.3em] text-gray-600 font-medium">PROMPT MODU</span>
                                    <div className="flex bg-[#111] border border-[#222] rounded-xl p-1 gap-1">
                                        <button
                                            onClick={() => setPromptMode("auto")}
                                            className={`flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-medium tracking-wider transition-all duration-200 ${promptMode === "auto"
                                                ? "bg-[#C9A84C] text-black"
                                                : "text-gray-500 hover:text-white hover:bg-white/5"
                                                }`}
                                        >
                                            <Sparkles size={14} />
                                            OTOMATİK
                                        </button>
                                        <button
                                            onClick={() => setPromptMode("custom")}
                                            className={`flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-medium tracking-wider transition-all duration-200 ${promptMode === "custom"
                                                ? "bg-[#C9A84C] text-black"
                                                : "text-gray-500 hover:text-white hover:bg-white/5"
                                                }`}
                                        >
                                            <PenLine size={14} />
                                            ÖZEL
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Custom Prompt Textarea */}
                            {promptMode === "custom" && (
                                <div className="w-full max-w-lg">
                                    <div className="relative">
                                        <textarea
                                            value={customPrompt}
                                            onChange={(e) => setCustomPrompt(e.target.value.slice(0, 500))}
                                            placeholder="Stilinizi açıklayın... sıcak tonlar, sinematik ışık, gün batımı..."
                                            className="w-full h-28 resize-none bg-[#111] text-white/90 text-sm px-4 py-3 rounded-xl border border-[#222] focus:border-[#C9A84C]/50 focus:outline-none focus:ring-2 focus:ring-[#C9A84C]/20 transition-all placeholder:text-gray-700"
                                        />
                                        <div className="absolute bottom-3 right-3 text-[10px] text-gray-700">
                                            {customPrompt.length} / 500
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Generate / Regenerate Button */}
                            <button
                                onClick={generateGrid}
                                disabled={loading}
                                className="group relative bg-[#C9A84C] hover:bg-[#D4B85C] disabled:bg-[#C9A84C]/50 px-12 py-4 rounded-xl text-black font-bold tracking-wider transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-[#C9A84C]/25"
                            >
                                <span className="flex items-center gap-3">
                                    <Zap size={20} />
                                    {gridGenerated ? "YENİDEN OLUŞTUR" : "GRID OLUŞTUR"}
                                    <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                                </span>
                            </button>

                            <span className="text-xs text-gray-600">
                                İŞLEM SÜRESİ: ~30-60 SANİYE
                            </span>
                        </div>
                    )}

                    {/* ==================== SECTION 2: GRID DISPLAY ==================== */}
                    {gridGenerated && (
                        <div className="w-full flex flex-col items-center gap-4">
                            {/* Grid Header */}
                            <div className="w-full max-w-4xl flex justify-between items-center">
                                <button
                                    onClick={selectAll}
                                    className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
                                >
                                    <div className={`w-4 h-4 rounded border ${selected.length === 9 ? "bg-[#C9A84C] border-[#C9A84C]" : "border-gray-600"} flex items-center justify-center`}>
                                        {selected.length === 9 && <Check size={10} className="text-black" />}
                                    </div>
                                    TÜMÜNÜ SEÇ
                                </button>
                                <button
                                    onClick={downloadGrid}
                                    className="flex items-center gap-2 bg-[#1a1a1a] hover:bg-[#222] border border-[#333] px-4 py-2 rounded-lg text-sm font-medium transition-all"
                                >
                                    <Download size={16} className="text-white" />
                                    <span className="text-white tracking-wider">GRİD'İ İNDİR (TEK PNG)</span>
                                </button>
                            </div>

                            {/* Grid */}
                            <div
                                className="w-full max-w-4xl grid gap-[2px] rounded-lg overflow-hidden"
                                style={{
                                    gridTemplateColumns: "repeat(3, 1fr)",
                                    aspectRatio: aspect === "16:9" ? "16/9" : aspect === "9:16" ? "9/16" : "1/1",
                                    background: "#000",
                                }}
                            >
                                {Array.from({ length: 9 }).map((_, i) => {
                                    const isSelected = selected.includes(i);
                                    const isExtracted = extractedImages.some((img) => img.index === i && img.status === "ready");
                                    const isExtracting = extractedImages.some((img) => img.index === i && img.status === "extracting");

                                    return (
                                        <div
                                            key={i}
                                            onClick={() => toggleCell(i)}
                                            className="relative cursor-pointer overflow-hidden group"
                                            style={{
                                                backgroundImage: gridImage ? `url(${gridImage})` : undefined,
                                                backgroundSize: "300% 300%",
                                                backgroundPosition: `${(i % 3) * 50}% ${Math.floor(i / 3) * 50}%`,
                                            }}
                                        >
                                            {isExtracting && (
                                                <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/50 backdrop-blur-sm border border-yellow-500/50 px-3 py-1.5 rounded text-xs font-medium text-yellow-400 tracking-wide">
                                                    <RefreshCw size={12} className="animate-spin" />
                                                    ÇIKARILIYOR
                                                </div>
                                            )}

                                            {!isExtracted && !isExtracting && (
                                                <div
                                                    className={`absolute bottom-2 left-2 px-1.5 py-0.5 rounded text-xs font-medium transition-all duration-200 ${isSelected
                                                        ? "bg-[#C9A84C] text-black opacity-100"
                                                        : "bg-black/70 text-gray-300 opacity-0 group-hover:opacity-100"
                                                        }`}
                                                >
                                                    #{i + 1}
                                                </div>
                                            )}

                                            <div
                                                className={`absolute inset-0 transition-all duration-200 pointer-events-none ${isSelected || isExtracted || isExtracting
                                                    ? "border-4 border-[#C9A84C]/70"
                                                    : "border-transparent"
                                                    }`}
                                            />

                                            <div
                                                className={`absolute top-2 right-2 w-5 h-5 rounded-full flex items-center justify-center transition-all duration-200 ${isSelected || isExtracted
                                                    ? "bg-[#C9A84C] scale-100"
                                                    : "bg-white/20 scale-0 group-hover:scale-100"
                                                    }`}
                                            >
                                                <Check size={12} className={isSelected || isExtracted ? "text-black" : "text-white/50"} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {/* ==================== SECTION 3: EXTRACTION ==================== */}
                    {gridGenerated && (
                        <div className="flex flex-col items-center gap-5 py-4">
                            {/* Extraction Quality */}
                            {selected.length > 0 && (
                                <>
                                    <div className="flex flex-col items-center gap-3">
                                        <span className="text-[10px] tracking-[0.3em] text-gray-600 font-medium">ÇIKARMA KALİTESİ</span>
                                        <div className="flex bg-[#111] border border-[#222] rounded-xl p-1 gap-1">
                                            {([1, 2, 4] as Scale[]).map((s) => (
                                                <button
                                                    key={s}
                                                    onClick={() => setScale(s)}
                                                    className={`relative px-8 py-3 rounded-lg text-sm font-bold tracking-wider transition-all duration-200 ${scale === s ? "bg-white text-black" : "text-gray-500 hover:text-white hover:bg-white/5"
                                                        }`}
                                                >
                                                    {s}X
                                                    {s === 4 && (
                                                        <span className="absolute -top-1 -right-1 text-[8px] bg-[#C9A84C] text-black px-1.5 py-0.5 rounded-full font-bold">
                                                            4K
                                                        </span>
                                                    )}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <button
                                        onClick={handleExtract}
                                        disabled={extracting}
                                        className="group relative bg-gradient-to-r from-[#8B6D28] to-[#C9A84C] hover:from-[#C9A84C] hover:to-[#D4B85C] px-14 py-4 rounded-xl text-black font-bold tracking-wider transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-[#C9A84C]/30"
                                    >
                                        <span className="flex items-center gap-3">
                                            <Download size={20} />
                                            {selected.length} GÖRSEL ÇIKAR
                                            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                                        </span>
                                    </button>
                                </>
                            )}

                            {/* GO AGAIN Button */}
                            <button
                                onClick={resetAll}
                                className="bg-[#C9A84C] hover:bg-[#D4B85C] px-16 py-4 rounded-xl text-black font-bold text-lg tracking-wider transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-[#C9A84C]/25"
                            >
                                TEKRAR BAŞLA
                            </button>
                        </div>
                    )}

                    {/* ==================== SECTION 4: EXTRACTED IMAGES ==================== */}
                    {extractedImages.length > 0 && (
                        <div className="flex flex-col items-center gap-6 w-full py-8">
                            <div className="w-full max-w-4xl flex flex-col items-center gap-0">
                                <div className="w-full h-[1px] bg-white/20" />
                                <div className="w-10 h-10 -mt-5 rounded-full border border-white/20 bg-[#0a0a0a] flex items-center justify-center">
                                    <Download size={18} className="text-gray-500" />
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                <h2 className="text-2xl font-bold tracking-wider text-[#C9A84C]">ÇIKARILAN GÖRSELLER</h2>
                                <span className="text-gray-500 text-2xl">({extractedImages.filter(img => img.status === "ready").length})</span>
                            </div>

                            <div className="w-full max-w-4xl flex justify-end">
                                {extracting ? (
                                    <div className="flex items-center gap-2 bg-[#1a1a1a] border border-[#333] px-4 py-2.5 rounded-lg text-sm">
                                        <Loader2 size={16} className="text-gray-400 animate-spin" />
                                        <span className="text-gray-400 tracking-wider">ÇIKARILIYOR...</span>
                                    </div>
                                ) : (
                                    <button
                                        onClick={downloadAllExtracted}
                                        className="flex items-center gap-2 bg-[#C9A84C] hover:bg-[#D4B85C] px-4 py-2.5 rounded-lg text-sm font-medium transition-all"
                                    >
                                        <Download size={16} className="text-black" />
                                        <span className="text-black tracking-wider">TÜMÜNÜ İNDİR</span>
                                    </button>
                                )}
                            </div>

                            <div className="w-full max-w-4xl grid grid-cols-3 gap-2">
                                {extractedImages.map((img) => (
                                    <div
                                        key={img.index}
                                        className="relative aspect-video bg-[#111] overflow-hidden group"
                                        style={{
                                            backgroundImage: img.status === "ready" ? `url(${img.url})` : `url(${gridImage})`,
                                            backgroundSize: img.status === "ready" ? "cover" : "300% 300%",
                                            backgroundPosition:
                                                img.status === "ready" ? "center" : `${(img.index % 3) * 50}% ${Math.floor(img.index / 3) * 50}%`,
                                        }}
                                    >
                                        {img.status === "extracting" && (
                                            <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center gap-3">
                                                <div className="w-10 h-10 border-2 border-[#C9A84C] border-t-transparent rounded-full animate-spin" />
                                            </div>
                                        )}

                                        {img.status === "ready" && (
                                            <div className="absolute bottom-3 right-3 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-all duration-300">
                                                {onSendToChat && (
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            onSendToChat(img.url);
                                                        }}
                                                        className="w-10 h-10 rounded-full bg-[#C9A84C] hover:bg-[#D4B85C] flex items-center justify-center transition-all hover:scale-110"
                                                        title="Chat'e Gönder"
                                                    >
                                                        <MessageSquarePlus size={16} className="text-black" />
                                                    </button>
                                                )}
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        downloadSingleImage(img);
                                                    }}
                                                    className="w-10 h-10 rounded-full bg-[#333] hover:bg-[#444] flex items-center justify-center transition-all"
                                                    title="Görseli indir"
                                                >
                                                    <Download size={16} className="text-white" />
                                                </button>
                                            </div>
                                        )}

                                        <div
                                            className={`absolute bottom-3 left-3 px-2 py-1 text-xs font-medium tracking-wider ${img.status === "extracting" ? "bg-[#C9A84C]/20 text-[#C9A84C]" : "bg-[#C9A84C] text-black"
                                                }`}
                                        >
                                            {img.status === "extracting" ? "EXTRACTING..." : "READY"}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Error */}
                    {error && (
                        <div className="flex items-center gap-2 p-3 rounded-lg max-w-lg"
                            style={{ background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)" }}>
                            <span style={{ color: "#f87171" }}>{error}</span>
                            <button onClick={() => setError(null)} className="ml-auto">
                                <X size={16} style={{ color: "#f87171" }} />
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
