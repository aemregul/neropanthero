"use client";

import { useState, useEffect, useMemo } from "react";
import { Download, Globe, RefreshCw, ChevronLeft, Star, Loader2, Trash2, X, Bookmark, Pencil, LayoutGrid, ImageIcon, Video, Upload, Search, MoreHorizontal, MessageSquarePlus, Send, ChevronRight, Music, CheckSquare, Square } from "lucide-react";
import { getAssets, GeneratedAsset, deleteAsset, saveAssetToWardrobe, renameAsset } from "@/lib/api";
import { useToast } from "./ToastProvider";

interface Asset {
    id: string;
    url: string;
    type: "image" | "video" | "audio" | "uploaded";
    label?: string;
    duration?: string;
    isFavorite?: boolean;
    savedToImages?: boolean;
    thumbnailUrl?: string;
    isPending?: boolean;
}

type FilterTab = "all" | "images" | "videos" | "audio" | "favorites" | "uploads";

interface AssetsPanelProps {
    collapsed?: boolean;
    onToggle?: () => void;
    sessionId?: string | null;
    refreshKey?: number;
    incomingAsset?: { url: string; type: "image" | "video" | "audio" | "uploaded" } | null;
    onIncomingAssetConsumed?: () => void;
    onSaveToImages?: () => void;
    onAssetDeleted?: () => void;
    onAttachAssetUrl?: (url: string, type: "image" | "video" | "audio" | "uploaded") => void;
}

export function AssetsPanel({
    collapsed = false,
    onToggle,
    sessionId,
    refreshKey,
    incomingAsset,
    onIncomingAssetConsumed,
    onSaveToImages,
    onAssetDeleted,
    onAttachAssetUrl,
}: AssetsPanelProps) {
    const [assets, setAssets] = useState<Asset[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
    const [activeFilter, setActiveFilter] = useState<FilterTab>("all");
    const [searchQuery, setSearchQuery] = useState("");
    const [showSearch, setShowSearch] = useState(false);
    const [contextMenu, setContextMenu] = useState<{ asset: Asset; x: number; y: number } | null>(null);
    const [renamingId, setRenamingId] = useState<string | null>(null);
    const [renameValue, setRenameValue] = useState("");
    const [selectMode, setSelectMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const toast = useToast();

    const toggleSelect = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const handleDownloadSelected = async () => {
        const toDownload = filteredAssets.filter(a => selectedIds.has(a.id));
        if (toDownload.length === 0) return;
        toast.success(`${toDownload.length} medya indiriliyor...`);
        for (const asset of toDownload) {
            try {
                const response = await fetch(asset.url);
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `pepper_${asset.id}.${asset.type === "video" ? "mp4" : asset.type === "audio" ? "wav" : "png"}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                await new Promise(r => setTimeout(r, 300));
            } catch { }
        }
        setSelectMode(false);
        setSelectedIds(new Set());
    };

    // Fetch assets
    const fetchAssets = async () => {
        if (!sessionId) {
            setAssets([]);
            return;
        }
        const showBlockingLoader = assets.length === 0;
        if (showBlockingLoader) {
            setIsLoading(true);
        } else {
            setIsRefreshing(true);
        }
        try {
            const data = await getAssets(sessionId);
            if (data && Array.isArray(data)) {
                const mapped: Asset[] = data.map((a: GeneratedAsset) => ({
                    id: a.id,
                    url: a.url,
                    type: (a.asset_type as "image" | "video" | "audio") || "image",
                    label: a.prompt?.substring(0, 50),
                    isFavorite: false,
                    savedToImages: false,
                    thumbnailUrl: a.thumbnail_url,
                }));
                setAssets((prev) => {
                    const optimisticAssets = prev.filter(
                        (asset) =>
                            asset.isPending &&
                            !mapped.some(
                                (serverAsset) => serverAsset.url === asset.url && serverAsset.type === asset.type
                            )
                    );

                    return [...optimisticAssets, ...mapped];
                });
            }
        } catch (error) {
            console.error("Assets fetch error:", error);
        } finally {
            setIsLoading(false);
            setIsRefreshing(false);
        }
    };

    useEffect(() => { fetchAssets(); }, [sessionId, refreshKey]);

    useEffect(() => {
        if (!incomingAsset?.url) {
            return;
        }

        setAssets((prev) => {
            const exists = prev.some((asset) => asset.url === incomingAsset.url && asset.type === incomingAsset.type);
            if (exists) {
                return prev;
            }

            return [
                {
                    id: `pending-${Date.now()}`,
                    url: incomingAsset.url,
                    type: incomingAsset.type,
                    label: "Hazırlanıyor...",
                    isFavorite: false,
                    savedToImages: false,
                    thumbnailUrl: incomingAsset.type === "image" ? incomingAsset.url : undefined,
                    isPending: true,
                },
                ...prev,
            ];
        });

        onIncomingAssetConsumed?.();
    }, [incomingAsset, onIncomingAssetConsumed]);

    // Filtered assets
    const filteredAssets = useMemo(() => {
        let result = assets;
        if (activeFilter === "images") result = result.filter(a => a.type === "image");
        else if (activeFilter === "videos") result = result.filter(a => a.type === "video");
        else if (activeFilter === "audio") result = result.filter(a => a.type === "audio");
        else if (activeFilter === "favorites") result = result.filter(a => a.isFavorite);
        else if (activeFilter === "uploads") result = result.filter(a => a.type === "uploaded");
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            result = result.filter(a => a.label?.toLowerCase().includes(q));
        }
        return result;
    }, [assets, activeFilter, searchQuery]);

    // Actions
    const toggleFavorite = (assetId: string) => {
        setAssets(prev => prev.map(a => a.id === assetId ? { ...a, isFavorite: !a.isFavorite } : a));
    };

    const handleDelete = async (assetId: string, e?: React.MouseEvent) => {
        e?.stopPropagation();
        try {
            await deleteAsset(assetId);
            setAssets(prev => prev.filter(a => a.id !== assetId));
            setContextMenu(null);
            onAssetDeleted?.();
            toast.success("Medya silindi");
        } catch { toast.error("Silme hatası"); }
    };

    const handleSaveToImages = async (asset: Asset, e?: React.MouseEvent) => {
        e?.stopPropagation();
        if (!sessionId) return;
        try {
            await saveAssetToWardrobe(sessionId, asset.url, asset.label);
            setAssets(prev => prev.map(a => a.id === asset.id ? { ...a, savedToImages: true } : a));
            setContextMenu(null);
            onSaveToImages?.();
            toast.success("Kaydedildi");
        } catch { toast.error("Kaydetme hatası"); }
    };

    const handleRename = async (asset: Asset) => {
        setRenamingId(asset.id);
        setRenameValue(asset.label || "");
        setContextMenu(null);
    };

    const submitRename = async (assetId: string) => {
        if (!renameValue.trim()) { setRenamingId(null); return; }
        try {
            await renameAsset(assetId, renameValue.trim());
            setAssets(prev => prev.map(a => a.id === assetId ? { ...a, label: renameValue.trim() } : a));
            toast.success("Ad güncellendi");
        } catch { toast.error("Güncelleme hatası"); }
        setRenamingId(null);
    };

    const handleAttachToChat = (asset: Asset, e?: React.MouseEvent) => {
        e?.stopPropagation();
        onAttachAssetUrl?.(asset.url, asset.type);
        toast.success(`${asset.type === "video" ? "Video" : asset.type === "audio" ? "Ses" : "Görsel"} chat'e eklendi`);
    };

    const downloadAsset = async (asset: Asset) => {
        try {
            const response = await fetch(asset.url);
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `pepper_${asset.id}.${asset.type === "video" ? "mp4" : "png"}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch { }
    };

    // Lightbox navigation
    const navigateLightbox = (direction: "prev" | "next") => {
        if (!selectedAsset) return;
        const idx = filteredAssets.findIndex(a => a.id === selectedAsset.id);
        const newIdx = direction === "next" ? (idx + 1) % filteredAssets.length : (idx - 1 + filteredAssets.length) % filteredAssets.length;
        setSelectedAsset(filteredAssets[newIdx]);
    };

    // Close context menu on click outside
    useEffect(() => {
        const handler = () => setContextMenu(null);
        window.addEventListener("click", handler);
        return () => window.removeEventListener("click", handler);
    }, []);

    const filterTabs: { key: FilterTab; icon: React.ElementType; label: string; count: number }[] = [
        { key: "all", icon: LayoutGrid, label: "Tümü", count: assets.length },
        { key: "images", icon: ImageIcon, label: "Görsel", count: assets.filter(a => a.type === "image").length },
        { key: "videos", icon: Video, label: "Video", count: assets.filter(a => a.type === "video").length },
        { key: "audio", icon: Music, label: "Ses", count: assets.filter(a => a.type === "audio").length },
        { key: "favorites", icon: Star, label: "Favori", count: assets.filter(a => a.isFavorite).length },
        { key: "uploads", icon: Upload, label: "Yüklenen", count: assets.filter(a => a.type === "uploaded").length },
    ];

    if (collapsed) {
        return (
            <button
                onClick={onToggle}
                className="hidden lg:flex fixed right-0 top-1/2 -translate-y-1/2 p-2 rounded-l-lg z-30"
                style={{ background: "var(--card)", border: "1px solid var(--border)" }}
            >
                <ChevronLeft size={20} />
            </button>
        );
    }

    return (
        <>
            {/* Context Menu */}
            {contextMenu && (
                <div
                    className="fixed z-[60] py-1 rounded-lg shadow-xl min-w-[160px]"
                    style={{
                        left: Math.min(contextMenu.x, window.innerWidth - 180),
                        top: Math.min(contextMenu.y, window.innerHeight - 200),
                        background: "var(--card)",
                        border: "1px solid var(--border)",
                    }}
                    onClick={e => e.stopPropagation()}
                >
                    <button
                        className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--background-secondary)] transition-colors"
                        onClick={() => { handleAttachToChat(contextMenu.asset); setContextMenu(null); }}
                    >
                        <MessageSquarePlus size={14} style={{ color: "var(--accent)" }} /> Chat&apos;e Ekle
                    </button>
                    <button
                        className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--background-secondary)] transition-colors"
                        onClick={() => { downloadAsset(contextMenu.asset); setContextMenu(null); }}
                    >
                        <Download size={14} /> İndir
                    </button>
                    <button
                        className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--background-secondary)] transition-colors"
                        onClick={() => { toggleFavorite(contextMenu.asset.id); setContextMenu(null); }}
                    >
                        <Star size={14} fill={contextMenu.asset.isFavorite ? "#eab308" : "none"} className={contextMenu.asset.isFavorite ? "text-yellow-500" : ""} />
                        {contextMenu.asset.isFavorite ? "Favoriden Çıkar" : "Favorilere Ekle"}
                    </button>
                    <button
                        className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--background-secondary)] transition-colors"
                        onClick={() => handleSaveToImages(contextMenu.asset)}
                    >
                        <Bookmark size={14} /> Kaydet
                    </button>
                    <button
                        className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-[var(--background-secondary)] transition-colors"
                        onClick={() => handleRename(contextMenu.asset)}
                    >
                        <Pencil size={14} /> Yeniden Adlandır
                    </button>
                    <div className="my-1 border-t" style={{ borderColor: "var(--border)" }} />
                    <button
                        className="w-full px-3 py-2 text-sm text-left flex items-center gap-2 hover:bg-red-500/10 text-red-400 transition-colors"
                        onClick={() => handleDelete(contextMenu.asset.id)}
                    >
                        <Trash2 size={14} /> Sil
                    </button>
                </div>
            )}

            {/* Lightbox Modal */}
            {selectedAsset && (
                <div
                    className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/90"
                    onClick={() => setSelectedAsset(null)}
                >
                    {/* Close button */}
                    <button className="absolute top-4 right-4 p-2 rounded-full hover:bg-white/10 transition-colors z-10" onClick={() => setSelectedAsset(null)}>
                        <X size={24} className="text-white" />
                    </button>

                    {/* Navigation arrows */}
                    {filteredAssets.length > 1 && (
                        <>
                            <button className="absolute left-4 top-1/2 -translate-y-1/2 p-3 rounded-full hover:bg-white/10 transition-colors" onClick={e => { e.stopPropagation(); navigateLightbox("prev"); }}>
                                <ChevronLeft size={28} className="text-white" />
                            </button>
                            <button className="absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-full hover:bg-white/10 transition-colors" onClick={e => { e.stopPropagation(); navigateLightbox("next"); }}>
                                <ChevronRight size={28} className="text-white" />
                            </button>
                        </>
                    )}

                    {/* Media content */}
                    <div className="max-w-[85vw] max-h-[75vh] flex items-center justify-center" onClick={e => e.stopPropagation()}>
                        {selectedAsset.type === "video" ? (
                            <video src={selectedAsset.url} controls autoPlay muted playsInline preload="metadata" className="max-w-full max-h-[75vh] rounded-lg" />
                        ) : selectedAsset.type === "audio" ? (
                            <div className="flex flex-col items-center gap-4 p-8">
                                <span className="text-6xl">🎵</span>
                                <audio src={selectedAsset.url} controls autoPlay />
                            </div>
                        ) : (
                            <img src={selectedAsset.url} alt="" className="max-w-full max-h-[75vh] object-contain rounded-lg" />
                        )}
                    </div>

                    {/* Lightbox toolbar */}
                    <div className="mt-4 flex items-center gap-2" onClick={e => e.stopPropagation()}>
                        {/* Chat'e Gönder — Ana buton */}
                        <button
                            onClick={() => { handleAttachToChat(selectedAsset); setSelectedAsset(null); }}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all hover:scale-105"
                            style={{ background: "var(--accent)", color: "white" }}
                        >
                            <Send size={16} /> Chat&apos;e Gönder
                        </button>
                        <button onClick={() => downloadAsset(selectedAsset)} className="p-2 rounded-full hover:bg-white/15 transition-colors" title="İndir">
                            <Download size={18} className="text-white" />
                        </button>
                        <button onClick={() => { toggleFavorite(selectedAsset.id); setSelectedAsset({ ...selectedAsset, isFavorite: !selectedAsset.isFavorite }); }} className="p-2 rounded-full hover:bg-white/15 transition-colors" title="Favori">
                            <Star size={18} fill={selectedAsset.isFavorite ? "#eab308" : "none"} className={selectedAsset.isFavorite ? "text-yellow-500" : "text-white"} />
                        </button>
                        <button onClick={() => handleDelete(selectedAsset.id)} className="p-2 rounded-full hover:bg-red-500/40 transition-colors" title="Sil">
                            <Trash2 size={18} className="text-white" />
                        </button>
                        <div className="w-px h-5 bg-white/20 mx-1" />
                        <span className="text-white/60 text-sm">
                            {filteredAssets.findIndex(a => a.id === selectedAsset.id) + 1} / {filteredAssets.length}
                        </span>
                    </div>
                </div>
            )}

            {/* Main Panel */}
            <aside
                className="hidden lg:flex flex-col w-[300px] xl:w-[340px] h-screen border-l"
                style={{ background: "var(--background-secondary)", borderColor: "var(--border)" }}
            >
                {/* Filter Tabs Header */}
                <header className="h-14 px-3 border-b shrink-0 flex items-center" style={{ borderColor: "var(--border)" }}>
                    <div className="flex items-center w-full gap-1">
                        {/* Filter tabs group */}
                        <div className="flex items-center gap-0.5 flex-1 justify-evenly">
                            {filterTabs.map(tab => {
                                const Icon = tab.icon;
                                const isActive = activeFilter === tab.key;
                                const hasItems = tab.count > 0;
                                return (
                                    <button
                                        key={tab.key}
                                        onClick={() => setActiveFilter(tab.key)}
                                        className={`relative p-2 rounded-lg transition-all duration-200 ${isActive ? "shadow-md" : "hover:bg-[var(--card)]"}`}
                                        style={isActive ? {
                                            background: "var(--accent)",
                                            color: "white",
                                        } : { color: "var(--foreground-muted)" }}
                                        title={`${tab.label} (${tab.count})`}
                                    >
                                        <Icon size={16} />
                                    </button>
                                );
                            })}
                        </div>

                        {/* Divider */}
                        <div className="w-px h-6 shrink-0" style={{ background: "var(--border)" }} />

                        {/* Action buttons group */}
                        <div className="flex items-center gap-0.5">
                            {/* Search toggle */}
                            <button
                                onClick={() => setShowSearch(!showSearch)}
                                className={`p-2 rounded-lg transition-colors ${showSearch ? "bg-[var(--card)]" : "hover:bg-[var(--card)]"}`}
                            >
                                <Search size={16} style={{ color: showSearch ? "var(--accent)" : "var(--foreground-muted)" }} />
                            </button>

                            {/* Refresh */}
                            <button
                                onClick={fetchAssets}
                                className="p-2 rounded-lg hover:bg-[var(--card)] transition-colors"
                                title="Yenile"
                            >
                                <RefreshCw size={16} className={isLoading || isRefreshing ? "animate-spin" : ""} style={{ color: "var(--foreground-muted)" }} />
                            </button>

                            {/* Collapse */}
                            <button
                                onClick={onToggle}
                                className="p-2 rounded-lg hover:bg-[var(--card)] transition-colors"
                            >
                                <ChevronRight size={16} style={{ color: "var(--foreground-muted)" }} />
                            </button>
                        </div>
                    </div>

                    {/* Search bar (conditional) */}
                    {showSearch && (
                        <div className="mt-2 mb-1 relative">
                            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--foreground-muted)" }} />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                                placeholder="Ara..."
                                autoFocus
                                className="w-full pl-8 pr-3 py-1.5 rounded-lg text-sm outline-none"
                                style={{
                                    background: "var(--card)",
                                    color: "var(--foreground)",
                                    border: "1px solid var(--border)",
                                }}
                            />
                        </div>
                    )}
                </header>

                {/* Assets Grid */}
                <div className="flex-1 overflow-y-auto p-2">
                    {isLoading && filteredAssets.length === 0 ? (
                        <div className="flex items-center justify-center h-40">
                            <Loader2 size={24} className="animate-spin" style={{ color: "var(--accent)" }} />
                        </div>
                    ) : filteredAssets.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-center px-4">
                            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-3" style={{ background: "var(--card)" }}>
                                {activeFilter === "images" ? <ImageIcon size={28} style={{ color: "var(--foreground-muted)" }} /> :
                                    activeFilter === "videos" ? <Video size={28} style={{ color: "var(--foreground-muted)" }} /> :
                                        activeFilter === "uploads" ? <Upload size={28} style={{ color: "var(--foreground-muted)" }} /> :
                                            <LayoutGrid size={28} style={{ color: "var(--foreground-muted)" }} />}
                            </div>
                            <p className="text-sm" style={{ color: "var(--foreground-muted)" }}>
                                {searchQuery ? "Sonuç bulunamadı" : "Henüz medya yok"}
                            </p>
                            <p className="text-xs mt-1" style={{ color: "var(--foreground-muted)" }}>
                                {searchQuery ? "Farklı bir arama deneyin" : "Chat'te içerik üretmeye başlayın!"}
                            </p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 gap-2">
                            {filteredAssets.map((asset) => (
                                <div
                                    key={asset.id}
                                    className={`group relative rounded-xl overflow-hidden cursor-pointer transition-all duration-200 ${selectMode && selectedIds.has(asset.id) ? 'ring-2 ring-[var(--accent)]' : 'hover:ring-2 hover:ring-[var(--accent)]/40'}`}
                                    style={{ background: "var(--card)" }}
                                    onClick={() => selectMode ? toggleSelect(asset.id) : setSelectedAsset(asset)}
                                    onContextMenu={e => { e.preventDefault(); setContextMenu({ asset, x: e.clientX, y: e.clientY }); }}
                                >
                                    {/* Media content */}
                                    <div className="aspect-square relative">
                                        {asset.type === "video" ? (
                                            <div className="w-full h-full">
                                                {asset.thumbnailUrl ? (
                                                    <img src={asset.thumbnailUrl} alt="" className="w-full h-full object-cover" loading={asset.isPending ? "eager" : "lazy"} />
                                                ) : (
                                                    <video
                                                        src={`${asset.url}#t=0.1`}
                                                        className="w-full h-full object-cover"
                                                        muted loop playsInline preload="metadata"
                                                        onMouseOver={e => { e.currentTarget.play().catch(() => { }); }}
                                                        onMouseOut={e => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }}
                                                    />
                                                )}
                                            </div>
                                        ) : asset.type === "audio" ? (
                                            <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-amber-900/40 to-stone-900/40">
                                                <span className="text-3xl mb-1">🎵</span>
                                                <span className="text-[10px] text-white/60 px-2 text-center truncate w-full">{asset.label || "Ses"}</span>
                                            </div>
                                        ) : (
                                            <img src={asset.url} alt="" className="w-full h-full object-cover" loading={asset.isPending ? "eager" : "lazy"} decoding="async" />
                                        )}

                                        {/* Rename overlay */}
                                        {renamingId === asset.id && (
                                            <div className="absolute inset-0 bg-black/70 flex items-center justify-center p-2 z-20" onClick={e => e.stopPropagation()}>
                                                <input
                                                    autoFocus
                                                    value={renameValue}
                                                    onChange={e => setRenameValue(e.target.value)}
                                                    onKeyDown={e => { if (e.key === "Enter") submitRename(asset.id); if (e.key === "Escape") setRenamingId(null); }}
                                                    onBlur={() => submitRename(asset.id)}
                                                    className="w-full px-2 py-1 rounded text-xs bg-white/10 text-white outline-none border border-white/20"
                                                />
                                            </div>
                                        )}

                                        {/* Hover overlay */}
                                        <div className={`absolute inset-0 transition-all duration-200 pointer-events-none ${selectMode && selectedIds.has(asset.id) ? 'bg-black/30' : 'bg-black/0 group-hover:bg-black/30'}`} />

                                        {/* Selection checkbox */}
                                        {selectMode && (
                                            <div className="absolute top-1.5 left-1.5 z-10">
                                                {selectedIds.has(asset.id) ? (
                                                    <CheckSquare size={18} style={{ color: 'var(--accent)' }} fill="var(--accent)" className="drop-shadow" />
                                                ) : (
                                                    <Square size={18} className="text-white/70 drop-shadow" />
                                                )}
                                            </div>
                                        )}

                                        {/* Top-left: type badge */}
                                        {asset.type === "video" && (
                                            <div className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-black/60 text-white flex items-center gap-1">
                                                <Video size={10} /> VİDEO
                                            </div>
                                        )}

                                        {asset.isPending && (
                                            <div className="absolute inset-0 bg-black/35 flex items-center justify-center pointer-events-none">
                                                <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-black/55 text-white text-[10px] font-medium">
                                                    <Loader2 size={10} className="animate-spin" />
                                                    Yükleniyor
                                                </div>
                                            </div>
                                        )}

                                        {/* Top-right: favorite star */}
                                        {asset.isFavorite && (
                                            <div className="absolute top-1.5 right-1.5">
                                                <Star size={14} fill="#eab308" className="text-yellow-500 drop-shadow" />
                                            </div>
                                        )}

                                        {/* Bottom-right: attach to chat button (hover only) */}
                                        <button
                                            onClick={e => handleAttachToChat(asset, e)}
                                            className="absolute bottom-1.5 right-1.5 p-2 rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-200 hover:scale-110"
                                            style={{ background: "var(--accent)", color: "white", boxShadow: "0 2px 8px rgba(0,0,0,0.3)" }}
                                            title="Chat'e Ekle"
                                        >
                                            <MessageSquarePlus size={14} />
                                        </button>

                                        {/* Bottom-left: more options (hover only) */}
                                        <button
                                            onClick={e => { e.stopPropagation(); setContextMenu({ asset, x: e.clientX, y: e.clientY }); }}
                                            className="absolute bottom-1.5 left-1.5 p-1.5 rounded-lg bg-black/50 opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-black/70"
                                            title="Daha Fazla"
                                        >
                                            <MoreHorizontal size={14} className="text-white" />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Bottom bar */}
                <div className="p-2 border-t flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
                    <div className="flex items-center gap-1">
                        <button
                            onClick={() => { setSelectMode(!selectMode); setSelectedIds(new Set()); }}
                            className={`p-1.5 rounded-lg transition-colors ${selectMode ? '' : 'hover:bg-[var(--card)]'}`}
                            style={selectMode ? { background: 'var(--accent)', color: 'white' } : { color: 'var(--foreground-muted)' }}
                            title={selectMode ? 'Seçimi İptal' : 'Seç ve İndir'}
                        >
                            <CheckSquare size={15} />
                        </button>
                        {selectMode && selectedIds.size > 0 && (
                            <button
                                onClick={handleDownloadSelected}
                                className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors hover:opacity-90"
                                style={{ background: 'var(--accent)', color: 'white' }}
                            >
                                <Download size={12} />
                                {selectedIds.size} İndir
                            </button>
                        )}
                    </div>
                    <span className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                        {selectMode ? `${selectedIds.size} / ${filteredAssets.length} seçili` : `${filteredAssets.length} medya`}
                    </span>
                </div>
            </aside >
        </>
    );
}
