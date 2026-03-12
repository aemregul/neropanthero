"use client";

import { useState, useEffect, useRef } from "react";
import { X, ImageIcon, Search, Trash2, Download, Copy, ExternalLink, Grid, List, Pencil, Check } from "lucide-react";
import { getEntities, deleteEntity, updateEntityName, Entity } from "@/lib/api";
import { useToast } from "./ToastProvider";

interface SavedImagesModalProps {
    isOpen: boolean;
    onClose: () => void;
    sessionId?: string | null;
    onRefresh?: () => void;  // Sidebar refresh için
    onItemDeleted?: (id: string, name: string, imageUrl: string, mediaType: 'image' | 'video' | 'audio') => void;
}

interface SavedImage {
    id: string;
    name: string;
    imageUrl: string;
    createdAt?: Date;
    type: 'image' | 'video' | 'audio';
}

export function SavedImagesModal({ isOpen, onClose, sessionId, onRefresh, onItemDeleted }: SavedImagesModalProps) {
    const [images, setImages] = useState<SavedImage[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");
    const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
    const [selectedImage, setSelectedImage] = useState<SavedImage | null>(null);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editingName, setEditingName] = useState("");
    const editInputRef = useRef<HTMLInputElement>(null);
    const toast = useToast();
    const [isDragging, setIsDragging] = useState(false);

    // Fetch saved images from entities
    useEffect(() => {
        const fetchImages = async () => {
            if (!isOpen || !sessionId) return;

            setIsLoading(true);
            try {
                const entities = await getEntities(sessionId);
                const savedImages: SavedImage[] = entities
                    .filter((e: Entity) => e.entity_type === 'wardrobe' && e.reference_image_url)
                    .map((e: Entity) => {
                        const isVideo = e.reference_image_url?.match(/\.(mp4|mov|webm)(\?.*)?$/i);
                        const isAudio = e.reference_image_url?.match(/\.(wav|mp3|ogg|aac|flac)(\?.*)?$/i);
                        return {
                            id: e.id,
                            name: e.name || e.tag || 'Untitled',
                            imageUrl: e.reference_image_url!,
                            createdAt: e.created_at ? new Date(e.created_at) : undefined,
                            type: isAudio ? 'audio' : isVideo ? 'video' : 'image'
                        };
                    });
                setImages(savedImages);
            } catch (error) {
                console.error('Saved images fetch error:', error);
                setImages([]);
            } finally {
                setIsLoading(false);
            }
        };

        fetchImages();
    }, [isOpen, sessionId]);

    // Filter images by search query
    const filteredImages = images.filter(img =>
        img.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Delete image
    const handleDelete = async (imageId: string) => {
        const image = images.find(img => img.id === imageId);
        const success = await deleteEntity(imageId);
        if (success) {
            setImages(images.filter(img => img.id !== imageId));
            setSelectedImage(null);
            onRefresh?.();
            // Trash state'ini anında güncelle
            if (image) {
                onItemDeleted?.(imageId, image.name, image.imageUrl, image.type);
            }
            toast.success('Görsel çöp kutusuna taşındı');
        } else {
            toast.error('Silme başarısız');
        }
    };

    // Start editing name
    const startEditing = (image: SavedImage) => {
        setEditingId(image.id);
        setEditingName(image.name);
        setTimeout(() => editInputRef.current?.focus(), 50);
    };

    // Save renamed name
    const handleRename = async () => {
        if (!editingId || !editingName.trim()) {
            setEditingId(null);
            return;
        }

        const result = await updateEntityName(editingId, editingName.trim());
        if (result) {
            setImages(images.map(img =>
                img.id === editingId ? { ...img, name: editingName.trim() } : img
            ));
            onRefresh?.();
            toast.success('İsim güncellendi');
        } else {
            toast.error('Güncelleme başarısız');
        }
        setEditingId(null);
    };

    // Copy URL to clipboard
    const handleCopyUrl = async (url: string) => {
        try {
            await navigator.clipboard.writeText(url);
            toast.success('URL kopyalandı!');
        } catch {
            toast.error('Kopyalama başarısız');
        }
    };

    // Download image
    const handleDownload = async (image: SavedImage) => {
        try {
            const response = await fetch(image.imageUrl);
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${image.name.replace(/\s+/g, '_')}.${image.type === 'video' ? 'mp4' : image.type === 'audio' ? 'wav' : 'png'}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            toast.success('İndirme başladı');
        } catch {
            toast.error('İndirme başarısız');
        }
    };

    // Drag start for chat drop
    const handleDragStart = (e: React.DragEvent, image: SavedImage) => {
        e.dataTransfer.setData('text/plain', image.imageUrl);
        e.dataTransfer.setData('application/x-asset-url', image.imageUrl);
        e.dataTransfer.setData('application/x-asset-type', image.type); // 'video' | 'image'
        e.dataTransfer.effectAllowed = 'copy';

        // Hide modal content to allow dropping on chat
        setTimeout(() => setIsDragging(true), 0);
    };

    const handleDragEnd = () => {
        setIsDragging(false);
        onClose(); // Panel'i kapat (Kullanıcı isteği: "eklendiğinde panel geri açılıyor o işlemi engelleyelim")
    };

    if (!isOpen) return null;

    return (
        <div className={`fixed inset-0 z-50 flex items-center justify-center transition-all duration-200 ${isDragging ? 'pointer-events-none opacity-0' : 'opacity-100'}`}>
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal */}
            <div
                className="relative w-[90vw] max-w-6xl h-[85vh] rounded-2xl overflow-hidden shadow-2xl flex flex-col"
                style={{ background: "var(--background)" }}
            >
                {/* Header */}
                <header
                    className="px-6 py-4 border-b flex items-center justify-between shrink-0"
                    style={{ borderColor: "var(--border)" }}
                >
                    <div className="flex items-center gap-3">
                        <div
                            className="p-2.5 rounded-xl"
                            style={{ background: "linear-gradient(135deg, var(--accent) 0%, #8b5cf6 100%)" }}
                        >
                            <ImageIcon size={24} className="text-white" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">Kaydedilen Medya Varlıkları</h2>
                            <p className="text-sm" style={{ color: "var(--foreground-muted)" }}>
                                {images.length} medya kayıtlı
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* View Mode Toggle */}
                        <div className="flex items-center gap-1 p-1 rounded-lg" style={{ background: "var(--card)" }}>
                            <button
                                onClick={() => setViewMode("grid")}
                                className={`p-2 rounded-md transition-colors ${viewMode === "grid" ? "bg-[var(--accent)]" : "hover:bg-[var(--border)]"}`}
                                title="Grid görünümü"
                            >
                                <Grid size={18} className={viewMode === "grid" ? "text-white" : ""} />
                            </button>
                            <button
                                onClick={() => setViewMode("list")}
                                className={`p-2 rounded-md transition-colors ${viewMode === "list" ? "bg-[var(--accent)]" : "hover:bg-[var(--border)]"}`}
                                title="Liste görünümü"
                            >
                                <List size={18} className={viewMode === "list" ? "text-white" : ""} />
                            </button>
                        </div>

                        {/* Search */}
                        <div className="relative">
                            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--foreground-muted)" }} />
                            <input
                                type="text"
                                placeholder="Medya ara..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-10 pr-4 py-2 rounded-lg border w-64"
                                style={{
                                    background: "var(--card)",
                                    borderColor: "var(--border)",
                                    color: "var(--foreground)"
                                }}
                            />
                        </div>

                        {/* Close */}
                        <button
                            onClick={onClose}
                            className="p-2 rounded-lg hover:bg-[var(--card)] transition-colors"
                        >
                            <X size={22} />
                        </button>
                    </div>
                </header>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {isLoading ? (
                        <div className="flex items-center justify-center h-full">
                            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2" style={{ borderColor: "var(--accent)" }} />
                        </div>
                    ) : filteredImages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-center">
                            <ImageIcon size={64} style={{ color: "var(--foreground-muted)" }} className="mb-4 opacity-50" />
                            <h3 className="text-lg font-medium mb-2">Henüz medya yok</h3>
                            <p style={{ color: "var(--foreground-muted)" }}>
                                {searchQuery ? "Arama sonucu bulunamadı" : "Oluşturduğun medya varlıklarını buraya kaydet!"}
                            </p>
                        </div>
                    ) : viewMode === "grid" ? (
                        /* Grid View */
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                            {filteredImages.map((image) => (
                                <div
                                    key={image.id}
                                    draggable
                                    onDragStart={(e) => handleDragStart(e, image)}
                                    onDragEnd={handleDragEnd}
                                    onClick={() => setSelectedImage(image)}
                                    className="group relative aspect-square rounded-xl overflow-hidden cursor-pointer border-2 border-transparent hover:border-[var(--accent)] transition-all shadow-md hover:shadow-xl"
                                    style={{ background: "var(--card)" }}
                                >
                                    {image.type === 'video' ? (
                                        <video
                                            src={image.imageUrl}
                                            className="w-full h-full object-cover transition-transform group-hover:scale-105"
                                            muted
                                            loop
                                            playsInline
                                            onMouseOver={e => {
                                                const p = e.currentTarget.play();
                                                if (p !== undefined) {
                                                    p.catch(error => {
                                                        if (error.name !== 'AbortError') console.error("Video play error:", error);
                                                    });
                                                }
                                            }}
                                            onMouseOut={e => {
                                                e.currentTarget.pause();
                                                e.currentTarget.currentTime = 0;
                                            }}
                                        />
                                    ) : image.type === 'audio' ? (
                                        <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-emerald-900/40 to-purple-900/40 p-3">
                                            <span className="text-3xl mb-2">🎵</span>
                                            <span className="text-xs text-white/70 text-center truncate w-full">{image.name}</span>
                                            <audio src={image.imageUrl} controls className="w-full mt-2" style={{ height: '28px' }} onClick={e => e.stopPropagation()} />
                                        </div>
                                    ) : (
                                        <img
                                            src={image.imageUrl}
                                            alt={image.name}
                                            className="w-full h-full object-cover transition-transform group-hover:scale-105"
                                        />
                                    )}

                                    {/* Overlay on hover */}
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                                        <div className="absolute bottom-0 left-0 right-0 p-3">
                                            <p className="text-white text-sm font-medium truncate">{image.name}</p>
                                            <p className="text-white/60 text-xs mt-0.5">Sürükle → Chat'e bırak</p>
                                        </div>
                                    </div>

                                    {/* Quick actions */}
                                    <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleCopyUrl(image.imageUrl); }}
                                            className="p-1.5 rounded-lg bg-black/60 hover:bg-black/80 transition-colors"
                                            title="URL Kopyala (Chat'e sürükleyin)"
                                        >
                                            <Copy size={14} className="text-white" />
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDelete(image.id); }}
                                            className="p-1.5 rounded-lg bg-red-500/80 hover:bg-red-500 transition-colors"
                                            title="Sil"
                                        >
                                            <Trash2 size={14} className="text-white" />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        /* List View */
                        <div className="space-y-2">
                            {filteredImages.map((image) => (
                                <div
                                    key={image.id}
                                    draggable
                                    onDragStart={(e) => handleDragStart(e, image)}
                                    onDragEnd={handleDragEnd}
                                    onClick={() => editingId !== image.id && setSelectedImage(image)}
                                    className="flex items-center gap-4 p-3 rounded-xl cursor-pointer hover:bg-[var(--card)] transition-colors border"
                                    style={{ borderColor: "var(--border)" }}
                                >
                                    {image.type === 'audio' ? (
                                        <div className="w-16 h-16 rounded-lg flex items-center justify-center bg-gradient-to-br from-emerald-900/40 to-purple-900/40">
                                            <span className="text-2xl">🎵</span>
                                        </div>
                                    ) : (
                                        <img
                                            src={image.imageUrl}
                                            alt={image.name}
                                            className="w-16 h-16 rounded-lg object-cover"
                                        />
                                    )}
                                    <div className="flex-1 min-w-0">
                                        {editingId === image.id ? (
                                            <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                                                <input
                                                    ref={editInputRef}
                                                    type="text"
                                                    value={editingName}
                                                    onChange={(e) => setEditingName(e.target.value)}
                                                    onKeyDown={(e) => {
                                                        if (e.key === 'Enter') handleRename();
                                                        if (e.key === 'Escape') setEditingId(null);
                                                    }}
                                                    className="flex-1 px-2 py-1 rounded border text-sm"
                                                    style={{ background: "var(--background)", borderColor: "var(--accent)", color: "var(--foreground)" }}
                                                />
                                                <button
                                                    onClick={handleRename}
                                                    className="p-1.5 rounded-lg bg-[var(--accent)] text-white hover:opacity-80"
                                                    title="Kaydet"
                                                >
                                                    <Check size={14} />
                                                </button>
                                            </div>
                                        ) : (
                                            <>
                                                <p className="font-medium truncate">{image.name}</p>
                                                <p className="text-sm" style={{ color: "var(--foreground-muted)" }}>
                                                    {image.createdAt?.toLocaleDateString('tr-TR') || 'Tarih bilinmiyor'}
                                                </p>
                                            </>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); startEditing(image); }}
                                            className="p-2 rounded-lg hover:bg-[var(--accent)]/20 transition-colors"
                                            title="Yeniden Adlandır"
                                        >
                                            <Pencil size={18} />
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDownload(image); }}
                                            className="p-2 rounded-lg hover:bg-[var(--accent)]/20 transition-colors"
                                            title="İndir"
                                        >
                                            <Download size={18} />
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleCopyUrl(image.imageUrl); }}
                                            className="p-2 rounded-lg hover:bg-[var(--accent)]/20 transition-colors"
                                            title="URL Kopyala"
                                        >
                                            <Copy size={18} />
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDelete(image.id); }}
                                            className="p-2 rounded-lg hover:bg-red-500/20 transition-colors text-red-400"
                                            title="Sil"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Image Preview Modal */}
                {selectedImage && (
                    <div
                        className="fixed inset-0 z-60 flex items-center justify-center bg-black/90"
                        onClick={() => setSelectedImage(null)}
                    >
                        <div className="relative max-w-[90vw] max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
                            {selectedImage.type === 'video' ? (
                                <video
                                    src={selectedImage.imageUrl}
                                    controls
                                    autoPlay
                                    className="max-w-full max-h-[85vh] object-contain shadow-2xl"
                                />
                            ) : selectedImage.type === 'audio' ? (
                                <div className="bg-[var(--card)] rounded-2xl p-8 shadow-2xl" style={{ minWidth: '400px' }}>
                                    <div className="flex items-center gap-3 mb-4">
                                        <span className="text-3xl">🎵</span>
                                        <span className="text-lg font-medium text-white">{selectedImage.name}</span>
                                    </div>
                                    <audio src={selectedImage.imageUrl} controls autoPlay className="w-full" />
                                </div>
                            ) : (
                                <img
                                    src={selectedImage.imageUrl}
                                    alt={selectedImage.name}
                                    className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl"
                                />
                            )}

                            {/* Actions */}
                            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 px-4 py-2 rounded-full bg-black/70">
                                <button
                                    onClick={() => handleDownload(selectedImage)}
                                    className="p-2 rounded-full hover:bg-white/10 transition-colors"
                                    title="İndir"
                                >
                                    <Download size={20} className="text-white" />
                                </button>
                                <button
                                    onClick={() => handleCopyUrl(selectedImage.imageUrl)}
                                    className="p-2 rounded-full hover:bg-white/10 transition-colors"
                                    title="URL Kopyala"
                                >
                                    <Copy size={20} className="text-white" />
                                </button>
                                <button
                                    onClick={() => window.open(selectedImage.imageUrl, '_blank')}
                                    className="p-2 rounded-full hover:bg-white/10 transition-colors"
                                    title="Yeni sekmede aç"
                                >
                                    <ExternalLink size={20} className="text-white" />
                                </button>
                                <button
                                    onClick={() => {
                                        handleDelete(selectedImage.id);
                                    }}
                                    className="p-2 rounded-full hover:bg-red-500/50 transition-colors"
                                    title="Sil"
                                >
                                    <Trash2 size={20} className="text-white" />
                                </button>
                            </div>

                            {/* Close */}
                            <button
                                onClick={() => setSelectedImage(null)}
                                className="absolute top-4 right-4 p-2 rounded-full bg-black/60 hover:bg-black/80 transition-colors"
                            >
                                <X size={24} className="text-white" />
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
