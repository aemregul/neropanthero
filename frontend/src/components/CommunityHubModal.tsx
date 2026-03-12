"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Search, Star, Download, TrendingUp, Clock, Users, Loader2, Globe, Pin, Plus, Check, Eye, EyeOff, Sparkles } from "lucide-react";
import { getMarketplacePlugins, getPresets, publishPlugin, installMarketplacePlugin, type MarketplacePlugin, type PresetData } from "@/lib/api";
import { useToast } from "./ToastProvider";

interface Project {
    id: string;
    name: string;
    active?: boolean;
}

interface CommunityHubModalProps {
    isOpen: boolean;
    onClose: () => void;
    projects: Project[];
    activeProjectId?: string;
    sessionId?: string | null;
}

type TabMode = "community" | "my-presets";
type SortMode = "downloads" | "rating" | "recent";

export function CommunityHubModal({ isOpen, onClose, projects, activeProjectId, sessionId }: CommunityHubModalProps) {
    const [activeTab, setActiveTab] = useState<TabMode>("community");
    const [searchQuery, setSearchQuery] = useState("");
    const [sortBy, setSortBy] = useState<SortMode>("downloads");
    const [communityPlugins, setCommunityPlugins] = useState<MarketplacePlugin[]>([]);
    const [myPresets, setMyPresets] = useState<PresetData[]>([]);
    const [loading, setLoading] = useState(false);
    const [installing, setInstalling] = useState<string | null>(null);
    const [publishing, setPublishing] = useState<string | null>(null);
    const [selectingPluginId, setSelectingPluginId] = useState<string | null>(null);
    const toast = useToast();

    // Fetch community presets
    const fetchCommunity = useCallback(async () => {
        setLoading(true);
        try {
            const data = await getMarketplacePlugins(sortBy, "all", searchQuery);
            setCommunityPlugins(data);
        } catch (err) {
            console.error("Community fetch error:", err);
        } finally {
            setLoading(false);
        }
    }, [sortBy, searchQuery]);

    // Fetch my presets
    const fetchMyPresets = useCallback(async () => {
        if (!sessionId) return;
        setLoading(true);
        try {
            const data = await getPresets(sessionId);
            setMyPresets(data);
        } catch (err) {
            console.error("My presets fetch error:", err);
        } finally {
            setLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        if (!isOpen) return;
        if (activeTab === "community") {
            fetchCommunity();
        } else {
            fetchMyPresets();
        }
    }, [isOpen, activeTab, fetchCommunity, fetchMyPresets]);

    // Debounce search
    useEffect(() => {
        if (!isOpen || activeTab !== "community") return;
        const timer = setTimeout(() => fetchCommunity(), 300);
        return () => clearTimeout(timer);
    }, [searchQuery]); // eslint-disable-line react-hooks/exhaustive-deps

    // Publish / Unpublish
    const handlePublish = async (presetId: string) => {
        setPublishing(presetId);
        try {
            const result = await publishPlugin(presetId);
            if (result.success) {
                setMyPresets(prev => prev.map(p =>
                    p.id === presetId ? { ...p, is_public: !p.is_public } : p
                ));
                const preset = myPresets.find(p => p.id === presetId);
                const isNowPublic = !preset?.is_public;
                toast.success(isNowPublic ? "Preset toplulukta yayınlandı!" : "Preset yayından kaldırıldı");
            }
        } catch {
            toast.error("İşlem başarısız");
        } finally {
            setPublishing(null);
        }
    };

    // Install to project
    const handleInstall = async (pluginId: string, projectId: string, projectName: string) => {
        setInstalling(pluginId);
        try {
            const result = await installMarketplacePlugin(pluginId, projectId);
            if (result.success) {
                toast.success(`Preset "${projectName}" projesine eklendi!`);
            } else if (result.error === "already_installed") {
                toast.error(result.message || "Bu preset zaten ekli");
            } else {
                toast.error(result.message || "Yükleme başarısız");
            }
        } catch {
            toast.error("Bağlantı hatası");
        } finally {
            setInstalling(null);
            setSelectingPluginId(null);
        }
    };

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString('tr-TR', {
            day: 'numeric', month: 'short', year: 'numeric'
        });
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/70 backdrop-blur-md" onClick={() => { setSelectingPluginId(null); onClose(); }} />

            <div
                className="relative w-full max-w-5xl max-h-[85vh] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
                style={{ background: "var(--card)", border: "1px solid var(--border)" }}
            >
                {/* Header */}
                <div
                    className="flex items-center justify-between p-5 border-b shrink-0"
                    style={{ borderColor: "var(--border)", background: "linear-gradient(135deg, rgba(167, 139, 250, 0.08) 0%, rgba(139, 92, 246, 0.05) 100%)" }}
                >
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl" style={{ background: "rgba(167, 139, 250, 0.15)" }}>
                            <Users size={24} className="text-purple-400" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">Topluluk Hub&apos;ı</h2>
                            <p className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                                Preset&apos;leri keşfet ve paylaş
                            </p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 rounded-xl hover:bg-[var(--background)] transition-all">
                        <X size={20} />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex items-center gap-1 px-5 py-3 border-b shrink-0" style={{ borderColor: "var(--border)" }}>
                    <button
                        onClick={() => setActiveTab("community")}
                        className={`px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-all ${
                            activeTab === "community"
                                ? "text-white"
                                : "hover:bg-[var(--background)]"
                        }`}
                        style={activeTab === "community" ? { background: "var(--accent)" } : {}}
                    >
                        <Globe size={16} /> Topluluk
                    </button>
                    <button
                        onClick={() => setActiveTab("my-presets")}
                        className={`px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 transition-all ${
                            activeTab === "my-presets"
                                ? "text-white"
                                : "hover:bg-[var(--background)]"
                        }`}
                        style={activeTab === "my-presets" ? { background: "var(--accent)" } : {}}
                    >
                        <Pin size={16} /> Preset&apos;lerim
                        {myPresets.length > 0 && (
                            <span className="px-1.5 py-0.5 text-[10px] rounded-full font-bold"
                                style={{ background: "rgba(167, 139, 250, 0.2)", color: "#a78bfa" }}>
                                {myPresets.length}
                            </span>
                        )}
                    </button>
                </div>

                {/* Search & Sort (Community tab only) */}
                {activeTab === "community" && (
                    <div className="flex items-center gap-3 px-5 py-3 border-b shrink-0" style={{ borderColor: "var(--border)" }}>
                        <div className="flex-1 relative">
                            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--foreground-muted)" }} />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="Preset ara..."
                                className="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm"
                                style={{ background: "var(--background)", border: "1px solid var(--border)" }}
                            />
                        </div>
                        <div className="flex items-center gap-1 p-1 rounded-xl" style={{ background: "var(--background)" }}>
                            {([
                                { sort: "downloads" as SortMode, icon: <TrendingUp size={12} />, label: "Popüler" },
                                { sort: "rating" as SortMode, icon: <Star size={12} />, label: "En İyi" },
                                { sort: "recent" as SortMode, icon: <Clock size={12} />, label: "Yeni" },
                            ]).map((fb) => (
                                <button
                                    key={fb.sort}
                                    onClick={() => setSortBy(fb.sort)}
                                    className={`px-3 py-1.5 text-xs rounded-lg flex items-center gap-1 transition-all ${
                                        sortBy === fb.sort ? "text-white" : ""
                                    }`}
                                    style={sortBy === fb.sort ? { background: "var(--accent)" } : {}}
                                >
                                    {fb.icon} {fb.label}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-5">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-16 gap-3">
                            <Loader2 size={32} className="animate-spin text-purple-400" />
                            <p className="text-sm" style={{ color: "var(--foreground-muted)" }}>Yükleniyor...</p>
                        </div>
                    ) : activeTab === "community" ? (
                        /* ===== COMMUNITY TAB ===== */
                        communityPlugins.length === 0 ? (
                            <div className="text-center py-16">
                                <Users size={48} className="mx-auto mb-4 opacity-20" />
                                <p className="text-lg font-medium mb-1">Henüz preset yok</p>
                                <p className="text-sm" style={{ color: "var(--foreground-muted)" }}>
                                    İlk preset&apos;ini chat&apos;te oluştur ve toplulukla paylaş!
                                </p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {communityPlugins.map((plugin) => (
                                    <div
                                        key={plugin.id}
                                        className="p-5 rounded-xl transition-all hover:shadow-lg relative group"
                                        style={{ background: "var(--background)", border: "1px solid var(--border)" }}
                                    >
                                        {/* Header */}
                                        <div className="flex items-start gap-3 mb-3">
                                            <span className="text-2xl">{plugin.icon}</span>
                                            <div className="flex-1 min-w-0">
                                                <h3 className="font-semibold text-sm truncate">{plugin.name}</h3>
                                                <div className="flex items-center gap-2 text-xs mt-1 flex-wrap" style={{ color: "var(--foreground-muted)" }}>
                                                    <span className="flex items-center gap-1">
                                                        <Users size={10} /> {plugin.author}
                                                    </span>
                                                    <span>•</span>
                                                    <span className="flex items-center gap-1">
                                                        <Star size={10} className="text-yellow-500" /> {plugin.rating}
                                                    </span>
                                                    <span>•</span>
                                                    <span className="flex items-center gap-1">
                                                        <Download size={10} /> {plugin.downloads.toLocaleString()}
                                                    </span>
                                                    <span>•</span>
                                                    <span>{formatDate(plugin.created_at)}</span>
                                                </div>
                                            </div>
                                            {/* Source badge */}
                                            <span
                                                className="px-2 py-0.5 text-[10px] rounded-full font-medium shrink-0"
                                                style={{
                                                    background: plugin.source === "official"
                                                        ? "rgba(139, 92, 246, 0.15)"
                                                        : "rgba(74, 222, 128, 0.15)",
                                                    color: plugin.source === "official" ? "#a78bfa" : "#4ade80",
                                                }}
                                            >
                                                {plugin.source === "official" ? "🏪 Resmi" : "👤 Topluluk"}
                                            </span>
                                        </div>

                                        {/* Description */}
                                        <p className="text-xs mb-3 line-clamp-2" style={{ color: "var(--foreground-muted)" }}>
                                            {plugin.description}
                                        </p>

                                        {/* Tags */}
                                        <div className="flex flex-wrap gap-1 mb-4">
                                            {plugin.style && (
                                                <span className="px-2 py-0.5 text-xs rounded"
                                                    style={{ background: `${plugin.color}20`, color: plugin.color }}>
                                                    {plugin.style}
                                                </span>
                                            )}
                                            {Array.isArray(plugin.config?.cameraAngles) && (plugin.config.cameraAngles as string[]).slice(0, 2).map((angle: string, i: number) => (
                                                <span key={i} className="px-2 py-0.5 text-xs rounded" style={{ background: "var(--card)" }}>
                                                    {angle}
                                                </span>
                                            ))}
                                        </div>

                                        {/* Install button */}
                                        <button
                                            onClick={() => setSelectingPluginId(plugin.id)}
                                            className="w-full py-2 text-sm font-medium rounded-lg transition-all flex items-center justify-center gap-2 hover:opacity-90"
                                            style={{ background: "var(--accent)", color: "var(--background)" }}
                                        >
                                            <Plus size={14} /> Projeye Ekle
                                        </button>

                                        {/* Project Selector */}
                                        {selectingPluginId === plugin.id && (
                                            <div
                                                className="absolute bottom-0 left-0 right-0 rounded-xl shadow-2xl overflow-hidden z-20 animate-in fade-in slide-in-from-bottom-3 duration-200"
                                                style={{
                                                    background: "var(--card)",
                                                    border: "1px solid var(--border)",
                                                    boxShadow: "0 -8px 32px rgba(0,0,0,0.4)"
                                                }}
                                            >
                                                <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
                                                    <span className="text-xs font-semibold flex items-center gap-2">📁 Proje Seç</span>
                                                    <button onClick={(e) => { e.stopPropagation(); setSelectingPluginId(null); }}
                                                        className="p-1 rounded-lg hover:bg-[var(--background)]">
                                                        <X size={14} />
                                                    </button>
                                                </div>
                                                <div className="max-h-48 overflow-y-auto">
                                                    {projects.length === 0 ? (
                                                        <div className="px-4 py-6 text-center text-xs" style={{ color: "var(--foreground-muted)" }}>
                                                            Henüz proje yok
                                                        </div>
                                                    ) : (
                                                        projects.map((project) => (
                                                            <button
                                                                key={project.id}
                                                                onClick={(e) => { e.stopPropagation(); handleInstall(plugin.id, project.id, project.name); }}
                                                                disabled={installing === plugin.id}
                                                                className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-all hover:bg-[var(--background)] disabled:opacity-50"
                                                                style={{ borderBottom: "1px solid var(--border)" }}
                                                            >
                                                                <span className="text-lg">📁</span>
                                                                <div className="flex-1 min-w-0">
                                                                    <div className="text-sm font-medium truncate">{project.name}</div>
                                                                    {project.id === activeProjectId && (
                                                                        <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                                                                            style={{ background: "rgba(167, 139, 250, 0.15)", color: "#a78bfa" }}>Aktif</span>
                                                                    )}
                                                                </div>
                                                                {installing === plugin.id && <Loader2 size={14} className="animate-spin text-purple-400 shrink-0" />}
                                                            </button>
                                                        ))
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )
                    ) : (
                        /* ===== MY PRESETS TAB ===== */
                        myPresets.length === 0 ? (
                            <div className="text-center py-16">
                                <Sparkles size={48} className="mx-auto mb-4 opacity-20 text-purple-400" />
                                <p className="text-lg font-medium mb-1">Henüz preset&apos;in yok</p>
                                <p className="text-sm" style={{ color: "var(--foreground-muted)" }}>
                                    Chat&apos;te ✨ butonuna tıklayarak bir preset oluştur!
                                </p>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {myPresets.map((preset) => (
                                    <div
                                        key={preset.id}
                                        className="p-4 rounded-xl flex items-center gap-4 transition-all hover:shadow-md"
                                        style={{ background: "var(--background)", border: "1px solid var(--border)" }}
                                    >
                                        {/* Icon */}
                                        <span className="text-2xl shrink-0">{preset.icon || "🎨"}</span>

                                        {/* Info */}
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <h3 className="font-semibold text-sm truncate">{preset.name}</h3>
                                                {preset.is_public && (
                                                    <span className="px-2 py-0.5 text-[10px] rounded-full font-medium shrink-0"
                                                        style={{ background: "rgba(167, 139, 250, 0.15)", color: "#a78bfa" }}>
                                                        <Check size={8} className="inline mr-0.5" /> Yayında
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-xs mt-0.5 truncate" style={{ color: "var(--foreground-muted)" }}>
                                                {preset.description || "Açıklama yok"}
                                            </p>
                                            <div className="flex items-center gap-3 mt-1.5 text-xs" style={{ color: "var(--foreground-muted)" }}>
                                                {preset.style && (
                                                    <span className="px-2 py-0.5 rounded text-[10px]" style={{ background: "var(--card)" }}>
                                                        {preset.style}
                                                    </span>
                                                )}
                                                <span>{formatDate(preset.created_at)}</span>
                                                {preset.downloads !== undefined && (
                                                    <span className="flex items-center gap-1">
                                                        <Download size={10} /> {preset.downloads}
                                                    </span>
                                                )}
                                            </div>
                                        </div>

                                        {/* Publish / Unpublish Button */}
                                        <button
                                            onClick={() => handlePublish(preset.id)}
                                            disabled={publishing === preset.id}
                                            className="px-4 py-2 text-xs font-medium rounded-lg transition-all flex items-center gap-2 shrink-0 hover:opacity-90 disabled:opacity-50"
                                            style={{
                                                background: preset.is_public
                                                    ? "rgba(239, 68, 68, 0.1)"
                                                    : "rgba(167, 139, 250, 0.15)",
                                                border: preset.is_public
                                                    ? "1px solid rgba(239, 68, 68, 0.3)"
                                                    : "1px solid rgba(167, 139, 250, 0.3)",
                                                color: preset.is_public ? "#ef4444" : "#a78bfa"
                                            }}
                                        >
                                            {publishing === preset.id ? (
                                                <Loader2 size={14} className="animate-spin" />
                                            ) : preset.is_public ? (
                                                <><EyeOff size={14} /> Yayından Kaldır</>
                                            ) : (
                                                <><Eye size={14} /> Toplulukta Yayınla</>
                                            )}
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )
                    )}
                </div>
            </div>
        </div>
    );
}
