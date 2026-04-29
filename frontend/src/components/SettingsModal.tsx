"use client";

import { useState, useEffect } from "react";
import { X, Moon, Sun, Palette, Bell, Lock, Info, Globe, Loader2, Save } from "lucide-react";
import { useTheme } from "./ThemeProvider";
import { getUserSettings, updateUserSettings, UserSettings } from "@/lib/api";

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
    const { theme, toggleTheme } = useTheme();
    const [settings, setSettings] = useState<UserSettings | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [hasChanges, setHasChanges] = useState(false);

    // Backend'den ayarları yükle
    useEffect(() => {
        const fetchSettings = async () => {
            if (!isOpen) return;

            setIsLoading(true);
            try {
                const data = await getUserSettings();
                setSettings(data);
            } catch (error) {
                console.error('Ayarlar yükleme hatası:', error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchSettings();
    }, [isOpen]);

    const handleUpdateSetting = async (key: keyof UserSettings, value: unknown) => {
        if (!settings) return;

        setSettings({ ...settings, [key]: value });
        setHasChanges(true);
    };

    const handleSave = async () => {
        if (!settings || !hasChanges) return;

        setIsSaving(true);
        try {
            await updateUserSettings({
                language: settings.language,
                notifications_enabled: settings.notifications_enabled,
                auto_save: settings.auto_save,
                default_model: settings.default_model
            });
            setHasChanges(false);
        } catch (error) {
            console.error('Ayar kaydetme hatası:', error);
        } finally {
            setIsSaving(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal */}
            <div
                className="relative w-full max-w-md rounded-xl shadow-2xl"
                style={{ background: "var(--card)", border: "1px solid var(--border)" }}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: "var(--border)" }}>
                    <h2 className="text-lg font-semibold">Ayarlar</h2>
                    <div className="flex items-center gap-2">
                        {hasChanges && (
                            <button
                                onClick={handleSave}
                                disabled={isSaving}
                                className="flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg transition-colors"
                                style={{ background: "var(--accent)", color: "var(--background)" }}
                            >
                                {isSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                                Kaydet
                            </button>
                        )}
                        <button
                            onClick={onClose}
                            className="p-1 rounded-lg hover:bg-[var(--background)] transition-colors"
                        >
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="p-4 space-y-4">
                    {isLoading ? (
                        <div className="flex items-center justify-center py-10">
                            <Loader2 className="animate-spin" size={24} style={{ color: "var(--accent)" }} />
                        </div>
                    ) : (
                        <>
                            {/* Appearance */}
                            <div>
                                <div className="flex items-center gap-2 text-sm font-medium mb-3" style={{ color: "var(--foreground-muted)" }}>
                                    <Palette size={16} />
                                    <span>Görünüm</span>
                                </div>

                                {/* Theme Toggle */}
                                <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: "var(--background)" }}>
                                    <div className="flex items-center gap-2">
                                        {theme === "dark" ? <Moon size={18} /> : <Sun size={18} />}
                                        <span className="text-sm">Tema</span>
                                    </div>
                                    <button
                                        onClick={toggleTheme}
                                        className="relative w-14 h-7 rounded-full transition-all duration-300 ease-in-out"
                                        style={{
                                            background: theme === "dark" ? "var(--accent)" : "rgba(120, 120, 128, 0.32)",
                                            boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.1)"
                                        }}
                                    >
                                        <div
                                            className="absolute top-0.5 w-6 h-6 rounded-full bg-white shadow-lg transition-all duration-300 ease-in-out"
                                            style={{
                                                left: theme === "dark" ? "30px" : "2px",
                                                boxShadow: "0 2px 4px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.05)"
                                            }}
                                        />
                                    </button>
                                </div>
                                <p className="text-xs mt-1 px-1" style={{ color: "var(--foreground-muted)" }}>
                                    {theme === "dark" ? "Koyu tema aktif" : "Açık tema aktif"}
                                </p>
                            </div>

                            {/* Language */}
                            <div>
                                <div className="flex items-center gap-2 text-sm font-medium mb-3" style={{ color: "var(--foreground-muted)" }}>
                                    <Globe size={16} />
                                    <span>Dil</span>
                                </div>
                                <div className="flex gap-2">
                                    {['tr', 'en'].map(lang => (
                                        <button
                                            key={lang}
                                            onClick={() => handleUpdateSetting('language', lang)}
                                            className="flex-1 px-4 py-2 rounded-lg text-sm transition-colors"
                                            style={{
                                                background: settings?.language === lang ? "var(--accent)" : "var(--background)",
                                                color: settings?.language === lang ? "var(--background)" : "var(--foreground)"
                                            }}
                                        >
                                            {lang === 'tr' ? '🇹🇷 Türkçe' : '🇺🇸 English'}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Notifications */}
                            <div>
                                <div className="flex items-center gap-2 text-sm font-medium mb-3" style={{ color: "var(--foreground-muted)" }}>
                                    <Bell size={16} />
                                    <span>Bildirimler</span>
                                </div>
                                <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: "var(--background)" }}>
                                    <span className="text-sm">Bildirimler aktif</span>
                                    <button
                                        onClick={() => handleUpdateSetting('notifications_enabled', !settings?.notifications_enabled)}
                                        className="relative w-14 h-7 rounded-full transition-all duration-300 ease-in-out"
                                        style={{
                                            background: settings?.notifications_enabled ? "var(--accent)" : "rgba(120, 120, 128, 0.32)",
                                            boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.1)"
                                        }}
                                    >
                                        <div
                                            className="absolute top-0.5 w-6 h-6 rounded-full bg-white shadow-lg transition-all duration-300 ease-in-out"
                                            style={{
                                                left: settings?.notifications_enabled ? "30px" : "2px",
                                                boxShadow: "0 2px 4px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.05)"
                                            }}
                                        />
                                    </button>
                                </div>
                            </div>

                            {/* Auto Save */}
                            <div>
                                <div className="flex items-center gap-2 text-sm font-medium mb-3" style={{ color: "var(--foreground-muted)" }}>
                                    <Lock size={16} />
                                    <span>Otomatik Kayıt</span>
                                </div>
                                <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: "var(--background)" }}>
                                    <span className="text-sm">Değişiklikleri otomatik kaydet</span>
                                    <button
                                        onClick={() => handleUpdateSetting('auto_save', !settings?.auto_save)}
                                        className="relative w-14 h-7 rounded-full transition-all duration-300 ease-in-out"
                                        style={{
                                            background: settings?.auto_save ? "var(--accent)" : "rgba(120, 120, 128, 0.32)",
                                            boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.1)"
                                        }}
                                    >
                                        <div
                                            className="absolute top-0.5 w-6 h-6 rounded-full bg-white shadow-lg transition-all duration-300 ease-in-out"
                                            style={{
                                                left: settings?.auto_save ? "30px" : "2px",
                                                boxShadow: "0 2px 4px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.05)"
                                            }}
                                        />
                                    </button>
                                </div>
                            </div>

                            {/* About */}
                            <div>
                                <div className="flex items-center gap-2 text-sm font-medium mb-3" style={{ color: "var(--foreground-muted)" }}>
                                    <Info size={16} />
                                    <span>Hakkında</span>
                                </div>
                                <div className="p-3 rounded-lg text-sm" style={{ background: "var(--background)", color: "var(--foreground-muted)" }}>
                                    <p><strong>Nero Panthero AI Studio</strong></p>
                                    <p className="text-xs mt-1">Versiyon 1.0.0</p>
                                    <p className="text-xs mt-1">Yapay zeka destekli görsel üretim platformu</p>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
