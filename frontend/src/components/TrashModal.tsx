"use client";

import { useState, useEffect, useRef } from "react";
import { X, Trash2, RotateCcw, Clock, AlertCircle, CheckSquare, Square, Trash, ImageIcon, Video } from "lucide-react";

export interface TrashItem {
    id: string;
    name: string;
    type: "proje" | "karakter" | "lokasyon" | "wardrobe" | "preset" | "marka" | "session" | "character" | "location" | "brand" | "asset";
    deletedAt: Date;
    imageUrl?: string;
    assetType?: "image" | "video" | "audio"; // from original_data.type
    originalData: Record<string, unknown>;
}

interface TrashModalProps {
    isOpen: boolean;
    onClose: () => void;
    items: TrashItem[];
    onRestore: (item: TrashItem) => void;
    onPermanentDelete: (id: string) => void;
    onDeleteAll?: () => void;
    onDeleteMultiple?: (ids: string[]) => void;
}

function getTimeRemaining(deletedAt: Date): string {
    const now = new Date();
    const deleteTime = new Date(deletedAt);
    deleteTime.setDate(deleteTime.getDate() + 3); // 3 gün sonra silinecek

    const diff = deleteTime.getTime() - now.getTime();
    if (diff <= 0) return "Siliniyor...";

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);
    const remainingHours = hours % 24;

    if (days > 0) {
        return `${days} gün ${remainingHours} saat`;
    }
    return `${hours} saat`;
}

// Gerçek medya tipini belirle (asset/wardrobe için URL veya original_data'dan)
function getMediaCategory(item: TrashItem): "image" | "video" | "audio" | null {
    // assetType zaten varsa direkt kullan
    if (item.assetType) return item.assetType;
    // original_data.type kontrolü
    const odType = item.originalData?.type as string | undefined;
    if (odType === "image" || odType === "video" || odType === "audio") return odType;
    // URL uzantısından tahmin
    const url = (item.imageUrl || item.originalData?.url || "") as string;
    if (url.match(/\.(mp4|mov|webm)(\?.*)?$/i)) return "video";
    if (url.match(/\.(wav|mp3|ogg|flac)(\?.*)?$/i)) return "audio";
    if (url.match(/\.(png|jpg|jpeg|webp|gif)(\?.*)?$/i)) return "image";
    // asset veya wardrobe ise varsayılan image
    if (item.type === "asset" || item.type === "wardrobe") return "image";
    return null;
}

function getTypeLabel(item: TrashItem): string {
    // Medya tipi olan item'lar için medya etiketi göster
    const media = getMediaCategory(item);
    if (media) {
        if (media === "video") return "Video";
        if (media === "audio") return "Ses";
        return "Görsel";
    }
    // Entity/proje tipleri
    const labels: Partial<Record<TrashItem["type"], string>> = {
        proje: "Proje", session: "Proje",
        karakter: "Karakter", character: "Karakter",
        lokasyon: "Lokasyon", location: "Lokasyon",
        preset: "Preset",
        marka: "Marka", brand: "Marka",
    };
    return labels[item.type] || item.type;
}

function getTypeColor(item: TrashItem): string {
    const media = getMediaCategory(item);
    if (media === "video") return "#3b82f6";
    if (media === "audio") return "#a855f7";
    if (media === "image") return "#f97316";
    const colors: Partial<Record<TrashItem["type"], string>> = {
        proje: "#C9A84C", session: "#C9A84C",
        karakter: "#B8963A", character: "#B8963A",
        lokasyon: "#3b82f6", location: "#3b82f6",
        preset: "#ec4899",
        marka: "#06b6d4", brand: "#06b6d4",
    };
    return colors[item.type] || "#6b7280";
}

// Lazy video thumbnail — only loads when scrolled into view
function LazyVideoThumb({ src }: { src: string }) {
    const ref = useRef<HTMLDivElement>(null);
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        const el = ref.current;
        if (!el) return;
        const observer = new IntersectionObserver(
            ([entry]) => { if (entry.isIntersecting) { setIsVisible(true); observer.disconnect(); } },
            { rootMargin: '100px' }
        );
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    return (
        <div ref={ref} className="w-full h-full">
            {isVisible ? (
                <video
                    src={src + '#t=1'}
                    muted
                    playsInline
                    preload="metadata"
                    className="w-full h-full object-cover"
                    onError={(e) => {
                        (e.currentTarget as HTMLVideoElement).style.display = 'none';
                    }}
                />
            ) : (
                <div className="w-full h-full flex items-center justify-center">
                    <span className="text-xl">🎬</span>
                </div>
            )}
        </div>
    );
}

export function TrashModal({
    isOpen,
    onClose,
    items,
    onRestore,
    onPermanentDelete,
    onDeleteAll,
    onDeleteMultiple
}: TrashModalProps) {
    const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
    const [selectedIds, setSelectedIds] = useState<string[]>([]);
    const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);
    const [confirmDeleteSelected, setConfirmDeleteSelected] = useState(false);
    const [activeFilter, setActiveFilter] = useState<string>("all");

    if (!isOpen) return null;

    // Filtreleme — medya tipine göre
    const filteredItems = activeFilter === "all"
        ? items
        : items.filter(item => {
            if (activeFilter === "image" || activeFilter === "video" || activeFilter === "audio") {
                return getMediaCategory(item) === activeFilter;
            }
            const typeAliases: Record<string, string[]> = {
                proje: ["proje", "session"],
                karakter: ["karakter", "character"],
                lokasyon: ["lokasyon", "location"],
                marka: ["marka", "brand"],
            };
            const aliases = typeAliases[activeFilter] || [activeFilter];
            return aliases.includes(item.type);
        });

    // Kategori sayıları — medya tipine göre
    const categoryCounts: Record<string, number> = {
        all: items.length,
        image: items.filter(i => getMediaCategory(i) === "image").length,
        video: items.filter(i => getMediaCategory(i) === "video").length,
        audio: items.filter(i => getMediaCategory(i) === "audio").length,
        proje: items.filter(i => i.type === "proje" || i.type === "session").length,
        karakter: items.filter(i => i.type === "karakter" || i.type === "character").length,
        lokasyon: items.filter(i => i.type === "lokasyon" || i.type === "location").length,
        preset: items.filter(i => i.type === "preset").length,
        marka: items.filter(i => i.type === "marka" || i.type === "brand").length,
    };

    const toggleSelection = (id: string) => {
        if (selectedIds.includes(id)) {
            setSelectedIds(selectedIds.filter(i => i !== id));
        } else {
            setSelectedIds([...selectedIds, id]);
        }
    };

    const toggleSelectAll = () => {
        if (selectedIds.length === filteredItems.length) {
            setSelectedIds([]);
        } else {
            setSelectedIds(filteredItems.map(i => i.id));
        }
    };

    const handleDeleteSelected = () => {
        if (onDeleteMultiple) {
            onDeleteMultiple(selectedIds);
        } else {
            selectedIds.forEach(id => onPermanentDelete(id));
        }
        setSelectedIds([]);
        setConfirmDeleteSelected(false);
    };

    const handleDeleteAll = () => {
        if (onDeleteAll) {
            onDeleteAll();
        } else {
            items.forEach(item => onPermanentDelete(item.id));
        }
        setConfirmDeleteAll(false);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/70 backdrop-blur-md"
                onClick={onClose}
            />

            {/* Modal */}
            <div
                className="relative w-full max-w-lg max-h-[80vh] rounded-2xl shadow-2xl overflow-hidden"
                style={{ background: "var(--card)", border: "1px solid var(--border)" }}
            >
                {/* Header */}
                <div
                    className="flex items-center justify-between p-5 border-b"
                    style={{
                        borderColor: "var(--border)",
                        background: "linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, transparent 100%)"
                    }}
                >
                    <div className="flex items-center gap-3">
                        <div
                            className="p-2 rounded-xl"
                            style={{ background: "rgba(239, 68, 68, 0.2)" }}
                        >
                            <Trash2 size={24} className="text-red-500" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">Çöp Kutusu</h2>
                            <p className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                                {items.length} öğe • 3 gün sonra kalıcı silinir
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-xl hover:bg-[var(--background)] transition-all duration-200"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Category Tabs */}
                {items.length > 0 && (
                    <div
                        className="flex gap-2 px-4 py-3 overflow-x-auto border-b"
                        style={{ borderColor: "var(--border)", background: "var(--background)" }}
                    >
                        {[
                            { key: "all", label: "Tümü", color: "#6b7280" },
                            { key: "image", label: "Görseller", color: "#f97316" },
                            { key: "video", label: "Videolar", color: "#3b82f6" },
                            { key: "audio", label: "Sesler", color: "#a855f7" },
                            { key: "proje", label: "Projeler", color: "#C9A84C" },
                            { key: "karakter", label: "Karakterler", color: "#B8963A" },
                            { key: "lokasyon", label: "Lokasyonlar", color: "#3b82f6" },
                            { key: "preset", label: "Presetler", color: "#ec4899" },
                            { key: "marka", label: "Markalar", color: "#06b6d4" },
                        ].map(cat => {
                            const count = categoryCounts[cat.key] || 0;
                            if (cat.key !== "all" && count === 0) return null;
                            return (
                                <button
                                    key={cat.key}
                                    onClick={() => {
                                        setActiveFilter(cat.key);
                                        setSelectedIds([]);
                                    }}
                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-all ${activeFilter === cat.key
                                        ? "ring-2 ring-offset-1 ring-offset-transparent"
                                        : "opacity-70 hover:opacity-100"
                                        }`}
                                    style={{
                                        background: activeFilter === cat.key ? `${cat.color}20` : "var(--card)",
                                        color: activeFilter === cat.key ? cat.color : "inherit",
                                        borderColor: activeFilter === cat.key ? cat.color : "transparent",
                                        borderWidth: "2px"
                                    }}
                                >
                                    <span
                                        className="w-2 h-2 rounded-full"
                                        style={{ background: cat.color }}
                                    />
                                    {cat.label}
                                    <span
                                        className="px-1.5 py-0.5 rounded text-xs"
                                        style={{ background: "var(--background)" }}
                                    >
                                        {count}
                                    </span>
                                </button>
                            );
                        })}
                    </div>
                )}

                {/* Toolbar - Select All & Bulk Actions */}
                {items.length > 0 && (
                    <div
                        className="flex items-center justify-between px-4 py-2 border-b"
                        style={{ borderColor: "var(--border)", background: "var(--background)" }}
                    >
                        <button
                            onClick={toggleSelectAll}
                            className="flex items-center gap-2 text-sm hover:opacity-80 transition-opacity"
                        >
                            {selectedIds.length === items.length ? (
                                <CheckSquare size={18} style={{ color: "var(--accent)" }} />
                            ) : (
                                <Square size={18} style={{ color: "var(--foreground-muted)" }} />
                            )}
                            <span style={{ color: "var(--foreground-muted)" }}>
                                {selectedIds.length > 0 ? `${selectedIds.length} seçili` : "Tümünü Seç"}
                            </span>
                        </button>

                        <div className="flex items-center gap-2">
                            {/* Delete Selected */}
                            {selectedIds.length > 0 && (
                                confirmDeleteSelected ? (
                                    <div className="flex items-center gap-1">
                                        <button
                                            onClick={handleDeleteSelected}
                                            className="px-3 py-1.5 text-xs rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
                                        >
                                            {selectedIds.length} Öğeyi Sil
                                        </button>
                                        <button
                                            onClick={() => setConfirmDeleteSelected(false)}
                                            className="px-3 py-1.5 text-xs rounded-lg hover:bg-[var(--card)] transition-colors"
                                        >
                                            İptal
                                        </button>
                                    </div>
                                ) : (
                                    <button
                                        onClick={() => setConfirmDeleteSelected(true)}
                                        className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg hover:bg-red-500/20 text-red-400 transition-colors"
                                    >
                                        <Trash size={14} />
                                        Seçilenleri Sil
                                    </button>
                                )
                            )}

                            {/* Delete All */}
                            {confirmDeleteAll ? (
                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={handleDeleteAll}
                                        className="px-3 py-1.5 text-xs rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
                                    >
                                        Tümünü Sil
                                    </button>
                                    <button
                                        onClick={() => setConfirmDeleteAll(false)}
                                        className="px-3 py-1.5 text-xs rounded-lg hover:bg-[var(--card)] transition-colors"
                                    >
                                        İptal
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={() => setConfirmDeleteAll(true)}
                                    className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-red-500/50 text-red-400 hover:bg-red-500/20 transition-colors"
                                >
                                    <Trash2 size={14} />
                                    Tümünü Sil
                                </button>
                            )}
                        </div>
                    </div>
                )}

                {/* Content */}
                <div className="p-4 overflow-y-auto max-h-[calc(80vh-180px)]">
                    {items.length === 0 ? (
                        <div className="text-center py-12">
                            <Trash2 size={48} className="mx-auto mb-3 opacity-20" />
                            <p style={{ color: "var(--foreground-muted)" }}>
                                Çöp kutusu boş
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {filteredItems.map((item) => (
                                <div
                                    key={item.id}
                                    className={`flex items-center justify-between p-3 rounded-xl transition-all ${selectedIds.includes(item.id) ? "ring-2 ring-[var(--accent)]" : ""
                                        }`}
                                    style={{ background: "var(--background)" }}
                                >
                                    {/* Checkbox */}
                                    <button
                                        onClick={() => toggleSelection(item.id)}
                                        className="mr-3 shrink-0"
                                    >
                                        {selectedIds.includes(item.id) ? (
                                            <CheckSquare size={20} style={{ color: "var(--accent)" }} />
                                        ) : (
                                            <Square size={20} style={{ color: "var(--foreground-muted)" }} />
                                        )}
                                    </button>

                                    <div className="flex items-center gap-3 flex-1 min-w-0">
                                        {/* Thumbnail — medya tipine göre */}
                                        {(() => {
                                            const media = getMediaCategory(item);
                                            if (media === 'video') return (
                                                <div className="w-14 h-14 rounded-lg shrink-0 border border-[var(--border)] bg-gradient-to-br from-purple-900/50 to-indigo-900/50 flex items-center justify-center overflow-hidden">
                                                    {item.imageUrl ? (
                                                        <LazyVideoThumb src={item.imageUrl} />
                                                    ) : (
                                                        <span className="text-2xl">🎬</span>
                                                    )}
                                                </div>
                                            );
                                            if (media === 'audio') return (
                                                <div className="w-14 h-14 rounded-lg shrink-0 border border-[var(--border)] bg-gradient-to-br from-amber-900/50 to-stone-900/50 flex items-center justify-center">
                                                    <span className="text-2xl">🎵</span>
                                                </div>
                                            );
                                            if (media === 'image') return (
                                                <div className="w-14 h-14 rounded-lg overflow-hidden shrink-0 border border-[var(--border)] bg-gradient-to-br from-sky-900/50 to-blue-900/50 flex items-center justify-center">
                                                    {item.imageUrl ? (
                                                        <img
                                                            src={item.imageUrl}
                                                            alt={item.name}
                                                            className="w-full h-full object-cover"
                                                            onError={(e) => {
                                                                (e.currentTarget as HTMLImageElement).style.display = 'none';
                                                            }}
                                                        />
                                                    ) : (
                                                        <span className="text-2xl">🖼️</span>
                                                    )}
                                                </div>
                                            );
                                            // Non-media items (proje, karakter, vb.)
                                            return (
                                                <div
                                                    className="w-10 h-10 rounded-lg shrink-0 flex items-center justify-center"
                                                    style={{ background: `${getTypeColor(item)}20` }}
                                                >
                                                    <span className="text-lg">
                                                        {item.type === 'proje' || item.type === 'session' ? '📁' :
                                                            item.type === 'karakter' || item.type === 'character' ? '👤' :
                                                                item.type === 'lokasyon' || item.type === 'location' ? '📍' :
                                                                    item.type === 'marka' || item.type === 'brand' ? '🏷️' :
                                                                        item.type === 'preset' ? '🧩' : '📄'}
                                                    </span>
                                                </div>
                                            );
                                        })()}
                                        <div className="flex-1 min-w-0">
                                            <div className="font-medium truncate text-sm">
                                                {item.imageUrl ? (item.name.length > 40 ? item.name.slice(0, 40) + '…' : item.name) : item.name}
                                            </div>
                                            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--foreground-muted)" }}>
                                                <span
                                                    className="px-1.5 py-0.5 rounded"
                                                    style={{ background: "var(--card)" }}
                                                >
                                                    {getTypeLabel(item)}
                                                </span>
                                                <span className="flex items-center gap-1">
                                                    <Clock size={10} />
                                                    {getTimeRemaining(item.deletedAt)}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-1 shrink-0">
                                        {/* Restore button */}
                                        <button
                                            onClick={() => onRestore(item)}
                                            className="p-2 rounded-lg hover:bg-green-500/20 transition-colors"
                                            title="Geri Yükle"
                                        >
                                            <RotateCcw size={16} className="text-green-500" />
                                        </button>

                                        {/* Permanent delete button */}
                                        {confirmDelete === item.id ? (
                                            <div className="flex items-center gap-1">
                                                <button
                                                    onClick={() => {
                                                        onPermanentDelete(item.id);
                                                        setConfirmDelete(null);
                                                    }}
                                                    className="px-2 py-1 text-xs rounded bg-red-500 text-white hover:bg-red-600 transition-colors"
                                                >
                                                    Sil
                                                </button>
                                                <button
                                                    onClick={() => setConfirmDelete(null)}
                                                    className="px-2 py-1 text-xs rounded hover:bg-[var(--card)] transition-colors"
                                                >
                                                    İptal
                                                </button>
                                            </div>
                                        ) : (
                                            <button
                                                onClick={() => setConfirmDelete(item.id)}
                                                className="p-2 rounded-lg hover:bg-red-500/20 transition-colors"
                                                title="Kalıcı Sil"
                                            >
                                                <Trash2 size={16} className="text-red-400" />
                                            </button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer info */}
                {items.length > 0 && (
                    <div
                        className="px-4 py-3 border-t flex items-center gap-2 text-xs"
                        style={{ borderColor: "var(--border)", color: "var(--foreground-muted)" }}
                    >
                        <AlertCircle size={14} />
                        <span>Öğeler 3 gün sonra otomatik olarak kalıcı silinir.</span>
                    </div>
                )}
            </div>
        </div>
    );
}
