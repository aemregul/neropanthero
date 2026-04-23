"use client";

import { useState, useEffect } from "react";
import { X, Shield, Puzzle, Activity, Zap, TrendingUp, PieChart as PieChartIcon, Loader2 } from "lucide-react";
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, BarChart, Bar, Legend
} from "recharts";
import {
    getAIModels, toggleAIModel,
    getUsageStats, getOverviewStats, getModelDistribution,
    AIModel, UsageStats, OverviewStats, ModelDistributionItem
} from "@/lib/api";

interface AdminPanelModalProps {
    isOpen: boolean;
    onClose: () => void;
}

// Default model distribution (veri yokken)
const defaultModelDistribution: ModelDistributionItem[] = [
    { name: "GPT-4o", value: 0, color: "#C9A84C" },
    { name: "fal.ai", value: 0, color: "#D4B85C" },
    { name: "Kling", value: 0, color: "#3b82f6" },
];



export function AdminPanelModal({ isOpen, onClose }: AdminPanelModalProps) {
    const [activeTab, setActiveTab] = useState<"overview" | "models" | "analytics">("overview");

    // Backend data states
    const [models, setModels] = useState<AIModel[]>([]);

    const [usageData, setUsageData] = useState<UsageStats[]>([]);
    const [overviewStats, setOverviewStats] = useState<OverviewStats | null>(null);
    const [modelDistribution, setModelDistribution] = useState<ModelDistributionItem[]>(defaultModelDistribution);
    const [isLoading, setIsLoading] = useState(true);
    const [modelCategoryFilter, setModelCategoryFilter] = useState<string>("all");



    // Fetch data from backend — her API bağımsız, biri hata verse diğerleri çalışır
    useEffect(() => {
        const fetchData = async () => {
            if (!isOpen) return;

            setIsLoading(true);

            // Her API'yi bağımsız çağır — biri başarısız olunca diğerlerini engellemesin
            const results = await Promise.allSettled([
                getAIModels(),
                getUsageStats(7),
                getOverviewStats(),
                getModelDistribution()
            ]);

            if (results[0].status === 'fulfilled') setModels(results[0].value);
            else console.error('Models fetch failed:', results[0].reason);

            if (results[1].status === 'fulfilled') setUsageData(results[1].value);
            else console.error('Usage stats fetch failed:', results[1].reason);

            if (results[2].status === 'fulfilled') setOverviewStats(results[2].value);
            else console.error('Overview stats fetch failed:', results[2].reason);

            if (results[3].status === 'fulfilled') {
                const dist = results[3].value;
                setModelDistribution(dist.length > 0 ? dist : defaultModelDistribution);
            } else console.error('Distribution fetch failed:', results[3].reason);

            setIsLoading(false);
        };

        fetchData();
    }, [isOpen]);

    const handleToggleModel = async (modelId: string, currentState: boolean) => {
        try {
            const updated = await toggleAIModel(modelId, !currentState);
            setModels(models.map(m => m.id === updated.id ? updated : m));
        } catch (error) {
            console.error('Model toggle hatası:', error);
        }
    };


    if (!isOpen) return null;

    // Convert usage data for charts
    const chartData = usageData.map(s => ({
        day: s.date,
        calls: s.api_calls,
        images: s.images_generated,
        videos: s.videos_generated
    }));

    // Calculate totals from usage data
    const totalCalls = usageData.reduce((sum, s) => sum + s.api_calls, 0);
    const totalImages = usageData.reduce((sum, s) => sum + s.images_generated, 0);
    const totalVideos = usageData.reduce((sum, s) => sum + s.videos_generated, 0);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/70 backdrop-blur-md"
                onClick={onClose}
            />

            {/* Modal */}
            <div
                className="relative w-full max-w-4xl max-h-[85vh] rounded-2xl shadow-2xl overflow-hidden"
                style={{ background: "var(--card)", border: "1px solid var(--border)" }}
            >
                {/* Header */}
                <div
                    className="flex items-center justify-between p-5 border-b"
                    style={{ borderColor: "var(--border)", background: "linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, transparent 100%)" }}
                >
                    <div className="flex items-center gap-3">
                        <div
                            className="p-2 rounded-xl"
                            style={{ background: "rgba(34, 197, 94, 0.2)" }}
                        >
                            <Shield size={24} style={{ color: "var(--accent)" }} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">Yönetim Paneli</h2>
                            <p className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                                Sistem yönetimi ve AI model kontrolü
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

                {/* Tabs */}
                <div className="flex gap-1 p-2 mx-4 mt-4 rounded-xl" style={{ background: "var(--background)" }}>
                    {[
                        { id: "overview", label: "Genel Bakış", icon: Activity },
                        { id: "models", label: "AI Modeller", icon: Puzzle },

                        { id: "analytics", label: "Analitik", icon: TrendingUp },
                    ].map((tab) => {
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                                className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm rounded-lg ${isActive ? "admin-tab-active" : "admin-tab"}`}
                            >
                                <tab.icon size={16} />
                                {tab.label}
                            </button>
                        );
                    })}
                </div>

                {/* Content */}
                <div className="p-4 overflow-y-auto max-h-[calc(85vh-180px)]">
                    {isLoading ? (
                        <div className="flex items-center justify-center py-20">
                            <Loader2 className="animate-spin" size={32} style={{ color: "var(--accent)" }} />
                        </div>
                    ) : (
                        <>
                            {/* Overview Tab */}
                            {activeTab === "overview" && (
                                <div className="space-y-4">
                                    {/* Stats Grid */}
                                    <div className="grid grid-cols-4 gap-3">
                                        {[
                                            { label: "Toplam Çağrı", value: overviewStats?.total_messages || 0, icon: Zap, color: "#C9A84C" },
                                            { label: "Görseller", value: overviewStats?.total_images || 0, icon: PieChartIcon, color: "#D4B85C" },
                                            { label: "Videolar", value: overviewStats?.total_videos || 0, icon: TrendingUp, color: "#3b82f6" },
                                            { label: "Aktif Model", value: overviewStats?.active_models || 0, icon: Activity, color: "#f59e0b" },
                                        ].map((stat) => (
                                            <div
                                                key={stat.label}
                                                className="p-4 rounded-xl relative overflow-hidden"
                                                style={{ background: "var(--background)" }}
                                            >
                                                <div
                                                    className="absolute top-0 right-0 w-16 h-16 rounded-full opacity-20"
                                                    style={{ background: stat.color, transform: "translate(30%, -30%)" }}
                                                />
                                                <stat.icon size={20} style={{ color: stat.color }} className="mb-2" />
                                                <div className="text-2xl font-bold">{stat.value}</div>
                                                <div className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                                                    {stat.label}
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    {/* Usage Chart */}
                                    <div className="p-4 rounded-xl" style={{ background: "var(--background)" }}>
                                        <h3 className="text-sm font-medium mb-4">Son 7 Gün API Kullanımı</h3>
                                        <ResponsiveContainer width="100%" height={200}>
                                            <LineChart data={chartData}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                                                <XAxis dataKey="day" stroke="rgba(255,255,255,0.5)" fontSize={12} />
                                                <YAxis stroke="rgba(255,255,255,0.5)" fontSize={12} />
                                                <Tooltip
                                                    contentStyle={{
                                                        background: "var(--card)",
                                                        border: "1px solid var(--border)",
                                                        borderRadius: "8px"
                                                    }}
                                                />
                                                <Line
                                                    type="monotone"
                                                    dataKey="calls"
                                                    stroke="#C9A84C"
                                                    strokeWidth={2}
                                                    dot={{ fill: "#C9A84C", strokeWidth: 2 }}
                                                    name="API Çağrısı"
                                                />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>

                                    {/* Active Models Quick View */}
                                    <div className="p-4 rounded-xl" style={{ background: "var(--background)" }}>
                                        <h3 className="text-sm font-medium mb-3">Aktif Modeller</h3>
                                        <div className="flex flex-wrap gap-2">
                                            {models.filter(m => m.is_enabled).map((model) => (
                                                <span
                                                    key={model.id}
                                                    className="px-3 py-1.5 rounded-full text-sm flex items-center gap-2"
                                                    style={{ background: "rgba(201, 168, 76, 0.2)", color: "#C9A84C" }}
                                                >
                                                    <span>{model.icon}</span>
                                                    {model.display_name}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Models Tab */}
                            {activeTab === "models" && (
                                <div className="space-y-3">
                                    {/* Kategori Filtre Tabları */}
                                    <div className="flex gap-1.5 flex-wrap pb-2" style={{ borderBottom: '1px solid var(--border)' }}>
                                        {[
                                            { id: "all", label: "Tümü", icon: "🔮" },
                                            { id: "image", label: "Görsel", icon: "🖼️" },
                                            { id: "edit", label: "Düzenleme", icon: "🎨" },
                                            { id: "video", label: "Video", icon: "🎬" },
                                            { id: "utility", label: "Araçlar", icon: "🔧" },
                                            { id: "audio", label: "Ses", icon: "🔊" },
                                            { id: "llm", label: "LLM", icon: "🤖" },
                                        ].map((cat) => {
                                            const count = cat.id === "all"
                                                ? models.length
                                                : models.filter(m => m.model_type === cat.id).length;
                                            const isActive = modelCategoryFilter === cat.id;
                                            return (
                                                <button
                                                    key={cat.id}
                                                    onClick={() => setModelCategoryFilter(cat.id)}
                                                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg transition-all duration-200 ${isActive ? 'font-medium shadow-sm' : 'opacity-60 hover:opacity-100'
                                                        }`}
                                                    style={{
                                                        background: isActive ? 'var(--accent)' : 'var(--background)',
                                                        color: isActive ? 'var(--background)' : 'var(--foreground)',
                                                        border: isActive ? 'none' : '1px solid var(--border)',
                                                    }}
                                                >
                                                    <span>{cat.icon}</span>
                                                    {cat.label}
                                                    <span className={`ml-0.5 px-1.5 py-0.5 rounded-full text-[10px] ${isActive ? 'bg-white/20' : ''
                                                        }`} style={{ background: isActive ? 'rgba(255,255,255,0.2)' : 'var(--card)' }}>
                                                        {count}
                                                    </span>
                                                </button>
                                            );
                                        })}
                                    </div>

                                    {/* Filtrelenmiş Model Listesi */}
                                    {models
                                        .filter(m => modelCategoryFilter === "all" || m.model_type === modelCategoryFilter)
                                        .map((model) => (
                                            <div
                                                key={model.id}
                                                className="flex items-center justify-between p-4 rounded-xl"
                                                style={{ background: "var(--background)" }}
                                            >
                                                <div className="flex items-center gap-3">
                                                    <span className="text-2xl">{model.icon}</span>
                                                    <div>
                                                        <div className="font-medium flex items-center gap-2">
                                                            {model.display_name}
                                                            <span className="px-2 py-0.5 text-xs rounded" style={{ background: "var(--card)" }}>
                                                                {model.model_type.toUpperCase()}
                                                            </span>
                                                        </div>
                                                        <div className="text-xs" style={{ color: "var(--foreground-muted)" }}>
                                                            {model.provider} • {model.description}
                                                        </div>
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => handleToggleModel(model.id, model.is_enabled)}
                                                    className={`relative w-12 h-6 rounded-full transition-colors ${model.is_enabled ? 'bg-green-500' : 'bg-gray-600'}`}
                                                >
                                                    <div
                                                        className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${model.is_enabled ? 'translate-x-7' : 'translate-x-1'}`}
                                                    />
                                                </button>
                                            </div>
                                        ))}
                                </div>
                            )}



                            {/* Analytics Tab */}
                            {activeTab === "analytics" && (
                                <div className="space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        {/* Pie Chart - Model Distribution */}
                                        <div className="p-4 rounded-xl" style={{ background: "var(--background)" }}>
                                            <h3 className="text-sm font-medium mb-4">Model Kullanım Dağılımı</h3>
                                            <ResponsiveContainer width="100%" height={200}>
                                                <PieChart>
                                                    <Pie
                                                        data={modelDistribution}
                                                        cx="50%"
                                                        cy="50%"
                                                        innerRadius={50}
                                                        outerRadius={80}
                                                        paddingAngle={5}
                                                        dataKey="value"
                                                    >
                                                        {modelDistribution.map((entry, index) => (
                                                            <Cell key={`cell-${index}`} fill={entry.color} />
                                                        ))}
                                                    </Pie>
                                                    <Tooltip
                                                        contentStyle={{
                                                            background: "var(--card)",
                                                            border: "1px solid var(--border)",
                                                            borderRadius: "8px"
                                                        }}
                                                        formatter={(value) => [`%${value}`, ""]}
                                                    />
                                                </PieChart>
                                            </ResponsiveContainer>
                                            <div className="flex flex-wrap gap-2 mt-2 justify-center">
                                                {modelDistribution.map((item, idx) => (
                                                    <span key={`dist-${idx}`} className="flex items-center gap-1 text-xs">
                                                        <span className="w-2 h-2 rounded-full" style={{ background: item.color }} />
                                                        {item.name}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Bar Chart - Daily Breakdown */}
                                        <div className="p-4 rounded-xl" style={{ background: "var(--background)" }}>
                                            <h3 className="text-sm font-medium mb-4">Günlük Üretim Detayı</h3>
                                            <ResponsiveContainer width="100%" height={200}>
                                                <BarChart data={chartData}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                                                    <XAxis dataKey="day" stroke="rgba(255,255,255,0.5)" fontSize={12} />
                                                    <YAxis stroke="rgba(255,255,255,0.5)" fontSize={12} />
                                                    <Tooltip
                                                        contentStyle={{
                                                            background: "var(--card)",
                                                            border: "1px solid var(--border)",
                                                            borderRadius: "8px"
                                                        }}
                                                    />
                                                    <Bar dataKey="images" fill="#D4B85C" name="Görsel" radius={[4, 4, 0, 0]} />
                                                    <Bar dataKey="videos" fill="#3b82f6" name="Video" radius={[4, 4, 0, 0]} />
                                                </BarChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>

                                    {/* Trend Line */}
                                    <div className="p-4 rounded-xl" style={{ background: "var(--background)" }}>
                                        <h3 className="text-sm font-medium mb-4">Haftalık Trend</h3>
                                        <ResponsiveContainer width="100%" height={150}>
                                            <LineChart data={chartData}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                                                <XAxis dataKey="day" stroke="rgba(255,255,255,0.5)" fontSize={12} />
                                                <YAxis stroke="rgba(255,255,255,0.5)" fontSize={12} />
                                                <Tooltip
                                                    contentStyle={{
                                                        background: "var(--card)",
                                                        border: "1px solid var(--border)",
                                                        borderRadius: "8px"
                                                    }}
                                                />
                                                <Legend />
                                                <Line type="monotone" dataKey="images" stroke="#D4B85C" strokeWidth={2} name="Görsel" />
                                                <Line type="monotone" dataKey="videos" stroke="#3b82f6" strokeWidth={2} name="Video" />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>


            </div>
        </div>
    );
}
