"use client";

import { useState, useEffect, useRef } from "react";
import {
    getEntities, deleteEntity, Entity, createSession, getSessions, deleteSession, updateSession,
    getCreativePlugins, createCreativePlugin, deleteCreativePlugin, CreativePluginData,
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
    LogOut,
    Tag,
    GripVertical
} from "lucide-react";
import { useTheme } from "./ThemeProvider";
import { useAuth } from "@/contexts/AuthContext";
import { SettingsModal } from "./SettingsModal";
import { SearchModal } from "./SearchModal";
import { NewProjectModal } from "./NewProjectModal";
import { AdminPanelModal } from "./AdminPanelModal";
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

const mockCreativePlugins: CreativePlugin[] = [
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

interface CollapsibleSectionProps {
    title: string;
    icon: React.ReactNode;
    items: { id: string; name: string }[];
    defaultOpen?: boolean;
    onDelete?: (id: string) => void;
}

function CollapsibleSection({ title, icon, items, defaultOpen = false, onDelete }: CollapsibleSectionProps) {
    // Her zaman items.length > 0 ise true, değilse false
    // Kullanıcının manuel açıp kapatmasına da izin ver
    const [userOverride, setUserOverride] = useState<boolean | null>(null);

    // Gerçek open durumu: kullanıcı override ettiyse onu kullan, yoksa items.length'e göre
    const open = userOverride !== null ? userOverride : items.length > 0;

    // items değiştiğinde user override'ı sıfırla (yeni data geldi)
    useEffect(() => {
        setUserOverride(null);
    }, [items.length]);

    const toggleOpen = () => {
        setUserOverride(!open);
    };


    const handleDragStart = (e: React.DragEvent, item: { id: string; name: string }) => {
        e.dataTransfer.setData('text/plain', item.name);
        e.dataTransfer.setData('application/x-entity-tag', item.name);
        e.dataTransfer.effectAllowed = 'copy';
    };

    return (
        <div className="mb-1">
            <button
                onClick={toggleOpen}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-[var(--card)] rounded-lg transition-colors"
            >
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                {icon}
                <span className="font-medium">{title}</span>
            </button>

            {open && (
                <div className="ml-4 mt-1 space-y-0.5">
                    {items.map((item) => (
                        <div
                            key={item.id}
                            draggable
                            onDragStart={(e) => handleDragStart(e, item)}
                            className="flex items-center justify-between group px-3 py-1.5 text-sm rounded-lg hover:bg-[var(--card)] cursor-grab active:cursor-grabbing transition-colors"
                            style={{ color: "var(--foreground-muted)" }}
                        >
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "var(--accent)" }} />
                                <span className="truncate">{item.name}</span>
                            </div>
                            {onDelete && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        e.preventDefault();
                                        onDelete(item.id);
                                    }}
                                    className="p-1 rounded hover:bg-red-500/20 transition-colors opacity-0 group-hover:opacity-100"
                                    title="Sil"
                                >
                                    <Trash2 size={14} className="text-red-400" />
                                </button>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}


// SavedImagesSection - Thumbnail grid ile kaydedilen görseller
interface SavedImagesSectionProps {
    items: { id: string; name: string; imageUrl?: string }[];
    onDelete?: (id: string) => void;
}

function SavedImagesSection({ items, onDelete }: SavedImagesSectionProps) {
    const [hoveredId, setHoveredId] = useState<string | null>(null);
    const [userOverride, setUserOverride] = useState<boolean | null>(null);

    const open = userOverride !== null ? userOverride : items.length > 0;

    useEffect(() => {
        setUserOverride(null);
    }, [items.length]);

    const toggleOpen = () => {
        setUserOverride(!open);
    };

    const handleDragStart = (e: React.DragEvent, item: { id: string; name: string; imageUrl?: string }) => {
        const url = item.imageUrl || '';
        e.dataTransfer.setData('text/plain', url || item.name);
        e.dataTransfer.setData('application/x-asset-url', url); // Changed from x-image-url
        e.dataTransfer.setData('application/x-entity-tag', item.name);

        // Detect type
        const isVideo = url.match(/\.(mp4|mov|webm)(\?.*)?$/i);
        e.dataTransfer.setData('application/x-asset-type', isVideo ? 'video' : 'image');

        e.dataTransfer.effectAllowed = 'copy';
    };

    return (
        <div className="mb-1">
            <button
                onClick={toggleOpen}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-[var(--card)] rounded-lg transition-colors"
            >
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <ImageIcon size={16} />
                <span className="font-medium">Kaydedilen Medya Varlıkları</span>
                {items.length > 0 && (
                    <span className="ml-auto text-xs px-1.5 py-0.5 rounded-full bg-[var(--accent)]/20" style={{ color: "var(--accent)" }}>
                        {items.length}
                    </span>
                )}
            </button>

            {open && (
                <div className="ml-4 mt-2 grid grid-cols-3 gap-1.5">
                    {items.map((item) => (
                        <div
                            key={item.id}
                            draggable
                            onDragStart={(e) => handleDragStart(e, item)}
                            className="relative group aspect-square rounded-lg overflow-hidden cursor-grab active:cursor-grabbing border border-[var(--border)] hover:border-[var(--accent)] transition-colors"
                            onMouseEnter={() => setHoveredId(item.id)}
                            onMouseLeave={() => setHoveredId(null)}
                            title={item.name}
                        >
                            {item.imageUrl ? (
                                <img
                                    src={item.imageUrl}
                                    alt={item.name}
                                    className="w-full h-full object-cover"
                                />
                            ) : (
                                <div className="w-full h-full flex items-center justify-center bg-[var(--card)]">
                                    <ImageIcon size={20} style={{ color: "var(--foreground-muted)" }} />
                                </div>
                            )}

                            {/* Delete button overlay */}
                            {onDelete && hoveredId === item.id && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onDelete(item.id);
                                    }}
                                    className="absolute top-1 right-1 p-1 rounded bg-black/60 hover:bg-red-500/80 transition-colors"
                                    title="Sil"
                                >
                                    <Trash2 size={12} className="text-white" />
                                </button>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

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
}

export function Sidebar({ activeProjectId, onProjectChange, onProjectDelete, sessionId, refreshKey, onSendPrompt, onSetInputText, onPluginsLoaded, onAssetRestore }: SidebarProps) {
    const { theme } = useTheme();
    const { user, logout } = useAuth();
    const toast = useToast();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [searchOpen, setSearchOpen] = useState(false);
    const [newProjectOpen, setNewProjectOpen] = useState(false);
    const [adminOpen, setAdminOpen] = useState(false);
    const [trashOpen, setTrashOpen] = useState(false);
    const [gridGeneratorOpen, setGridGeneratorOpen] = useState(false);
    const [savedImagesOpen, setSavedImagesOpen] = useState(false);
    const [userMenuOpen, setUserMenuOpen] = useState(false);
    const [projects, setProjects] = useState<{ id: string; name: string; active: boolean; category?: string; description?: string }[]>([]);
    const [isLoadingEntities, setIsLoadingEntities] = useState(false);
    const [isLoadingProjects, setIsLoadingProjects] = useState(false);
    const [entitySearchQuery, setEntitySearchQuery] = useState("");

    // Drag-and-drop reorder state
    const [dragProjectId, setDragProjectId] = useState<string | null>(null);
    const [dragOverProjectId, setDragOverProjectId] = useState<string | null>(null);

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
    };

    const handleProjectDragOver = (e: React.DragEvent, projectId: string) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        if (projectId !== dragProjectId) setDragOverProjectId(projectId);
    };

    const handleProjectDrop = (e: React.DragEvent, targetId: string) => {
        e.preventDefault();
        if (!dragProjectId || dragProjectId === targetId) return;
        const fromIdx = projects.findIndex(p => p.id === dragProjectId);
        const toIdx = projects.findIndex(p => p.id === targetId);
        if (fromIdx === -1 || toIdx === -1) return;
        const reordered = [...projects];
        const [moved] = reordered.splice(fromIdx, 1);
        reordered.splice(toIdx, 0, moved);
        setProjects(reordered);
        localStorage.setItem('projectOrder', JSON.stringify(reordered.map(p => p.id)));
        setDragProjectId(null);
        setDragOverProjectId(null);
    };

    const handleProjectDragEnd = () => {
        setDragProjectId(null);
        setDragOverProjectId(null);
    };

    // Keyboard shortcuts
    useKeyboardShortcuts({
        shortcuts: [
            { ...SHORTCUTS.SEARCH, action: () => setSearchOpen(true) },
            { ...SHORTCUTS.NEW_PROJECT, action: () => setNewProjectOpen(true) },
            { ...SHORTCUTS.SETTINGS, action: () => setSettingsOpen(true) },
            { ...SHORTCUTS.GRID, action: () => setGridGeneratorOpen(true) },
            { ...SHORTCUTS.ADMIN, action: () => setAdminOpen(true) },
            {
                ...SHORTCUTS.ESCAPE,
                action: () => {
                    // Close any open modal
                    if (searchOpen) setSearchOpen(false);
                    else if (settingsOpen) setSettingsOpen(false);
                    else if (newProjectOpen) setNewProjectOpen(false);
                    else if (adminOpen) setAdminOpen(false);
                    else if (trashOpen) setTrashOpen(false);
                    else if (gridGeneratorOpen) setGridGeneratorOpen(false);
                    else if (userMenuOpen) setUserMenuOpen(false);
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

    // Entity states - API'den gelecek
    const [characters, setCharacters] = useState<{ id: string; name: string }[]>([]);
    const [locations, setLocations] = useState<{ id: string; name: string }[]>([]);
    const [savedImages, setSavedImages] = useState<{ id: string; name: string; imageUrl?: string }[]>([]);
    const [brands, setBrands] = useState<{ id: string; name: string }[]>([]);
    const [creativePlugins, setCreativePlugins] = useState<CreativePlugin[]>([]);

    // Filtrelenmiş entity'ler (arama için)
    const filteredCharacters = characters.filter(c =>
        c.name.toLowerCase().includes(entitySearchQuery.toLowerCase())
    );
    const filteredLocations = locations.filter(l =>
        l.name.toLowerCase().includes(entitySearchQuery.toLowerCase())
    );
    const filteredSavedImages = savedImages.filter(w =>
        w.name.toLowerCase().includes(entitySearchQuery.toLowerCase())
    );
    const filteredBrands = brands.filter(b =>
        b.name.toLowerCase().includes(entitySearchQuery.toLowerCase())
    );

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

    // Backend'den creative plugins'i yükle
    useEffect(() => {
        const fetchCreativePlugins = async () => {
            if (!sessionId) return;
            try {
                const plugins = await getCreativePlugins(sessionId);
                const pluginList: CreativePlugin[] = plugins.map((p: CreativePluginData) => ({
                    id: p.id,
                    name: p.name,
                    description: p.description || '',
                    author: 'Ben',
                    isPublic: p.is_public,
                    config: {},
                    createdAt: new Date(),
                    downloads: p.usage_count,
                    rating: 0
                }));
                setCreativePlugins(pluginList);
            } catch (error) {
                console.error('Creative plugins yükleme hatası:', error);
                setCreativePlugins([]);
            }
        };

        fetchCreativePlugins();
    }, [sessionId, refreshKey]);

    // Plugin listesi değiştiğinde parent'a bildir
    useEffect(() => {
        if (onPluginsLoaded) {
            const simplified = creativePlugins.map(p => {
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
    }, [creativePlugins, onPluginsLoaded]);

    // API'den entity'leri çek
    useEffect(() => {
        const fetchEntities = async () => {
            if (!sessionId) return;

            setIsLoadingEntities(true);
            try {
                const entities = await getEntities(sessionId);

                // getEntities artık her zaman array döndürüyor (API düzeltildi)
                // Yine de güvenlik için kontrol ekle
                const entityList = Array.isArray(entities) ? entities : [];

                // Entity'leri türlerine göre ayır
                const chars = entityList
                    .filter((e: Entity) => e.entity_type === 'character')
                    .map((e: Entity) => ({ id: e.id, name: e.tag || e.name }));
                const locs = entityList
                    .filter((e: Entity) => e.entity_type === 'location')
                    .map((e: Entity) => ({ id: e.id, name: e.tag || e.name }));
                const ward = entityList
                    .filter((e: Entity) => e.entity_type === 'wardrobe')
                    .map((e: Entity) => ({ id: e.id, name: e.tag || e.name, imageUrl: e.reference_image_url }));
                const brandList = entityList
                    .filter((e: Entity) => e.entity_type === 'brand')
                    .map((e: Entity) => ({ id: e.id, name: e.tag || e.name }));

                setCharacters(chars);
                setLocations(locs);
                setSavedImages(ward);
                setBrands(brandList);
            } catch (error) {
                console.error('Entity yükleme hatası:', error);
                // Hata durumunda boş göster
                setCharacters([]);
                setLocations([]);
                setSavedImages([]);
                setBrands([]);
            } finally {
                setIsLoadingEntities(false);
            }
        };

        fetchEntities();
    }, [sessionId, refreshKey]);
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

    // Confirm delete handlers - API'ye bağlı
    const confirmDeleteCharacter = (id: string) => {
        const char = characters.find(c => c.id === id);
        if (!char) return;
        setDeleteConfirm({
            isOpen: true,
            itemId: id,
            itemName: char.name,
            itemType: "karakter",
            onConfirm: async () => {
                // Backend'den sil
                const success = await deleteEntity(id);
                if (success) {
                    moveToTrash(id, char.name, "karakter", char);
                    setCharacters(characters.filter(c => c.id !== id));
                    toast.success(`"${char.name}" çöp kutusuna taşındı`);
                } else {
                    toast.error('Karakter silinemedi');
                }
            }
        });
    };

    const confirmDeleteLocation = (id: string) => {
        const loc = locations.find(l => l.id === id);
        if (!loc) return;
        setDeleteConfirm({
            isOpen: true,
            itemId: id,
            itemName: loc.name,
            itemType: "lokasyon",
            onConfirm: async () => {
                const success = await deleteEntity(id);
                if (success) {
                    moveToTrash(id, loc.name, "lokasyon", loc);
                    setLocations(locations.filter(l => l.id !== id));
                    toast.success(`"${loc.name}" çöp kutusuna taşındı`);
                } else {
                    toast.error('Lokasyon silinemedi');
                }
            }
        });
    };

    const confirmDeleteWardrobe = (id: string) => {
        const item = savedImages.find((w: { id: string; name: string; imageUrl?: string }) => w.id === id);
        if (!item) return;
        setDeleteConfirm({
            isOpen: true,
            itemId: id,
            itemName: item.name,
            itemType: "wardrobe",
            onConfirm: async () => {
                const success = await deleteEntity(id);
                if (success) {
                    moveToTrash(id, item.name, "wardrobe", item, item.imageUrl as string | undefined);
                    setSavedImages(savedImages.filter((w: { id: string; name: string; imageUrl?: string }) => w.id !== id));
                    toast.success(`"${item.name}" çöp kutusuna taşındı`);
                } else {
                    toast.error('Görsel silinemedi');
                }
            }
        });
    };

    const confirmDeleteBrand = (id: string) => {
        const item = brands.find(b => b.id === id);
        if (!item) return;
        setDeleteConfirm({
            isOpen: true,
            itemId: id,
            itemName: item.name,
            itemType: "brand",
            onConfirm: async () => {
                const success = await deleteEntity(id);
                if (success) {
                    moveToTrash(id, item.name, "brand", item);
                    setBrands(brands.filter(b => b.id !== id));
                    toast.success(`"${item.name}" çöp kutusuna taşındı`);
                } else {
                    toast.error('Marka silinemedi');
                }
            }
        });
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
                    case "karakter":
                    case "character":  // Backend alias
                        console.log("Adding to characters");
                        setCharacters([...characters, {
                            id: restored.id,
                            name: restored.name || item.name
                        }]);
                        break;
                    case "lokasyon":
                    case "location":  // Backend alias
                        console.log("Adding to locations");
                        setLocations([...locations, {
                            id: restored.id,
                            name: restored.name || item.name
                        }]);
                        break;
                    case "wardrobe":
                        console.log("Adding to saved images");
                        setSavedImages([...savedImages, {
                            id: restored.id,
                            name: restored.name || item.name,
                            imageUrl: (item as { imageUrl?: string })?.imageUrl
                        }]);
                        break;
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
                    case "marka":
                    case "brand":  // Backend alias
                        console.log("Adding brand to characters");
                        setCharacters([...characters, {
                            id: restored.id,
                            name: restored.name || item.name
                        }]);
                        break;
                    default:
                        console.log("Unknown type:", item.type);
                }
            } else {
                console.log("result.success:", result.success);
                console.log("result.restored:", result.restored);
            }

            // Çöp kutusundan kaldır
            setTrashItems(trashItems.filter(t => t.id !== item.id));
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
            setTrashItems(trashItems.filter(t => t.id !== id));
            toast.success('Kalıcı olarak silindi');
        } catch (error) {
            console.error('Kalıcı silme hatası:', error);
            toast.error('Kalıcı silme başarısız oldu');
        }
    };

    // Delete all trash items
    const handleDeleteAll = async () => {
        try {
            for (const item of trashItems) {
                await permanentDeleteTrashItem(item.id);
            }
            setTrashItems([]);
        } catch (error) {
            console.error('Tümünü silme hatası:', error);
        }
    };

    // Delete multiple selected items
    const handleDeleteMultiple = async (ids: string[]) => {
        try {
            for (const id of ids) {
                await permanentDeleteTrashItem(id);
            }
            setTrashItems(trashItems.filter(t => !ids.includes(t.id)));
        } catch (error) {
            console.error('Çoklu silme hatası:', error);
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
            case 'kisisel': return { bg: 'rgba(34,197,94,0.15)', text: '#22c55e' };
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
                        <span className="text-4xl">🫑</span>
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
                            background: 'rgba(74, 222, 128, 0.10)',
                            border: '1px solid rgba(74, 222, 128, 0.25)',
                            color: '#4ade80'
                        }}
                    >
                        <Grid3x3 size={20} />
                        <span className="rail-label" style={{ color: '#4ade80' }}>Grid Oluşturucu</span>
                    </button>

                    <button
                        className="rail-feature-btn"
                        onClick={() => setSavedImagesOpen(true)}
                        style={{
                            background: 'rgba(56, 189, 248, 0.10)',
                            border: '1px solid rgba(56, 189, 248, 0.25)',
                            color: '#38bdf8'
                        }}
                    >
                        <ImageIcon size={20} />
                        <span className="rail-label" style={{ color: '#60a5fa' }}>Kaydedilenler</span>
                    </button>

                    <button
                        className="rail-feature-btn"
                        onClick={() => setCommunityHubOpen(true)}
                        style={{
                            background: 'rgba(167, 139, 250, 0.10)',
                            border: '1px solid rgba(167, 139, 250, 0.25)',
                            color: '#a78bfa'
                        }}
                    >
                        <Users size={20} />
                        <span className="rail-label" style={{ color: '#a78bfa' }}>Topluluk</span>
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

                    <button className="rail-btn" onClick={() => setAdminOpen(true)}>
                        <Shield size={24} />
                        <span className="rail-label">Admin</span>
                    </button>

                    <div className="rail-divider" />

                    {/* User avatar */}
                    <div style={{ position: 'relative' }}>
                        <div
                            className="rail-btn"
                            onClick={() => setUserMenuOpen(!userMenuOpen)}
                            style={{ cursor: 'pointer', padding: '0 8px' }}
                        >
                            <div className="rail-avatar">
                                {user?.avatar_url ? (
                                    <img src={user.avatar_url} alt={user.full_name || "User"} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                ) : (
                                    <span>{(user?.full_name || user?.email || "U")[0].toUpperCase()}</span>
                                )}
                            </div>
                            <span className="rail-label">{user?.full_name || 'Profil'}</span>
                        </div>

                        {/* User dropdown */}
                        {userMenuOpen && (
                            <div
                                style={{
                                    position: 'fixed', bottom: 16, left: 72,
                                    width: 220, borderRadius: 12, overflow: 'hidden',
                                    background: 'var(--card)', border: '1px solid var(--border)',
                                    boxShadow: '0 8px 32px rgba(0,0,0,0.15)', zIndex: 99999,
                                    backdropFilter: 'blur(20px)'
                                }}
                            >
                                <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
                                    <div style={{ fontSize: 13, fontWeight: 600 }}>{user?.full_name || "User"}</div>
                                    <div style={{ fontSize: 11, color: 'var(--foreground-muted)' }}>{user?.email}</div>
                                </div>
                                <button
                                    onClick={() => { setUserMenuOpen(false); logout(); }}
                                    style={{
                                        width: '100%', display: 'flex', alignItems: 'center', gap: 8,
                                        padding: '8px 12px', fontSize: 13, color: '#ef4444',
                                        background: 'transparent', border: 'none', cursor: 'pointer'
                                    }}
                                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(239,68,68,0.1)')}
                                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                                >
                                    <LogOut size={14} />
                                    Çıkış Yap
                                </button>
                            </div>
                        )}
                    </div>
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
                                            <div
                                                key={project.id}
                                                draggable={!isEditing}
                                                onDragStart={(e) => handleProjectDragStart(e, project.id)}
                                                onDragOver={(e) => handleProjectDragOver(e, project.id)}
                                                onDrop={(e) => handleProjectDrop(e, project.id)}
                                                onDragEnd={handleProjectDragEnd}
                                                className={`project-card-v2 group ${project.active ? 'active' : ''} ${dragProjectId === project.id ? 'opacity-40' : ''} ${dragOverProjectId === project.id ? 'ring-2 ring-[var(--accent)]' : ''}`}
                                                style={{ cursor: isEditing ? 'text' : 'grab' }}
                                                onClick={() => !isEditing && handleProjectClick(project.id)}
                                                onDoubleClick={(e) => {
                                                    e.stopPropagation();
                                                    startEditingProject(project.id, project.name);
                                                }}
                                            >
                                                {/* Drag handle + Thumbnail */}
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
                                                        className="group-hover:!opacity-100"
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
                                        background: 'rgba(74, 222, 128, 0.08)', border: '1px solid rgba(74, 222, 128, 0.15)',
                                        color: 'var(--accent)', fontSize: 13, fontWeight: 500,
                                        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                                        transition: 'all 0.2s ease'
                                    }}
                                    onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(74, 222, 128, 0.15)')}
                                    onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(74, 222, 128, 0.08)')}
                                >
                                    <Plus size={14} />
                                    Yeni Proje
                                </button>
                            </div>
                        </>
                    )}

                    {/* === ENTITIES PANEL === */}
                    {drawerPanel === 'entities' && (
                        <>
                            <div className="drawer-header">
                                <h3>Varlıklar</h3>
                            </div>

                            {/* Entity Search */}
                            <div style={{ padding: '8px 12px' }}>
                                <div style={{ position: 'relative' }}>
                                    <Search size={14} style={{
                                        position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
                                        color: 'var(--foreground-muted)'
                                    }} />
                                    <input
                                        type="text"
                                        placeholder="Varlık ara..."
                                        value={entitySearchQuery}
                                        onChange={(e) => setEntitySearchQuery(e.target.value)}
                                        style={{
                                            width: '100%', padding: '6px 12px 6px 32px',
                                            fontSize: 12, borderRadius: 8, border: '1px solid var(--border)',
                                            background: 'var(--card)', color: 'var(--foreground)', outline: 'none'
                                        }}
                                    />
                                    {entitySearchQuery && (
                                        <button
                                            onClick={() => setEntitySearchQuery("")}
                                            style={{
                                                position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                                                background: 'none', border: 'none', cursor: 'pointer', color: 'var(--foreground-muted)'
                                            }}
                                        >
                                            <X size={12} />
                                        </button>
                                    )}
                                </div>
                            </div>

                            <div style={{ flex: 1, overflowY: 'auto' }}>
                                {/* Characters */}
                                <CollapsibleSection
                                    title="Karakterler"
                                    icon={<Users size={16} />}
                                    items={filteredCharacters}
                                    onDelete={confirmDeleteCharacter}
                                />

                                {/* Locations */}
                                <CollapsibleSection
                                    title="Lokasyonlar"
                                    icon={<MapPin size={16} />}
                                    items={filteredLocations}
                                    onDelete={confirmDeleteLocation}
                                />

                                {/* Brands */}
                                <CollapsibleSection
                                    title="Markalar"
                                    icon={<Tag size={16} />}
                                    items={filteredBrands}
                                    onDelete={confirmDeleteBrand}
                                />

                                {/* Creative Plugins — başlık her zaman görünür */}
                                <div style={{ marginTop: 8 }}>
                                    <div style={{
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                        padding: '8px 16px'
                                    }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 500, color: 'var(--foreground-muted)' }}>
                                            <Puzzle size={14} />
                                            <span>Yaratıcı Eklentiler</span>
                                            {creativePlugins.length > 0 && (
                                                <span style={{ opacity: 0.6 }}>({creativePlugins.length})</span>
                                            )}
                                        </div>
                                    </div>
                                    {creativePlugins.length > 0 ? (
                                        <div>
                                            {creativePlugins.map((plugin) => (
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
                                                            background: plugin.isPublic ? '#8b5cf6' : '#f59e0b', flexShrink: 0
                                                        }} />
                                                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{plugin.name}</span>
                                                    </div>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            deleteCreativePlugin(plugin.id).then(success => {
                                                                if (success) {
                                                                    setCreativePlugins(creativePlugins.filter(p => p.id !== plugin.id));
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

            <AdminPanelModal
                isOpen={adminOpen}
                onClose={() => setAdminOpen(false)}
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
                onDelete={(id) => setCreativePlugins(creativePlugins.filter(p => p.id !== id))}
                onUse={(plugin) => {
                    const setTextFn = onSetInputText || onSendPrompt;
                    if (setTextFn && plugin.config) {
                        const parts: string[] = [];
                        if (plugin.config.style) parts.push(`Stil: ${plugin.config.style}`);
                        if (plugin.config.cameraAngles && plugin.config.cameraAngles.length > 0) {
                            parts.push(`Açılar: ${plugin.config.cameraAngles.join(", ")}`);
                        }
                        if (plugin.config.timeOfDay) parts.push(`Zaman: ${plugin.config.timeOfDay}`);
                        const prompt = plugin.config.promptTemplate
                            ? `[${plugin.name}] ${plugin.config.promptTemplate}${parts.length > 0 ? ` (${parts.join(", ")})` : ""}`
                            : `[${plugin.name}] ${parts.join(", ")} tarzında görsel üret`;
                        setTextFn(prompt);
                    }
                    setPluginDetailOpen(false);
                }}
            />



            <GridGeneratorModal
                isOpen={gridGeneratorOpen}
                onClose={() => setGridGeneratorOpen(false)}
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
                    // Sidebar entity listesinden de kaldır
                    setSavedImages(prev => prev.filter(w => w.id !== id));
                }}
            />
        </>
    );
}
