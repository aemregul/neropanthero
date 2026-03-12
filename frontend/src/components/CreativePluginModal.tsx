"use client";

import { useState } from "react";
import { X, Sparkles, Share2, Download, Check, Users, MapPin, Clock, Camera, Palette, FileJson, Pencil, Trash2 } from "lucide-react";

export interface CreativePlugin {
    id: string;
    name: string;
    description: string;
    author: string;
    isPublic: boolean;
    preview?: string;
    config: {
        character?: {
            id: string;
            name: string;
            isVariable: boolean;
        };
        character_tag?: string;
        location?: {
            id: string;
            name: string;
            settings: string;
        };
        location_tag?: string;
        timeOfDay?: string;
        cameraAngles?: string[];
        style?: string;
        promptTemplate?: string;
        [key: string]: unknown;
    };
    createdAt: Date;
    downloads: number;
    rating: number;
}

// =====================================================
// 1. SAVE PLUGIN MODAL (AI tarafından tetiklenir)
// =====================================================
interface SavePluginModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (name: string, isPublic: boolean) => void;
    suggestedName?: string;
    pluginPreview: Partial<CreativePlugin["config"]>;
}

export function SavePluginModal({ isOpen, onClose, onSave, suggestedName, pluginPreview }: SavePluginModalProps) {
    const [name, setName] = useState(suggestedName || "");
    const [isPublic, setIsPublic] = useState(false);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/70 backdrop-blur-md" onClick={onClose} />

            <div
                className="relative w-full max-w-md rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200"
                style={{ background: "var(--card)", border: "1px solid var(--border)" }}
            >
                {/* Header */}
                <div
                    className="p-5 border-b"
                    style={{ borderColor: "var(--border)", background: "linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, transparent 100%)" }}
                >
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl" style={{ background: "rgba(139, 92, 246, 0.2)" }}>
                            <Sparkles size={24} className="text-purple-500" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold">Plugin Olarak Kaydet</h2>
                            <p className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                                Bu kombinasyonu kaydet ve tekrar kullan
                            </p>
                        </div>
                    </div>
                </div>

                {/* Preview */}
                <div className="p-4 border-b" style={{ borderColor: "var(--border)" }}>
                    <div className="text-xs font-medium mb-2" style={{ color: "var(--foreground-muted)" }}>
                        Algılanan Ayarlar:
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {pluginPreview.character && (
                            <span className="px-2 py-1 text-xs rounded-lg flex items-center gap-1" style={{ background: "var(--background)" }}>
                                <Users size={12} /> {pluginPreview.character.name}
                            </span>
                        )}
                        {pluginPreview.location && (
                            <span className="px-2 py-1 text-xs rounded-lg flex items-center gap-1" style={{ background: "var(--background)" }}>
                                <MapPin size={12} /> {pluginPreview.location.name}
                            </span>
                        )}
                        {pluginPreview.timeOfDay && (
                            <span className="px-2 py-1 text-xs rounded-lg flex items-center gap-1" style={{ background: "var(--background)" }}>
                                <Clock size={12} /> {pluginPreview.timeOfDay}
                            </span>
                        )}
                        {pluginPreview.cameraAngles && pluginPreview.cameraAngles.length > 0 && (
                            <span className="px-2 py-1 text-xs rounded-lg flex items-center gap-1" style={{ background: "var(--background)" }}>
                                <Camera size={12} /> {pluginPreview.cameraAngles.length} açı
                            </span>
                        )}
                        {pluginPreview.style && (
                            <span className="px-2 py-1 text-xs rounded-lg flex items-center gap-1" style={{ background: "var(--background)" }}>
                                <Palette size={12} /> {pluginPreview.style}
                            </span>
                        )}
                    </div>
                </div>

                {/* Form */}
                <div className="p-4 space-y-4">
                    <div>
                        <label className="text-sm font-medium mb-2 block">Plugin Adı</label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="Örn: Mutfak Akşam Seti"
                            className="w-full px-4 py-3 rounded-xl text-sm"
                            style={{ background: "var(--background)", border: "1px solid var(--border)" }}
                            autoFocus
                        />
                    </div>

                    <div
                        className="flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all"
                        style={{ background: isPublic ? "rgba(139, 92, 246, 0.1)" : "var(--background)" }}
                        onClick={() => setIsPublic(!isPublic)}
                    >
                        <div
                            className={`w-5 h-5 rounded flex items-center justify-center transition-all ${isPublic ? "bg-purple-500" : ""}`}
                            style={!isPublic ? { border: "2px solid var(--border)" } : {}}
                        >
                            {isPublic && <Check size={14} className="text-white" />}
                        </div>
                        <div className="flex-1">
                            <div className="font-medium text-sm flex items-center gap-2">
                                <Share2 size={14} />
                                Marketplace'te Paylaş
                            </div>
                            <div className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                                Diğer kullanıcılar bu plugin'i görüp kullanabilir
                            </div>
                        </div>
                    </div>
                </div>

                {/* Actions */}
                <div className="flex gap-3 p-4 border-t" style={{ borderColor: "var(--border)" }}>
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2.5 text-sm rounded-xl hover:bg-[var(--background)] transition-colors"
                        style={{ border: "1px solid var(--border)" }}
                    >
                        İptal
                    </button>
                    <button
                        onClick={() => { onSave(name, isPublic); onClose(); }}
                        disabled={!name.trim()}
                        className="flex-1 px-4 py-2.5 text-sm font-medium rounded-xl transition-colors disabled:opacity-50"
                        style={{ background: "var(--accent)", color: "var(--background)" }}
                    >
                        Kaydet
                    </button>
                </div>
            </div>
        </div>
    );
}

// =====================================================
// 2. PLUGIN DETAIL MODAL (Tıklayınca açılır — Skill kartı)
// =====================================================
interface PluginDetailModalProps {
    isOpen: boolean;
    onClose: () => void;
    plugin: CreativePlugin | null;
    onDelete?: (id: string) => void;
    onUse?: (plugin: CreativePlugin) => void;
    onUpdate?: (plugin: CreativePlugin) => void;
}

export function PluginDetailModal({ isOpen, onClose, plugin, onDelete, onUse, onUpdate }: PluginDetailModalProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [editName, setEditName] = useState("");
    const [editDescription, setEditDescription] = useState("");
    const [editStyle, setEditStyle] = useState("");
    const [editTimeOfDay, setEditTimeOfDay] = useState("");
    const [editCameraAngles, setEditCameraAngles] = useState<string[]>([]);
    const [editPromptTemplate, setEditPromptTemplate] = useState("");
    const [editCharacterTag, setEditCharacterTag] = useState("");
    const [editLocationTag, setEditLocationTag] = useState("");
    const [newAngle, setNewAngle] = useState("");
    const [saving, setSaving] = useState(false);

    if (!isOpen || !plugin) return null;

    const startEditing = () => {
        setEditName(plugin.name);
        setEditDescription(plugin.description || "");
        setEditStyle(plugin.config?.style || "");
        setEditTimeOfDay(plugin.config?.timeOfDay || "");
        setEditCameraAngles([...(plugin.config?.cameraAngles || [])]);
        setEditPromptTemplate(plugin.config?.promptTemplate || "");
        setEditCharacterTag((plugin.config?.character_tag as string) || "");
        setEditLocationTag((plugin.config?.location_tag as string) || "");
        setIsEditing(true);
    };

    const cancelEditing = () => {
        setIsEditing(false);
        setNewAngle("");
    };

    const addCameraAngle = () => {
        const trimmed = newAngle.trim();
        if (trimmed && !editCameraAngles.includes(trimmed)) {
            setEditCameraAngles([...editCameraAngles, trimmed]);
            setNewAngle("");
        }
    };

    const removeCameraAngle = (angle: string) => {
        setEditCameraAngles(editCameraAngles.filter(a => a !== angle));
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const { updatePreset } = await import("@/lib/api");
            await updatePreset(plugin.id, {
                name: editName,
                description: editDescription,
                config: {
                    style: editStyle || undefined,
                    timeOfDay: editTimeOfDay || undefined,
                    cameraAngles: editCameraAngles.length > 0 ? editCameraAngles : undefined,
                    promptTemplate: editPromptTemplate || undefined,
                    character_tag: editCharacterTag || undefined,
                    location_tag: editLocationTag || undefined,
                }
            });

            // Parent'a güncellenen plugin'i bildir
            if (onUpdate) {
                onUpdate({
                    ...plugin,
                    name: editName,
                    description: editDescription,
                    config: {
                        ...plugin.config,
                        style: editStyle || undefined,
                        timeOfDay: editTimeOfDay || undefined,
                        cameraAngles: editCameraAngles.length > 0 ? editCameraAngles : undefined,
                        promptTemplate: editPromptTemplate || undefined,
                        character_tag: editCharacterTag || undefined,
                        location_tag: editLocationTag || undefined,
                    }
                });
            }
            setIsEditing(false);
        } catch (error) {
            console.error("Preset güncelleme hatası:", error);
        } finally {
            setSaving(false);
        }
    };

    const handleDownload = () => {
        const pluginData = {
            name: plugin.name,
            description: plugin.description,
            version: "1.0",
            author: plugin.author,
            createdAt: plugin.createdAt,
            config: plugin.config
        };

        const blob = new Blob([JSON.stringify(pluginData, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${plugin.name.toLowerCase().replace(/\s+/g, "_")}.pepper-preset.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/70 backdrop-blur-md" onClick={onClose} />

            <div
                className="relative w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200"
                style={{ background: "var(--card)", border: "1px solid var(--border)", maxHeight: "85vh" }}
            >
                {/* Header */}
                <div
                    className="p-5 border-b"
                    style={{ borderColor: "var(--border)", background: "linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(99, 102, 241, 0.05) 100%)" }}
                >
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                            <div className="p-2.5 rounded-xl" style={{ background: "rgba(139, 92, 246, 0.2)" }}>
                                <Sparkles size={22} className="text-purple-400" />
                            </div>
                            <div className="flex-1 min-w-0">
                                {isEditing ? (
                                    <input
                                        type="text"
                                        value={editName}
                                        onChange={(e) => setEditName(e.target.value)}
                                        className="w-full text-lg font-bold bg-transparent outline-none px-2 py-1 rounded-lg"
                                        style={{ border: "1px solid var(--accent)" }}
                                        autoFocus
                                    />
                                ) : (
                                    <div className="flex items-center gap-2">
                                        <h2 className="text-lg font-bold truncate">{plugin.name}</h2>
                                        <button
                                            onClick={startEditing}
                                            className="p-1 rounded-lg transition-all opacity-50 hover:opacity-100 hover:bg-white/10"
                                            title="İsmi düzenle"
                                        >
                                            <Pencil size={14} />
                                        </button>
                                    </div>
                                )}
                                <div className="flex items-center gap-2 text-xs mt-0.5" style={{ color: "var(--foreground-muted)" }}>
                                    {plugin.isPublic && (
                                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ background: "rgba(139, 92, 246, 0.25)", color: "#a78bfa" }}>
                                            Topluluk
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                        <button onClick={onClose} className="p-2 rounded-xl hover:bg-white/10 transition-all ml-2">
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Scrollable Content */}
                <div className="overflow-y-auto" style={{ maxHeight: "calc(85vh - 180px)" }}>
                    <div className="p-5 space-y-4">

                        {/* Açıklama */}
                        <div>
                            <div className="flex items-center gap-2 text-xs font-medium mb-2" style={{ color: "var(--foreground-muted)" }}>
                                <FileJson size={12} /> Açıklama
                            </div>
                            {isEditing ? (
                                <textarea
                                    value={editDescription}
                                    onChange={(e) => setEditDescription(e.target.value)}
                                    rows={2}
                                    className="w-full px-3 py-2 rounded-xl text-sm resize-none"
                                    style={{ background: "var(--background)", border: "1px solid var(--border)" }}
                                    placeholder="Preset açıklaması..."
                                />
                            ) : (
                                <p className="text-sm leading-relaxed" style={{ color: "var(--foreground-muted)" }}>
                                    {plugin.description || "Açıklama eklenmemiş"}
                                </p>
                            )}
                        </div>

                        {/* Konfigürasyon Grid */}
                        <div>
                            <div className="flex items-center gap-2 text-xs font-medium mb-3" style={{ color: "var(--foreground-muted)" }}>
                                <Sparkles size={12} /> Sahne Detayları
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                                {/* Karakter Tag */}
                                {plugin.config?.character_tag && (
                                    <div className="p-3 rounded-xl" style={{ background: "var(--background)" }}>
                                        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider mb-1.5" style={{ color: "var(--foreground-muted)" }}>
                                            <Users size={10} /> Karakter
                                        </div>
                                        <div className="text-sm font-medium">{String(plugin.config.character_tag)}</div>
                                    </div>
                                )}

                                {/* Lokasyon Tag */}
                                {plugin.config?.location_tag && (
                                    <div className="p-3 rounded-xl" style={{ background: "var(--background)" }}>
                                        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider mb-1.5" style={{ color: "var(--foreground-muted)" }}>
                                            <MapPin size={10} /> Lokasyon
                                        </div>
                                        <div className="text-sm font-medium">{String(plugin.config.location_tag)}</div>
                                    </div>
                                )}

                                {/* Stil */}
                                <div className="p-3 rounded-xl" style={{ background: "var(--background)" }}>
                                    <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider mb-1.5" style={{ color: "var(--foreground-muted)" }}>
                                        <Palette size={10} /> Stil
                                    </div>
                                    {isEditing ? (
                                        <input
                                            value={editStyle}
                                            onChange={(e) => setEditStyle(e.target.value)}
                                            className="w-full text-sm bg-transparent outline-none px-1 py-0.5 rounded"
                                            style={{ border: "1px solid var(--border)" }}
                                            placeholder="realistic, anime..."
                                        />
                                    ) : (
                                        <div className="text-sm font-medium">{plugin.config?.style || "—"}</div>
                                    )}
                                </div>

                                {/* Zaman */}
                                <div className="p-3 rounded-xl" style={{ background: "var(--background)" }}>
                                    <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider mb-1.5" style={{ color: "var(--foreground-muted)" }}>
                                        <Clock size={10} /> Zaman
                                    </div>
                                    {isEditing ? (
                                        <input
                                            value={editTimeOfDay}
                                            onChange={(e) => setEditTimeOfDay(e.target.value)}
                                            className="w-full text-sm bg-transparent outline-none px-1 py-0.5 rounded"
                                            style={{ border: "1px solid var(--border)" }}
                                            placeholder="Gün batımı, gece..."
                                        />
                                    ) : (
                                        <div className="text-sm font-medium">{plugin.config?.timeOfDay || "—"}</div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Kamera Açıları — chip listesi */}
                        <div>
                            <div className="flex items-center gap-2 text-xs font-medium mb-2" style={{ color: "var(--foreground-muted)" }}>
                                <Camera size={12} /> Kamera Açıları
                            </div>
                            <div className="p-3 rounded-xl" style={{ background: "var(--background)" }}>
                                {isEditing ? (
                                    <>
                                        <div className="flex flex-wrap gap-1.5 mb-2">
                                            {editCameraAngles.map((angle, i) => (
                                                <span
                                                    key={i}
                                                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg group"
                                                    style={{ background: "rgba(139, 92, 246, 0.15)", color: "#a78bfa" }}
                                                >
                                                    {angle}
                                                    <button
                                                        onClick={() => removeCameraAngle(angle)}
                                                        className="opacity-50 hover:opacity-100 transition-opacity"
                                                    >
                                                        <X size={10} />
                                                    </button>
                                                </span>
                                            ))}
                                        </div>
                                        <div className="flex gap-2">
                                            <input
                                                value={newAngle}
                                                onChange={(e) => setNewAngle(e.target.value)}
                                                onKeyDown={(e) => e.key === "Enter" && addCameraAngle()}
                                                className="flex-1 text-xs px-2.5 py-1.5 rounded-lg bg-transparent"
                                                style={{ border: "1px solid var(--border)" }}
                                                placeholder="Close-up, Wide Shot..."
                                            />
                                            <button
                                                onClick={addCameraAngle}
                                                className="px-3 py-1.5 text-xs rounded-lg font-medium"
                                                style={{ background: "rgba(139, 92, 246, 0.2)", color: "#a78bfa" }}
                                            >
                                                + Ekle
                                            </button>
                                        </div>
                                    </>
                                ) : (
                                    <div className="flex flex-wrap gap-1.5">
                                        {plugin.config?.cameraAngles && plugin.config.cameraAngles.length > 0 ? (
                                            plugin.config.cameraAngles.map((angle, i) => (
                                                <span
                                                    key={i}
                                                    className="px-2.5 py-1 text-xs rounded-lg"
                                                    style={{ background: "rgba(139, 92, 246, 0.1)", color: "#a78bfa" }}
                                                >
                                                    {angle}
                                                </span>
                                            ))
                                        ) : (
                                            <span className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                                                Henüz eklenmedi
                                            </span>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Karakter & Lokasyon Tag'leri */}
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <div className="flex items-center gap-2 text-xs font-medium mb-2" style={{ color: "var(--foreground-muted)" }}>
                                    <Users size={12} /> Karakter Tag
                                </div>
                                <div className="p-3 rounded-xl" style={{ background: "var(--background)" }}>
                                    {isEditing ? (
                                        <input
                                            value={editCharacterTag}
                                            onChange={(e) => setEditCharacterTag(e.target.value.replace(/^@/, ''))}
                                            className="w-full text-xs bg-transparent outline-none"
                                            style={{ border: "1px solid var(--border)", padding: "6px 8px", borderRadius: "8px" }}
                                            placeholder="emre, johny..."
                                        />
                                    ) : (
                                        <span className="text-xs" style={{ color: (plugin.config?.character_tag as string) ? "var(--accent)" : "var(--foreground-muted)" }}>
                                            {(plugin.config?.character_tag as string) ? `@${plugin.config.character_tag}` : "—"}
                                        </span>
                                    )}
                                </div>
                            </div>
                            <div>
                                <div className="flex items-center gap-2 text-xs font-medium mb-2" style={{ color: "var(--foreground-muted)" }}>
                                    <MapPin size={12} /> Lokasyon Tag
                                </div>
                                <div className="p-3 rounded-xl" style={{ background: "var(--background)" }}>
                                    {isEditing ? (
                                        <input
                                            value={editLocationTag}
                                            onChange={(e) => setEditLocationTag(e.target.value.replace(/^@/, ''))}
                                            className="w-full text-xs bg-transparent outline-none"
                                            style={{ border: "1px solid var(--border)", padding: "6px 8px", borderRadius: "8px" }}
                                            placeholder="sahil, orman..."
                                        />
                                    ) : (
                                        <span className="text-xs" style={{ color: (plugin.config?.location_tag as string) ? "var(--accent)" : "var(--foreground-muted)" }}>
                                            {(plugin.config?.location_tag as string) ? `@${plugin.config.location_tag}` : "—"}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Prompt Şablonu */}
                        <div>
                            <div className="flex items-center gap-2 text-xs font-medium mb-2" style={{ color: "var(--foreground-muted)" }}>
                                <FileJson size={12} /> Prompt Şablonu
                            </div>
                            <div className="p-3 rounded-xl" style={{ background: "var(--background)" }}>
                                {isEditing ? (
                                    <textarea
                                        value={editPromptTemplate}
                                        onChange={(e) => setEditPromptTemplate(e.target.value)}
                                        rows={3}
                                        className="w-full text-xs font-mono bg-transparent outline-none resize-none"
                                        style={{ border: "1px solid var(--border)", padding: "8px", borderRadius: "8px" }}
                                        placeholder="cinematic photo, {character}, sunset..."
                                    />
                                ) : (
                                    <code className="text-xs font-mono block leading-relaxed" style={{ color: "var(--accent)" }}>
                                        {plugin.config?.promptTemplate || "Şablon eklenmemiş"}
                                    </code>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 p-4 border-t" style={{ borderColor: "var(--border)" }}>
                    {isEditing ? (
                        <>
                            <button
                                onClick={cancelEditing}
                                className="px-4 py-2.5 text-sm rounded-xl hover:bg-white/5 transition-colors"
                                style={{ border: "1px solid var(--border)" }}
                            >
                                İptal
                            </button>
                            <div className="flex-1" />
                            <button
                                onClick={handleSave}
                                disabled={saving || !editName.trim()}
                                className="px-6 py-2.5 text-sm font-medium rounded-xl transition-colors flex items-center gap-2 disabled:opacity-50"
                                style={{ background: "var(--accent)", color: "var(--background)" }}
                            >
                                {saving ? (
                                    <span className="animate-spin">⏳</span>
                                ) : (
                                    <Check size={16} />
                                )}
                                Kaydet
                            </button>
                        </>
                    ) : (
                        <>
                            <button
                                onClick={handleDownload}
                                className="flex items-center gap-2 px-3 py-2.5 text-sm rounded-xl hover:bg-white/5 transition-colors"
                                style={{ border: "1px solid var(--border)" }}
                                title="JSON olarak indir"
                            >
                                <Download size={14} />
                            </button>

                            <button
                                onClick={startEditing}
                                className="flex items-center gap-2 px-3 py-2.5 text-sm rounded-xl hover:bg-white/5 transition-colors"
                                style={{ border: "1px solid var(--border)" }}
                                title="Düzenle"
                            >
                                <Pencil size={14} />
                                <span>Düzenle</span>
                            </button>

                            {onDelete && (
                                <button
                                    onClick={() => { onDelete(plugin.id); onClose(); }}
                                    className="px-3 py-2.5 text-sm rounded-xl hover:bg-red-500/20 text-red-400 transition-colors"
                                    title="Sil"
                                >
                                    <Trash2 size={14} />
                                </button>
                            )}

                            <div className="flex-1" />

                            {onUse && (
                                <button
                                    onClick={() => { onUse(plugin); onClose(); }}
                                    className="px-6 py-2.5 text-sm font-medium rounded-xl transition-colors flex items-center gap-2"
                                    style={{ background: "var(--accent)", color: "var(--background)" }}
                                >
                                    <Sparkles size={16} />
                                    Kullan
                                </button>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

