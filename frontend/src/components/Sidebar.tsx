"use client";

import { useState, useEffect, useRef } from "react";
import {
    createSession, getSessions, deleteSession, updateSession,
    getPresets, createPreset, deletePreset, PresetData,
    getTrashItems, restoreTrashItem, permanentDeleteTrashItem, TrashItemData
} from "@/lib/api";
import {
    ChevronDown,
    ChevronRight,
    FolderOpen,
    Brain,
    Users,
    MapPin,
    Shirt,
    ImageIcon,
    Search,
    Plus,

    Menu,
    X,
    Settings,
    Shield,
    User,
    Puzzle,
    Trash2,

    Pencil,
    Grid3x3,

    Tag,
    GripVertical
} from "lucide-react";
import { useTheme } from "./ThemeProvider";

import { SettingsModal } from "./SettingsModal";
import { SearchModal } from "./SearchModal";
import { NewProjectModal } from "./NewProjectModal";

import { ConfirmDeleteModal } from "./ConfirmDeleteModal";
import { TrashModal, TrashItem } from "./TrashModal";
import { SavePluginModal, PluginDetailModal, CreativePlugin } from "./CreativePluginModal";
import { useToast } from "./ToastProvider";
import { CommunityHubModal } from "./CommunityHubModal";
import { GridGeneratorModal } from "./GridGeneratorModal";
import { SavedImagesModal } from "./SavedImagesModal";
import { useKeyboardShortcuts, SHORTCUTS } from "@/hooks/useKeyboardShortcuts";

interface SidebarItem {
    id: string;
    name: string;
    type: "project" | "character" | "location" | "wardrobe";
}

// Mock data
const mockProjects = [
    { id: "1", name: "Samsung Reklam Kampanyası", active: false },
    { id: "2", name: "Modern Mutfak Tanıtımı", active: true },
];

const mockCharacters = [
    { id: "c1", name: "@character_emre" },
    { id: "c2", name: "@character_ahmet" },
    { id: "c3", name: "@character_ayse" },
];

const mockLocations = [
    { id: "l1", name: "@location_kitchen" },
    { id: "l2", name: "@location_office" },
];

const mockWardrobe = [
    { id: "w1", name: "@costume_black_jacket" },
    { id: "w2", name: "@costume_chef_outfit" },
    { id: "w3", name: "@object_modern_tv" },
    { id: "w4", name: "@object_smartphone" },
];

const mockPresets: CreativePlugin[] = [
    {
        id: "p1",
        name: "Mutfak Reklamı Seti",
        description: "Modern mutfak arka planı ile profesyonel görsel üretimi",
        author: "Ben",
        isPublic: false,
        config: {
            character: { id: "variable", name: "Değişken", isVariable: true },
            location: { id: "mutfak", name: "Modern Mutfak", settings: "" },
            timeOfDay: "Gün Batımı",
            cameraAngles: ["Orta Plan (Medium Shot)", "Yakın Çekim (Close-up)"],
            style: "Sıcak Tonlar"
        },
        createdAt: new Date(),
        downloads: 0,
        rating: 0
    },
    {
        id: "p2",
        name: "Açık Hava Modası",
        description: "Dış mekan moda çekimi için hazır şablon",
        author: "Ben",
        isPublic: true,
        config: {
            character: { id: "variable", name: "Değişken", isVariable: true },
            location: { id: "outdoor", name: "Outdoor - Park", settings: "" },
            timeOfDay: "Sabah",
            cameraAngles: ["Geniş Açı (Wide Shot)", "Orta Plan (Medium Shot)"],
            style: "Editoryal"
        },
        createdAt: new Date(),
        downloads: 45,
        rating: 4.5
    },
];



interface SidebarProps {
    activeProjectId?: string;
    onProjectChange?: (projectId: string) => void;
    onProjectDelete?: () => void;  // Proje silindiğinde çağrılır
    sessionId?: string | null;
    refreshKey?: number;
    onSendPrompt?: (prompt: string) => void;
    onSetInputText?: (text: string) => void;  // Chat input'a yazar ama göndermez
    onPluginsLoaded?: (plugins: Array<{ id: string; name: string; promptText: string }>) => void;
    onAssetRestore?: () => void;  // Çöp kutusundan asset geri yüklenince media panel'ı güncelle
    onAttachAssetUrl?: (url: string, type: "image" | "video" | "audio" | "uploaded") => void;  // Grid'den chat'e görsel gönderme
}

export function Sidebar({ activeProjectId, onProjectChange, onProjectDelete, sessionId, refreshKey, onSendPrompt, onSetInputText, onPluginsLoaded, onAssetRestore, onAttachAssetUrl }: SidebarProps) {
    const { theme } = useTheme();

    const toast = useToast();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [searchOpen, setSearchOpen] = useState(false);
    const [newProjectOpen, setNewProjectOpen] = useState(false);

    const [trashOpen, setTrashOpen] = useState(false);
    const [gridGeneratorOpen, setGridGeneratorOpen] = useState(false);
    const [savedImagesOpen, setSavedImagesOpen] = useState(false);
    const [projects, setProjects] = useState<{ id: string; name: string; active: boolean; category?: string; description?: string }[]>([]);
    const [isLoadingProjects, setIsLoadingProjects] = useState(false);

    // Drag-and-drop reorder state
    const [dragProjectId, setDragProjectId] = useState<string | null>(null);
    const [dragOverProjectId, setDragOverProjectId] = useState<string | null>(null);
    const [dragOverPosition, setDragOverPosition] = useState<'above' | 'below' | null>(null);

    const applyProjectOrder = (list: typeof projects) => {
        try {
            const savedOrder = localStorage.getItem('projectOrder');
            if (!savedOrder) return list;
            const order: string[] = JSON.parse(savedOrder);
            const sorted = [...list].sort((a, b) => {
                const ai = order.indexOf(a.id);
                const bi = order.indexOf(b.id);
                if (ai === -1 && bi === -1) return 0;
                if (ai === -1) return 1;
                if (bi === -1) return -1;
                return ai - bi;
            });
            return sorted;
        } catch { return list; }
    };

    const handleProjectDragStart = (e: React.DragEvent, projectId: string) => {
        setDragProjectId(projectId);
        e.dataTransfer.effectAllowed = 'move';
        // Daha iyi ghost efekti
        const el = e.currentTarget as HTMLElement;
        el.style.opacity = '0.5';
    };

    const handleProjectDragOver = (e: React.DragEvent, projectId: string) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        if (projectId === dragProjectId) return;
        // Üst/alt yarı tespiti — hangi tarafa bırakılacağını belirle
        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        const pos = e.clientY < midY ? 'above' : 'below';
        setDragOverProjectId(projectId);
        setDragOverPosition(pos as 'above' | 'below');
    };

    const handleProjectDrop = (e: React.DragEvent, targetId: string) => {
        e.preventDefault();
        if (!dragProjectId || dragProjectId === targetId) return;
        const fromIdx = projects.findIndex(p => p.id === dragProjectId);
        const toIdx = projects.findIndex(p => p.id === targetId);
        if (fromIdx === -1 || toIdx === -1) return;
        const reordered = [...projects];
        const [moved] = reordered.splice(fromIdx, 1);
        // Pozisyona göre ekleme noktasını ayarla
        const adjustedIdx = dragOverPosition === 'below'
            ? (toIdx > fromIdx ? toIdx : toIdx + 1)
            : (toIdx > fromIdx ? toIdx - 1 : toIdx);
        reordered.splice(Math.max(0, adjustedIdx), 0, moved);
        setProjects(reordered);
        localStorage.setItem('projectOrder', JSON.stringify(reordered.map(p => p.id)));
        setDragProjectId(null);
        setDragOverProjectId(null);
        setDragOverPosition(null);
    };

    const handleProjectDragEnd = (e: React.DragEvent) => {
        (e.currentTarget as HTMLElement).style.opacity = '1';
        setDragProjectId(null);
        setDragOverProjectId(null);
        setDragOverPosition(null);
    };

    // Keyboard shortcuts
    useKeyboardShortcuts({
        shortcuts: [
            { ...SHORTCUTS.SEARCH, action: () => setSearchOpen(true) },
            { ...SHORTCUTS.NEW_PROJECT, action: () => setNewProjectOpen(true) },
            { ...SHORTCUTS.SETTINGS, action: () => setSettingsOpen(true) },
            { ...SHORTCUTS.GRID, action: () => setGridGeneratorOpen(true) },

            {
                ...SHORTCUTS.ESCAPE,
                action: () => {
                    // Close any open modal
                    if (searchOpen) setSearchOpen(false);
                    else if (settingsOpen) setSettingsOpen(false);
                    else if (newProjectOpen) setNewProjectOpen(false);
                    else if (trashOpen) setTrashOpen(false);
                    else if (gridGeneratorOpen) setGridGeneratorOpen(false);
                }
            },
        ],
    });

    // Proje ismi düzenleme state'leri
    const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
    const [editingProjectName, setEditingProjectName] = useState("");
    const editInputRef = useRef<HTMLInputElement>(null);

    // Proje ismi düzenleme fonksiyonları
    const startEditingProject = (projectId: string, currentName: string) => {
        setEditingProjectId(projectId);
        setEditingProjectName(currentName);
        setTimeout(() => editInputRef.current?.focus(), 0);
    };

    const cancelEditingProject = () => {
        setEditingProjectId(null);
        setEditingProjectName("");
    };

    const saveProjectName = async (projectId: string) => {
        const trimmedName = editingProjectName.trim();
        if (trimmedName && trimmedName !== projects.find(p => p.id === projectId)?.name) {
            try {
                await updateSession(projectId, trimmedName);
                setProjects(projects.map(p =>
                    p.id === projectId ? { ...p, name: trimmedName } : p
                ));
            } catch (error) {
                console.error('Proje adı güncellenemedi:', error);
            }
        }
        cancelEditingProject();
    };

    // Preset states
    const [presetsList, setPresetsList] = useState<CreativePlugin[]>([]);

    // Backend'den projeleri yükle
    useEffect(() => {
        const fetchProjects = async () => {
            setIsLoadingProjects(true);
            try {
                const sessions = await getSessions();
                // main_chat session'ını proje listesinden çıkar
                const projectList = sessions
                    .filter(s => s.category !== 'main_chat')
                    .map(s => ({
                        id: s.id,
                        name: s.title,
                        active: sessionId === s.id,
                        category: s.category || undefined,
                        description: s.description || undefined
                    }));
                setProjects(applyProjectOrder(projectList));
            } catch (error) {
                console.error('Proje yükleme hatası:', error);
                setProjects([]);
            } finally {
                setIsLoadingProjects(false);
            }
        };

        fetchProjects();
    }, [sessionId, refreshKey]);

    // Backend'den presets'i yükle
    useEffect(() => {
        const fetchPresets = async () => {
            if (!sessionId) return;
            try {
                const plugins = await getPresets(sessionId);
                const pluginList: CreativePlugin[] = plugins.map((p: PresetData) => ({
                    id: p.id,
                    name: p.name,
                    description: p.description || '',
                    author: 'Ben',
                    isPublic: p.is_public,
                    config: p.config || {},
                    createdAt: new Date(),
                    downloads: p.usage_count,
                    rating: 0
                }));
                setPresetsList(pluginList);
            } catch (error) {
                console.error('Creative plugins yükleme hatası:', error);
                setPresetsList([]);
            }
        };

        fetchPresets();
    }, [sessionId, refreshKey]);

    // Plugin listesi değiştiğinde parent'a bildir
    useEffect(() => {
        if (onPluginsLoaded) {
            const simplified = presetsList.map(p => {
                const parts: string[] = [];
                if (p.config?.style) parts.push(`Stil: ${p.config.style}`);
                if (p.config?.cameraAngles?.length) parts.push(`Açılar: ${p.config.cameraAngles.join(', ')}`);
                if (p.config?.timeOfDay) parts.push(`Zaman: ${p.config.timeOfDay}`);
                const promptText = p.config?.promptTemplate
                    ? `[${p.name}] ${p.config.promptTemplate}${parts.length > 0 ? ` (${parts.join(', ')})` : ''}`
                    : `[${p.name}] ${parts.join(', ')} tarzında görsel üret`;
                return { id: p.id, name: p.name, promptText };
            });
            onPluginsLoaded(simplified);
        }
    }, [presetsList, onPluginsLoaded]);



    const [selectedPlugin, setSelectedPlugin] = useState<CreativePlugin | null>(null);
    const [pluginDetailOpen, setPluginDetailOpen] = useState(false);
    const [communityHubOpen, setCommunityHubOpen] = useState(false);

    // Trash state - backend'den yükle
    const [trashItems, setTrashItems] = useState<TrashItem[]>([]);

    // Backend'den trash items'ları yükle
    useEffect(() => {
        const fetchTrashItems = async () => {
            try {
                const items = await getTrashItems();
                const trashList: TrashItem[] = items.map((i: TrashItemData) => ({
                    id: i.id,
                    name: i.item_name,
                    type: i.item_type as TrashItem["type"],
                    deletedAt: new Date(i.deleted_at),
                    imageUrl: (i.original_data?.url || i.original_data?.reference_image_url || undefined) as string | undefined,
                    assetType: i.original_data?.type as TrashItem["assetType"] || undefined,
                    originalData: i.original_data || {}
                }));
                setTrashItems(trashList);
            } catch (error) {
                console.error('Trash yükleme hatası:', error);
                setTrashItems([]);
            }
        };

        fetchTrashItems();
    }, [refreshKey]);


    // Delete confirmation state
    const [deleteConfirm, setDeleteConfirm] = useState<{
        isOpen: boolean;
        itemId: string;
        itemName: string;
        itemType: TrashItem["type"];
        onConfirm: () => void;
    } | null>(null);

    // Update projects when activeProjectId changes from parent
    const handleProjectClick = (projectId: string) => {
        setProjects(projects.map(p => ({
            ...p,
            active: p.id === projectId
        })));
        onProjectChange?.(projectId);
    };

    // Move to trash instead of deleting
    const moveToTrash = (id: string, name: string, type: TrashItem["type"], originalData: Record<string, unknown>, imageUrl?: string) => {
        setTrashItems(prev => [...prev, {
            id,
            name,
            type,
            deletedAt: new Date(),
            imageUrl,
            assetType: (originalData?.type as TrashItem["assetType"]) || undefined,
            originalData
        }]);
    };



    const confirmDeleteProject = (id: string) => {
        const proj = projects.find(p => p.id === id);
        if (!proj) return;
        setDeleteConfirm({
            isOpen: true,
            itemId: id,
            itemName: proj.name,
            itemType: "proje",
            onConfirm: async () => {
                try {
                    // Backend'den session'ı sil
                    await deleteSession(id);
                    moveToTrash(id, proj.name, "proje", proj);
                    const remainingProjects = projects.filter(p => p.id !== id);
                    setProjects(remainingProjects);
                    toast.success(`"${proj.name}" çöp kutusuna taşındı`);

                    // Eğer aktif proje silindiyse, ana sayfayı bilgilendir
                    if (proj.active || remainingProjects.length === 0) {
                        onProjectDelete?.();
                    }
                } catch (error) {
                    console.error('Proje silinemedi:', error);
                    toast.error('Proje silinemedi');
                }
            }
        });
    };

    // Restore from trash - backend'e bağlı
    const handleRestore = async (item: TrashItem) => {
        try {
            console.log("=== RESTORE DEBUG ===");
            console.log("TrashItem:", item);
            console.log("item.type:", item.type);
            console.log("Current projects:", projects);

            const result = await restoreTrashItem(item.id);
            console.log("API Result:", result);

            if (result.success && result.restored) {
                const restored = result.restored;
                console.log("Restored object:", restored);

                // UI güncelle - backend'den dönen verilerle
                switch (item.type) {
                    case "proje":
                    case "session":  // Backend "session" tip döndürüyor
                        console.log("Adding to projects:", { id: restored.id, name: restored.title || item.name });
                        const newProject = {
                            id: restored.id,
                            name: restored.title || item.name,
                            active: false
                        };
                        setProjects(prevProjects => [...prevProjects, newProject]);
                        break;
                    case "preset":
                        // Preset geri yüklendi — sidebar refresh olacak
                        console.log("Preset restored");
                        break;
                    default:
                        console.log("Unknown type:", item.type);
                }
            } else {
                console.log("result.success:", result.success);
                console.log("result.restored:", result.restored);
            }

            // Çöp kutusundan kaldır
            setTrashItems(prev => prev.filter(t => t.id !== item.id));
            toast.success(`"${item.name}" başarıyla geri yüklendi`);

            // Asset geri yüklendiyse media panel'ı güncelle
            if (item.type === 'asset') {
                onAssetRestore?.();
            }
        } catch (error) {
            console.error('Geri yükleme hatası:', error);
            toast.error('Geri yükleme başarısız oldu');
        }
    };

    // Permanent delete - backend'e bağlı
    const handlePermanentDelete = async (id: string) => {
        try {
            await permanentDeleteTrashItem(id);
            setTrashItems(prev => prev.filter(t => t.id !== id));
            toast.success('Kalıcı olarak silindi');
        } catch (error) {
            console.error('Kalıcı silme hatası:', error);
            toast.error('Kalıcı silme başarısız oldu');
        }
    };

    // Delete all trash items
    const handleDeleteAll = async () => {
        try {
            const currentItems = [...trashItems];
            await Promise.all(currentItems.map(item => permanentDeleteTrashItem(item.id)));
            setTrashItems([]);
            toast.success('Tüm öğeler silindi');
        } catch (error) {
            console.error('Tümünü silme hatası:', error);
            // Hata durumunda backend'den tekrar yükle
            const items = await getTrashItems();
            const trashList: TrashItem[] = items.map((i: TrashItemData) => ({
                id: i.id,
                name: i.item_name,
                type: i.item_type as TrashItem["type"],
                deletedAt: new Date(i.deleted_at),
                imageUrl: (i.original_data?.url || i.original_data?.reference_image_url || undefined) as string | undefined,
                assetType: i.original_data?.type as TrashItem["assetType"] || undefined,
                originalData: i.original_data || {}
            }));
            setTrashItems(trashList);
        }
    };

    // Delete multiple selected items
    const handleDeleteMultiple = async (ids: string[]) => {
        try {
            await Promise.all(ids.map(id => permanentDeleteTrashItem(id)));
            setTrashItems(prev => prev.filter(t => !ids.includes(t.id)));
            toast.success(`${ids.length} öğe silindi`);
        } catch (error) {
            console.error('Çoklu silme hatası:', error);
            // Hata durumunda backend'den tekrar yükle
            const items = await getTrashItems();
            const trashList: TrashItem[] = items.map((i: TrashItemData) => ({
                id: i.id,
                name: i.item_name,
                type: i.item_type as TrashItem["type"],
                deletedAt: new Date(i.deleted_at),
                imageUrl: (i.original_data?.url || i.original_data?.reference_image_url || undefined) as string | undefined,
                assetType: i.original_data?.type as TrashItem["assetType"] || undefined,
                originalData: i.original_data || {}
            }));
            setTrashItems(trashList);
        }
    };



    // Category helpers
    const categoryEmoji = (cat?: string) => {
        switch (cat) {
            case 'reklam': return '📢';
            case 'sosyal_medya': return '📱';
            case 'film': return '🎬';
            case 'marka': return '🏷️';
            case 'kisisel': return '🌱';
            default: return '📁';
        }
    };

    const categoryColor = (cat?: string) => {
        switch (cat) {
            case 'reklam': return { bg: 'rgba(239,68,68,0.15)', text: '#ef4444' };
            case 'sosyal_medya': return { bg: 'rgba(59,130,246,0.15)', text: '#3b82f6' };
            case 'film': return { bg: 'rgba(168,85,247,0.15)', text: '#a855f7' };
            case 'marka': return { bg: 'rgba(245,158,11,0.15)', text: '#f59e0b' };
            case 'kisisel': return { bg: 'rgba(201,168,76,0.15)', text: '#C9A84C' };
            default: return { bg: 'rgba(107,114,128,0.15)', text: '#6b7280' };
        }
    };

    const categoryLabel = (cat?: string) => {
        switch (cat) {
            case 'reklam': return 'Reklam';
            case 'sosyal_medya': return 'Sosyal Medya';
            case 'film': return 'Film';
            case 'marka': return 'Marka';
            case 'kisisel': return 'Kişisel';
            default: return 'Kategori';
        }
    };

    // Drawer panel state
    const [drawerPanel, setDrawerPanel] = useState<'projects' | 'entities' | null>('projects');

    const toggleDrawer = (panel: 'projects' | 'entities') => {
        setDrawerPanel(prev => prev === panel ? null : panel);
    };

    return (
        <>
            {/* Mobile hamburger button */}
            <button
                onClick={() => setMobileOpen(true)}
                className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg"
                style={{ background: "var(--card)" }}
            >
                <Menu size={24} />
            </button>

            {/* Mobile overlay */}
            {mobileOpen && (
                <div
                    className="lg:hidden fixed inset-0 bg-black/60 z-40"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* ===== TWO-LAYER SIDEBAR ===== */}
            <div
                className={`fixed lg:relative flex z-50 transition-transform duration-300 ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}
                style={{ height: '100vh' }}
            >
                {/* ── ICON RAIL ── */}
                <div className="sidebar-rail">
                    {/* Logo */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', padding: '4px 0', marginBottom: 8 }}>
                        <div style={{ width: 36, height: 36, borderRadius: 10, background: 'linear-gradient(135deg, #D4B85C, #8B6D28)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="black"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5m14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>
                        </div>
                    </div>

                    {/* Main nav */}
                    <button
                        className={`rail-btn ${drawerPanel === 'projects' ? 'active' : ''}`}
                        onClick={() => toggleDrawer('projects')}
                    >
                        <FolderOpen size={24} />
                        <span className="rail-label">Projeler</span>
                    </button>

                    <button
                        className={`rail-btn ${drawerPanel === 'entities' ? 'active' : ''}`}
                        onClick={() => toggleDrawer('entities')}
                    >
                        <Brain size={24} />
                        <span className="rail-label">Varlıklar</span>
                    </button>

                    <div className="rail-divider" />

                    {/* Feature tools — each with unique color */}
                    <button
                        className="rail-feature-btn"
                        onClick={() => setGridGeneratorOpen(true)}
                        style={{
                            background: 'rgba(201, 168, 76, 0.10)',
                            border: '1px solid rgba(201, 168, 76, 0.25)',
                            color: '#C9A84C'
                        }}
                    >
                        <Grid3x3 size={20} />
                        <span className="rail-label" style={{ color: '#C9A84C' }}>Grid Oluşturucu</span>
                    </button>

                    <button
                        className="rail-feature-btn"
                        onClick={() => setSavedImagesOpen(true)}
                        style={{
                            background: 'rgba(201, 168, 76, 0.08)',
                            border: '1px solid rgba(201, 168, 76, 0.20)',
                            color: '#B8963A'
                        }}
                    >
                        <ImageIcon size={20} />
                        <span className="rail-label" style={{ color: '#B8963A' }}>Kaydedilenler</span>
                    </button>

                    <button
                        className="rail-feature-btn"
                        onClick={() => setCommunityHubOpen(true)}
                        style={{
                            background: 'rgba(184, 150, 58, 0.08)',
                            border: '1px solid rgba(184, 150, 58, 0.20)',
                            color: '#A68B30'
                        }}
                    >
                        <Users size={20} />
                        <span className="rail-label" style={{ color: '#A68B30' }}>Topluluk</span>
                    </button>
                    {/* Spacer */}
                    <div className="rail-spacer" />
                    <div className="rail-divider" />

                    {/* Bottom tools */}
                    <button className="rail-btn" onClick={() => setSearchOpen(true)}>
                        <Search size={24} />
                        <span className="rail-label">Ara</span>
                    </button>

                    <button className="rail-btn" onClick={() => setTrashOpen(true)} style={{ position: 'relative' }}>
                        <Trash2 size={24} />
                        <span className="rail-label">Çöp Kutusu</span>
                        {trashItems.length > 0 && (
                            <span style={{
                                position: 'absolute', top: 4, right: 4,
                                width: 8, height: 8, borderRadius: '50%',
                                background: '#ef4444'
                            }} />
                        )}
                    </button>

                    <button className="rail-btn" onClick={() => setSettingsOpen(true)}>
                        <Settings size={24} />
                        <span className="rail-label">Ayarlar</span>
                    </button>

                </div>

                {/* ── SLIDING DRAWER ── */}
                <div className={`sidebar-drawer ${drawerPanel === null ? 'collapsed' : ''}`}>
                    {/* Close button (mobile) */}
                    <button
                        onClick={() => setMobileOpen(false)}
                        className="lg:hidden absolute top-4 right-4 z-50"
                    >
                        <X size={20} />
                    </button>

                    {/* === PROJECTS PANEL === */}
                    {drawerPanel === 'projects' && (
                        <>
                            <div className="drawer-header">
                                <h3>Projeler</h3>
                                <button
                                    onClick={() => setNewProjectOpen(true)}
                                    className="rail-btn"
                                    style={{ width: 28, height: 28 }}
                                    title="Yeni Proje"
                                >
                                    <Plus size={14} />
                                </button>
                            </div>

                            <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
                                {isLoadingProjects ? (
                                    <div style={{ textAlign: 'center', padding: 24, color: 'var(--foreground-muted)', fontSize: 12 }}>
                                        Yükleniyor...
                                    </div>
                                ) : projects.length === 0 ? (
                                    <div style={{ textAlign: 'center', padding: 24, color: 'var(--foreground-muted)', fontSize: 12 }}>
                                        Henüz proje yok
                                    </div>
                                ) : (
                                    projects.map((project) => {
                                        const isEditing = editingProjectId === project.id;
                                        const colors = categoryColor(project.category);
                                        return (
                                            <div key={project.id} style={{ position: 'relative' }}>
                                                {/* Drop indicator — above */}
                                                {dragOverProjectId === project.id && dragOverPosition === 'above' && dragProjectId !== project.id && (
                                                    <div style={{
                                                        position: 'absolute', top: -1, left: 8, right: 8, height: 2,
                                                        background: 'var(--accent)', borderRadius: 2, zIndex: 10,
                                                        boxShadow: '0 0 6px var(--accent)'
                                                    }} />
                                                )}

                                                <div
                                                    draggable={!isEditing}
                                                    onDragStart={(e) => handleProjectDragStart(e, project.id)}
                                                    onDragOver={(e) => handleProjectDragOver(e, project.id)}
                                                    onDrop={(e) => handleProjectDrop(e, project.id)}
                                                    onDragEnd={handleProjectDragEnd}
                                                    className={`project-card-v2 group ${project.active ? 'active' : ''}`}
                                                    style={{
                                                        cursor: isEditing ? 'text' : 'pointer',
                                                        opacity: dragProjectId === project.id ? 0.35 : 1,
                                                        transform: dragProjectId === project.id ? 'scale(0.97)' : 'scale(1)',
                                                        transition: 'opacity 0.2s ease, transform 0.2s ease'
                                                    }}
                                                    onClick={() => !isEditing && handleProjectClick(project.id)}
                                                    onDoubleClick={(e) => {
                                                        e.stopPropagation();
                                                        startEditingProject(project.id, project.name);
                                                    }}
                                                >
                                                    {/* Drag handle — only visible on hover */}
                                                    {!isEditing && (
                                                        <div
                                                            style={{
                                                                display: 'flex', alignItems: 'center',
                                                                cursor: 'grab', opacity: 0, transition: 'opacity 0.15s',
                                                                padding: '0 2px', marginLeft: -4
                                                            }}
                                                            className="group-hover:opacity-100!"
                                                            onMouseDown={(e) => e.stopPropagation()}
                                                        >
                                                            <GripVertical size={14} style={{ color: 'var(--foreground-muted)' }} />
                                                        </div>
                                                    )}

                                                    {/* Thumbnail */}
                                                    <div className="project-thumb" style={{ position: 'relative' }}>
                                                        {categoryEmoji(project.category)}
                                                    </div>

                                                    {/* Info */}
                                                    <div className="project-info">
                                                        {isEditing ? (
                                                            <input
                                                                ref={editInputRef}
                                                                type="text"
                                                                value={editingProjectName}
                                                                onChange={(e) => setEditingProjectName(e.target.value)}
                                                                onBlur={() => saveProjectName(project.id)}
                                                                onKeyDown={(e) => {
                                                                    if (e.key === 'Enter') saveProjectName(project.id);
                                                                    if (e.key === 'Escape') cancelEditingProject();
                                                                }}
                                                                onClick={(e) => e.stopPropagation()}
                                                                style={{
                                                                    width: '100%', background: 'transparent',
                                                                    border: 'none', borderBottom: '1px solid var(--accent)',
                                                                    outline: 'none', fontSize: 13, color: 'var(--foreground)',
                                                                    padding: '2px 0'
                                                                }}
                                                                autoFocus
                                                            />
                                                        ) : (
                                                            <>
                                                                <div className="project-name">{project.name}</div>
                                                                <div className="project-meta">
                                                                    {project.category && (
                                                                        <span
                                                                            className="category-badge"
                                                                            style={{ background: colors.bg, color: colors.text }}
                                                                        >
                                                                            {categoryLabel(project.category)}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </>
                                                        )}
                                                    </div>

                                                    {/* Actions */}
                                                    {!isEditing && (
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: 2, opacity: 0, transition: 'opacity 0.15s' }}
                                                            className="group-hover:opacity-100!"
                                                        >
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); startEditingProject(project.id, project.name); }}
                                                                className="p-1 rounded hover:bg-[var(--card-hover)]"
                                                                title="Yeniden Adlandır"
                                                            >
                                                                <Pencil size={12} style={{ color: 'var(--foreground-muted)' }} />
                                                            </button>
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); confirmDeleteProject(project.id); }}
                                                                className="p-1 rounded hover:bg-red-500/20"
                                                                title="Sil"
                                                            >
                                                                <Trash2 size={12} style={{ color: '#ef4444' }} />
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Drop indicator — below */}
                                                {dragOverProjectId === project.id && dragOverPosition === 'below' && dragProjectId !== project.id && (
                                                    <div style={{
                                                        position: 'absolute', bottom: -1, left: 8, right: 8, height: 2,
                                                        background: 'var(--accent)', borderRadius: 2, zIndex: 10,
                                                        boxShadow: '0 0 6px var(--accent)'
                                                    }} />
                                                )}
                                            </div>
                                        );
                                    })
                                )}
                            </div>

                            {/* New project button at bottom */}
                            <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
                                <button
                                    onClick={() => setNewProjectOpen(true)}
                                    style={{
                                        width: '100%', padding: '8px 12px', borderRadius: 8,
                                        background: 'rgba(201, 168, 76, 0.08)', border: '1px solid rgba(201, 168, 76, 0.15)',
                                        color: 'var(--accent)', fontSize: 13, fontWeight: 500,
                                        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                                        transition: 'all 0.2s ease'
                                    }}
                                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(201, 168, 76, 0.15)')}
                                    onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(201, 168, 76, 0.08)')}
                                >
                                    <Plus size={14} />
                                    Yeni Proje
                                </button>
                            </div>
                        </>
                    )}

                    {/* === PLUGINS PANEL === */}
                    {drawerPanel === 'entities' && (
                        <>
                            <div className="drawer-header">
                                <h3>Eklentiler</h3>
                            </div>


                            <div style={{ flex: 1, overflowY: 'auto' }}>

                                {/* Creative Plugins — başlık her zaman görünür */}
                                <div style={{ marginTop: 8 }}>
                                    <div style={{
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                        padding: '8px 16px'
                                    }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 500, color: 'var(--foreground-muted)' }}>
                                            <Puzzle size={14} />
                                            <span>Yaratıcı Eklentiler</span>
                                            {presetsList.length > 0 && (
                                                <span style={{ opacity: 0.6 }}>({presetsList.length})</span>
                                            )}
                                        </div>
                                    </div>
                                    {presetsList.length > 0 ? (
                                        <div>
                                            {presetsList.map((plugin) => (
                                                <div
                                                    key={plugin.id}
                                                    onClick={() => { setSelectedPlugin(plugin); setPluginDetailOpen(true); }}
                                                    className="group"
                                                    style={{
                                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                                        padding: '6px 16px 6px 28px', cursor: 'pointer', fontSize: 13,
                                                        color: 'var(--foreground-muted)', transition: 'background 0.15s'
                                                    }}
                                                >
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
                                                        <span style={{
                                                            width: 6, height: 6, borderRadius: '50%',
                                                            background: plugin.isPublic ? '#C9A84C' : '#f59e0b', flexShrink: 0
                                                        }} />
                                                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{plugin.name}</span>
                                                    </div>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            deletePreset(plugin.id).then(success => {
                                                                if (success) {
                                                                    setPresetsList(presetsList.filter(p => p.id !== plugin.id));
                                                                    // Çöp kutusuna anında ekle
                                                                    moveToTrash(
                                                                        plugin.id,
                                                                        plugin.name,
                                                                        "preset",
                                                                        { description: plugin.description },
                                                                        undefined
                                                                    );
                                                                }
                                                            });
                                                        }}
                                                        className="p-1 rounded hover:bg-red-500/20 opacity-0 group-hover:!opacity-100 transition-opacity"
                                                        style={{ flexShrink: 0 }}
                                                        title="Sil"
                                                    >
                                                        <Trash2 size={12} style={{ color: '#ef4444' }} />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div style={{ padding: '4px 16px 8px 28px', fontSize: 12, color: 'var(--foreground-muted)', opacity: 0.5 }}>
                                            Henüz preset eklenmemiş
                                        </div>
                                    )}
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>

            {/* ===== MODALS ===== */}
            <SettingsModal
                isOpen={settingsOpen}
                onClose={() => setSettingsOpen(false)}
            />

            <SearchModal
                isOpen={searchOpen}
                onClose={() => setSearchOpen(false)}
                sessionId={sessionId}
            />

            <NewProjectModal
                isOpen={newProjectOpen}
                onClose={() => setNewProjectOpen(false)}
                onSubmit={async (name, description, category) => {
                    try {
                        const newSession = await createSession(name, description, category);
                        setProjects([...projects, { id: newSession.id, name, active: false, category, description }]);
                    } catch (error) {
                        console.error('Proje oluşturulamadı:', error);
                        setProjects([...projects, { id: Date.now().toString(), name, active: false }]);
                    }
                }}
            />


            <ConfirmDeleteModal
                isOpen={deleteConfirm?.isOpen ?? false}
                onClose={() => setDeleteConfirm(null)}
                onConfirm={() => deleteConfirm?.onConfirm()}
                itemName={deleteConfirm?.itemName ?? ""}
                itemType={deleteConfirm?.itemType ?? "öğe"}
            />

            <TrashModal
                isOpen={trashOpen}
                onClose={() => setTrashOpen(false)}
                items={trashItems}
                onRestore={handleRestore}
                onPermanentDelete={handlePermanentDelete}
                onDeleteAll={handleDeleteAll}
                onDeleteMultiple={handleDeleteMultiple}
            />

            <PluginDetailModal
                isOpen={pluginDetailOpen}
                onClose={() => setPluginDetailOpen(false)}
                plugin={selectedPlugin}
                onDelete={(id) => {
                    setPresetsList(presetsList.filter(p => p.id !== id));
                    setPluginDetailOpen(false);
                }}
                onUpdate={(updated) => {
                    setPresetsList(presetsList.map(p => p.id === updated.id ? updated : p));
                    setSelectedPlugin(updated);
                }}
                onUse={(plugin) => {
                    const setTextFn = onSetInputText || onSendPrompt;
                    if (setTextFn) {
                        setTextFn(`Preset: ${plugin.name}`);
                    }
                    setPluginDetailOpen(false);
                }}
            />



            <GridGeneratorModal
                isOpen={gridGeneratorOpen}
                onClose={() => setGridGeneratorOpen(false)}
                onSendToChat={(url) => {
                    onAttachAssetUrl?.(url, "image");
                    setGridGeneratorOpen(false);
                }}
            />

            <CommunityHubModal
                isOpen={communityHubOpen}
                onClose={() => setCommunityHubOpen(false)}
                projects={projects}
                activeProjectId={sessionId || undefined}
                sessionId={sessionId}
            />
            <SavedImagesModal
                isOpen={savedImagesOpen}
                onClose={() => setSavedImagesOpen(false)}
                sessionId={sessionId}
                onRefresh={() => { }}
                onItemDeleted={(id, name, imageUrl, mediaType) => {
                    moveToTrash(id, name, "wardrobe", { reference_image_url: imageUrl, type: mediaType }, imageUrl);
                }}
            />
        </>
    );
}
