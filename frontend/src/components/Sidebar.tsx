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
    Search,
    Plus,
    Menu,
    X,
    Settings,
    Puzzle,
    Trash2,
    Pencil,
    Grid3x3,
    GripVertical,
    PanelLeftClose,
    PanelLeftOpen
} from "lucide-react";
import { useTheme } from "./ThemeProvider";

import { SettingsModal } from "./SettingsModal";
import { SearchModal } from "./SearchModal";
import { NewProjectModal } from "./NewProjectModal";

import { ConfirmDeleteModal } from "./ConfirmDeleteModal";
import { TrashModal, TrashItem } from "./TrashModal";
import { SavePluginModal, PluginDetailModal, CreativePlugin } from "./CreativePluginModal";
import { useToast } from "./ToastProvider";
import { GridGeneratorModal } from "./GridGeneratorModal";
import { useKeyboardShortcuts, SHORTCUTS } from "@/hooks/useKeyboardShortcuts";

interface SidebarItem {
    id: string;
    name: string;
    type: "project" | "character" | "location" | "wardrobe";
}

function SidebarItem({ collapsed, icon, label, active, onClick, accent, badge }: {
    collapsed: boolean; icon: React.ReactNode; label: string;
    active?: boolean; onClick: () => void; accent?: boolean; badge?: boolean;
}) {
    return (
        <button
            onClick={onClick}
            title={label}
            style={{
                display: 'flex',
                flexDirection: collapsed ? 'column' : 'row',
                alignItems: 'center',
                gap: collapsed ? 3 : 10,
                padding: collapsed ? '8px 4px' : '7px 10px',
                borderRadius: 10,
                border: 'none',
                background: active ? 'rgba(201,168,76,0.12)' : 'transparent',
                cursor: 'pointer',
                width: collapsed ? 56 : '100%',
                transition: 'background 0.15s',
                position: 'relative',
            }}
        >
            <span style={{ color: active ? 'var(--accent)' : accent ? 'var(--accent)' : 'var(--foreground-muted)', display: 'flex', alignItems: 'center' }}>{icon}</span>
            {collapsed ? (
                <span style={{ fontSize: 9, color: active ? 'var(--accent)' : 'var(--foreground-muted)' }}>{label}</span>
            ) : (
                <span style={{ fontSize: 13, color: active ? 'var(--accent)' : 'var(--foreground)', whiteSpace: 'nowrap' }}>{label}</span>
            )}
            {badge && <span style={{ position: 'absolute', top: collapsed ? 4 : 8, right: collapsed ? 12 : 10, width: 6, height: 6, borderRadius: '50%', background: '#ef4444' }} />}
        </button>
    );
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
            character: { id: "variable", name: "DeÄŸişken", isVariable: true },
            location: { id: "mutfak", name: "Modern Mutfak", settings: "" },
            timeOfDay: "Gün Batımı",
            cameraAngles: ["Orta Plan (Medium Shot)", "Yakın Ã‡ekim (Close-up)"],
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
            character: { id: "variable", name: "DeÄŸişken", isVariable: true },
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
    onProjectDelete?: () => void;  // Proje silindiÄŸinde çaÄŸrılır
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
    const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
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
        // Ãœst/alt yarı tespiti â€” hangi tarafa bırakılacaÄŸını belirle
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

    // Plugin listesi deÄŸiştiÄŸinde parent'a bildir
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

                    // EÄŸer aktif proje silindiyse, ana sayfayı bilgilendir
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

    // Restore from trash - backend'e baÄŸlı
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
                        // Preset geri yüklendi â€” sidebar refresh olacak
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

    // Permanent delete - backend'e baÄŸlı
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
            toast.success('Tüm öÄŸeler silindi');
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
            toast.success(`${ids.length} öÄŸe silindi`);
        } catch (error) {
            console.error('Ã‡oklu silme hatası:', error);
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
            case 'reklam': return '\u{1F4E2}';
            case 'sosyal_medya': return '\u{1F4F1}';
            case 'film': return '\u{1F3AC}';
            case 'marka': return '\u{1F3F7}';
            case 'kisisel': return '\u{1F331}';
            default: return '\u{1F4C1}';
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
    const [drawerPanel, setDrawerPanel] = useState<'projects' | 'entities' | null>(null);

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

            {/* ===== SIDEBAR ===== */}
            <div
                className={`fixed lg:relative flex flex-col z-50 transition-all duration-300 ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}
                style={{
                    height: '100vh',
                    width: sidebarCollapsed ? 64 : 200,
                    background: 'var(--background-secondary)',
                    borderRight: '1px solid var(--border)',
                    padding: sidebarCollapsed ? '10px 0 8px' : '10px 8px 8px',
                    alignItems: sidebarCollapsed ? 'center' : 'stretch',
                }}
            >
                {/* Logo */}
                <div
                    onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                    style={{
                        display: 'flex', alignItems: 'center',
                        padding: sidebarCollapsed ? '4px 0 12px' : '0 0 8px',
                        cursor: 'pointer',
                        justifyContent: 'center',
                    }}
                    title={sidebarCollapsed ? "Genişlet" : "Daralt"}
                >
                    {sidebarCollapsed ? (
                        <img src="/panther-watermark.png" alt="Nero Panthero" style={{ width: 36, height: 36, objectFit: 'contain' }} />
                    ) : (
                        <img src="/nero-panthero-full.png" alt="Nero Panthero" style={{ width: '100%', objectFit: 'contain', filter: 'invert(1) hue-rotate(180deg)', mixBlendMode: 'screen' }} />
                    )}
                </div>

                {/* Projeler */}
                <SidebarItem collapsed={sidebarCollapsed} icon={<FolderOpen size={18} />} label="Projeler" active={drawerPanel === 'projects'} onClick={() => setDrawerPanel(drawerPanel === 'projects' ? null : 'projects')} />

                {/* Section: CREATE */}
                {!sidebarCollapsed && <div style={{ fontSize: 9, fontWeight: 600, color: 'var(--foreground-muted)', letterSpacing: 1.2, textTransform: 'uppercase', padding: '14px 10px 4px', opacity: 0.6 }}>Oluştur</div>}
                <SidebarItem collapsed={sidebarCollapsed} icon={<Plus size={18} />} label="Yeni Proje" onClick={() => setNewProjectOpen(true)} accent />
                <SidebarItem collapsed={sidebarCollapsed} icon={<Grid3x3 size={18} />} label="Grid Oluşturucu" onClick={() => setGridGeneratorOpen(true)} />

                {/* Section: TOOLS */}
                {!sidebarCollapsed && <div style={{ fontSize: 9, fontWeight: 600, color: 'var(--foreground-muted)', letterSpacing: 1.2, textTransform: 'uppercase', padding: '14px 10px 4px', opacity: 0.6 }}>Araçlar</div>}
                <SidebarItem collapsed={sidebarCollapsed} icon={<Search size={18} />} label="Ara" onClick={() => setSearchOpen(true)} />

                {/* Spacer */}
                <div style={{ flex: 1 }} />

                {/* Bottom */}
                <SidebarItem collapsed={sidebarCollapsed} icon={<Trash2 size={18} />} label="Çöp" onClick={() => setTrashOpen(true)} badge={trashItems.length > 0} />
                <SidebarItem collapsed={sidebarCollapsed} icon={<Settings size={18} />} label="Ayarlar" onClick={() => setSettingsOpen(true)} />
            </div>

            {/* ===== FLYOUT PROJECT PANEL ===== */}
            {drawerPanel === 'projects' && (
                <div style={{ width: 200, height: '100vh', flexShrink: 0, background: 'var(--background-secondary)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 12px 8px' }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)' }}>Projeler</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            <button onClick={() => setNewProjectOpen(true)} className="p-1 rounded-md hover:bg-[var(--card)] transition-colors" title="Yeni Proje" style={{ background: 'rgba(201,168,76,0.1)' }}><Plus size={14} style={{ color: 'var(--accent)' }} /></button>
                            <button onClick={() => setDrawerPanel(null)} className="p-0.5 rounded hover:bg-[var(--card)]"><X size={14} style={{ color: 'var(--foreground-muted)' }} /></button>
                        </div>
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', padding: '0 6px' }}>
                        {isLoadingProjects ? (
                            <div style={{ textAlign: 'center', padding: 20, color: 'var(--foreground-muted)', fontSize: 11 }}>Yükleniyor...</div>
                        ) : projects.length === 0 ? (
                            <button onClick={() => setNewProjectOpen(true)} style={{ width: '100%', padding: 10, borderRadius: 8, background: 'rgba(201,168,76,0.06)', border: '1px dashed rgba(201,168,76,0.2)', color: 'var(--foreground-muted)', fontSize: 11, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                                <Plus size={12} /> İlk Projeyi Oluştur
                            </button>
                        ) : projects.map((project) => {
                            const isEditing = editingProjectId === project.id;
                            const isActive = project.active;
                            return (
                                <div key={project.id} className="group" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', borderRadius: 6, marginBottom: 1, cursor: isEditing ? 'text' : 'pointer', background: isActive ? 'rgba(201,168,76,0.12)' : 'transparent', borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent', transition: 'all 0.15s' }} onClick={() => !isEditing && handleProjectClick(project.id)} onDoubleClick={(e) => { e.stopPropagation(); startEditingProject(project.id, project.name); }} onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = 'var(--card)'; }} onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}>
                                    <span style={{ fontSize: 13, flexShrink: 0 }}>{categoryEmoji(project.category)}</span>
                                    {isEditing ? (
                                        <input ref={editInputRef} type="text" value={editingProjectName} onChange={(e) => setEditingProjectName(e.target.value)} onBlur={() => saveProjectName(project.id)} onKeyDown={(e) => { if (e.key === 'Enter') saveProjectName(project.id); if (e.key === 'Escape') cancelEditingProject(); }} onClick={(e) => e.stopPropagation()} style={{ flex: 1, background: 'transparent', border: 'none', borderBottom: '1px solid var(--accent)', outline: 'none', fontSize: 11, color: 'var(--foreground)', padding: '1px 0', minWidth: 0 }} autoFocus />
                                    ) : (
                                        <span style={{ flex: 1, fontSize: 11, color: isActive ? 'var(--foreground)' : 'var(--foreground-muted)', fontWeight: isActive ? 500 : 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{project.name}</span>
                                    )}
                                    {!isEditing && (
                                        <div style={{ display: 'flex', gap: 1, opacity: 0, transition: 'opacity 0.1s' }} className="group-hover:!opacity-100">
                                            <button onClick={(e) => { e.stopPropagation(); startEditingProject(project.id, project.name); }} className="p-0.5 rounded hover:bg-[var(--card-hover)]"><Pencil size={10} style={{ color: 'var(--foreground-muted)' }} /></button>
                                            <button onClick={(e) => { e.stopPropagation(); confirmDeleteProject(project.id); }} className="p-0.5 rounded hover:bg-red-500/20"><Trash2 size={10} style={{ color: '#ef4444' }} /></button>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

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
                        console.error('Proje Oluşturulamadı:', error);
                        setProjects([...projects, { id: Date.now().toString(), name, active: false }]);
                    }
                }}
            />


            <ConfirmDeleteModal
                isOpen={deleteConfirm?.isOpen ?? false}
                onClose={() => setDeleteConfirm(null)}
                onConfirm={() => deleteConfirm?.onConfirm()}
                itemName={deleteConfirm?.itemName ?? ""}
                itemType={deleteConfirm?.itemType ?? "öÄŸe"}
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


        </>
    );
}
