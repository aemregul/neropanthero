"use client";

import { useState, useEffect, useRef } from "react";
import { X, Search as SearchIcon, User, MapPin, Image, FileText, Loader2 } from "lucide-react";
import { getEntities, getAssets, Entity, GeneratedAsset } from "@/lib/api";

interface SearchModalProps {
    isOpen: boolean;
    onClose: () => void;
    sessionId?: string | null;
}

interface SearchResult {
    id: string;
    type: "character" | "location" | "wardrobe" | "asset";
    name: string;
    description?: string;
}

export function SearchModal({ isOpen, onClose, sessionId }: SearchModalProps) {
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<SearchResult[]>([]);
    const [allItems, setAllItems] = useState<SearchResult[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    // Fetch all entities and assets when modal opens
    useEffect(() => {
        const fetchAllItems = async () => {
            if (!isOpen || !sessionId) return;

            setIsLoading(true);
            try {
                // Fetch entities
                const entities = await getEntities(sessionId);
                const entityResults: SearchResult[] = entities.map((e: Entity) => ({
                    id: e.id,
                    type: e.type as "character" | "location" | "wardrobe",
                    name: e.tag || e.name,
                    description: e.description || e.name
                }));

                // Fetch assets
                const assets = await getAssets(sessionId);
                const assetResults: SearchResult[] = assets.map((a: GeneratedAsset) => ({
                    id: a.id,
                    type: "asset" as const,
                    name: `Asset ${a.id.substring(0, 8)}`,
                    description: a.prompt?.substring(0, 50) || a.asset_type
                }));

                setAllItems([...entityResults, ...assetResults]);
            } catch (error) {
                console.error('Arama verileri yüklenemedi:', error);
                setAllItems([]);
            } finally {
                setIsLoading(false);
            }
        };

        fetchAllItems();
    }, [isOpen, sessionId]);

    useEffect(() => {
        if (isOpen && inputRef.current) {
            inputRef.current.focus();
        }
        if (!isOpen) {
            setQuery("");
            setResults([]);
        }
    }, [isOpen]);

    // Filter results based on query
    useEffect(() => {
        if (query.length > 0) {
            const filtered = allItems.filter(
                (item) =>
                    item.name.toLowerCase().includes(query.toLowerCase()) ||
                    item.description?.toLowerCase().includes(query.toLowerCase())
            );
            setResults(filtered);
        } else {
            setResults([]);
        }
    }, [query, allItems]);

    const getIcon = (type: string) => {
        switch (type) {
            case "character":
                return <User size={16} className="text-blue-400" />;
            case "location":
                return <MapPin size={16} className="text-green-400" />;
            case "wardrobe":
                return <FileText size={16} className="text-yellow-400" />;
            case "asset":
                return <Image size={16} style={{ color: '#C9A84C' }} />;
            default:
                return null;
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal */}
            <div
                className="relative w-full max-w-lg rounded-xl shadow-2xl overflow-hidden"
                style={{ background: "var(--card)", border: "1px solid var(--border)" }}
            >
                {/* Search Input */}
                <div className="flex items-center gap-3 p-4 border-b" style={{ borderColor: "var(--border)" }}>
                    {isLoading ? (
                        <Loader2 size={20} className="animate-spin" style={{ color: "var(--foreground-muted)" }} />
                    ) : (
                        <SearchIcon size={20} style={{ color: "var(--foreground-muted)" }} />
                    )}
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Karakter, lokasyon veya asset ara..."
                        className="flex-1 bg-transparent outline-none text-sm"
                        style={{ color: "var(--foreground)" }}
                    />
                    <button
                        onClick={onClose}
                        className="p-1 rounded hover:bg-[var(--background)] transition-colors"
                    >
                        <X size={18} style={{ color: "var(--foreground-muted)" }} />
                    </button>
                </div>

                {/* Results */}
                <div className="max-h-[300px] overflow-y-auto">
                    {isLoading ? (
                        <div className="p-4 text-center text-sm" style={{ color: "var(--foreground-muted)" }}>
                            Yükleniyor...
                        </div>
                    ) : query.length === 0 ? (
                        <div className="p-4 text-center text-sm" style={{ color: "var(--foreground-muted)" }}>
                            {allItems.length > 0
                                ? `${allItems.length} öğe aranabilir. Aramaya başlamak için yazın...`
                                : "Henüz kayıtlı öğe yok. Sohbette karakter/mekan oluşturun."}
                        </div>
                    ) : results.length === 0 ? (
                        <div className="p-4 text-center text-sm" style={{ color: "var(--foreground-muted)" }}>
                            "{query}" için sonuç bulunamadı
                        </div>
                    ) : (
                        <div className="p-2">
                            {results.map((result) => (
                                <button
                                    key={result.id}
                                    className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-[var(--background)] transition-colors text-left"
                                    onClick={() => {
                                        // TODO: Navigate to result or insert tag
                                        onClose();
                                    }}
                                >
                                    {getIcon(result.type)}
                                    <div>
                                        <div className="text-sm font-medium">{result.name}</div>
                                        {result.description && (
                                            <div className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                                                {result.description}
                                            </div>
                                        )}
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Keyboard shortcut hint */}
                <div className="p-2 border-t text-center" style={{ borderColor: "var(--border)" }}>
                    <span className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                        ESC ile kapat
                    </span>
                </div>
            </div>
        </div>
    );
}
