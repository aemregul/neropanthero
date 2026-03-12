// API Client for Pepper Root AI Agency Backend

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

// Types
export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    image_url?: string;
}

export interface Session {
    id: string;
    title: string;
    description?: string;
    category?: string;
    cover_image_url?: string;
    created_at: string;
    updated_at: string;
}

export interface Entity {
    id: string;
    session_id: string;
    entity_type: 'character' | 'location' | 'wardrobe' | 'brand';
    name: string;
    tag: string;
    description?: string;
    attributes?: Record<string, string>;
    reference_image_url?: string;
    created_at: string;
    // Alias for backwards compatibility
    type?: 'character' | 'location' | 'wardrobe';
}

export interface ChatRequest {
    message: string;
    session_id?: string;
    reference_video_url?: string;
}

export interface MessageResponse {
    id: string;
    session_id: string;
    role: string;
    content: string;
    metadata_?: Record<string, unknown>;
    created_at: string;
}

export interface AssetResponse {
    id?: string;
    asset_type: string;
    url: string;
    prompt?: string;
    thumbnail_url?: string;
}

export interface TrashOriginalData extends Record<string, unknown> {
    url?: string;
    type?: string;
    prompt?: string;
}

export interface ChatResponse {
    session_id: string;
    message: MessageResponse;
    response: MessageResponse;
    assets: AssetResponse[];
    entities_created: unknown[];
}

export interface ToolCall {
    name: string;
    args: Record<string, unknown>;
    result?: unknown;
}

export interface GeneratedAsset {
    id: string;
    asset_type: 'image' | 'video';
    url: string;
    prompt?: string;
    thumbnail_url?: string;
}

// API Functions

// Helper to get auth headers
function getAuthHeaders(): HeadersInit {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const headers: HeadersInit = {
        'Content-Type': 'application/json',
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

export async function createSession(title?: string, description?: string, category?: string): Promise<Session> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/sessions/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
            title: title || 'Yeni Proje',
            description: description || null,
            category: category || null
        }),
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Failed to create session: ${error}`);
    }

    return response.json();
}

export async function getSessions(): Promise<Session[]> {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    const headers: HeadersInit = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/sessions/`, {
        headers,
    });

    if (!response.ok) {
        throw new Error('Failed to fetch sessions');
    }

    return response.json();
}

// Tek Asistan: kullanıcının ana chat session'ını al (yoksa otomatik oluşturulur)
export async function getMainChatSession(): Promise<{ session_id: string; title: string }> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/chat/main-session`, {
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        throw new Error('Failed to get main chat session');
    }

    return response.json();
}

export async function sendMessage(
    sessionId: string,
    message: string,
    referenceFiles?: File[],
    activeProjectId?: string
): Promise<ChatResponse> {
    // Eğer dosyalar varsa FormData ile /with-files endpoint kullan
    if (referenceFiles && referenceFiles.length > 0) {
        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('message', message);
        for (const file of referenceFiles) {
            formData.append('reference_files', file);
        }
        if (activeProjectId) {
            formData.append('active_project_id', activeProjectId);
        }

        // Auth header ekle (Content-Type FormData için otomatik set edilir)
        const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
        const headers: HeadersInit = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${API_BASE_URL}${API_PREFIX}/chat/with-files`, {
            method: 'POST',
            headers,
            body: formData,
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Failed to send message: ${error}`);
        }

        return response.json();
    }

    // Dosya yoksa normal JSON gönder
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/chat/`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
            session_id: sessionId,
            message: message,
            active_project_id: activeProjectId || null,
        }),
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Failed to send message: ${error}`);
    }

    return response.json();
}

// SSE Streaming version — ChatGPT-style token-by-token
export async function sendMessageStream(
    sessionId: string,
    message: string,
    activeProjectId?: string,
    callbacks?: {
        onToken?: (token: string) => void;
        onAssets?: (assets: Array<{ url: string; prompt?: string }>) => void;
        onVideos?: (videos: Array<{ url: string; prompt?: string; thumbnail_url?: string }>) => void;
        onEntities?: (entities: unknown[]) => void;
        onStatus?: (status: string) => void;
        onGenerationStart?: (generations: Array<{ type: string; prompt?: string; duration?: string | number }>) => void;
        onGenerationComplete?: (data: { type: string }) => void;
        onDone?: () => void;
        onError?: (error: string) => void;
    },
    signal?: AbortSignal,
    referenceMedia?: {
        referenceVideoUrl?: string;
    }
): Promise<void> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/chat/stream`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
            session_id: sessionId,
            message: message,
            active_project_id: activeProjectId || null,
            reference_video_url: referenceMedia?.referenceVideoUrl || null,
        }),
        signal,
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Stream failed: ${error}`);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('No readable stream');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by double newlines
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const event of events) {
            if (!event.trim()) continue;

            const lines = event.split('\n');
            let eventType = '';
            let data = '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    data = line.slice(6);
                }
            }

            switch (eventType) {
                case 'token':
                    try { callbacks?.onToken?.(JSON.parse(data)); } catch { /* ignore */ }
                    break;
                case 'assets':
                    try { callbacks?.onAssets?.(JSON.parse(data)); } catch { /* ignore */ }
                    break;
                case 'videos':
                    try { callbacks?.onVideos?.(JSON.parse(data)); } catch { /* ignore */ }
                    break;
                case 'entities':
                    try { callbacks?.onEntities?.(JSON.parse(data)); } catch { /* ignore */ }
                    break;
                case 'status':
                    callbacks?.onStatus?.(data);
                    break;
                case 'done':
                    callbacks?.onDone?.();
                    break;
                case 'generation_start':
                    try { callbacks?.onGenerationStart?.(JSON.parse(data)); } catch { /* ignore */ }
                    break;
                case 'generation_complete':
                    try { callbacks?.onGenerationComplete?.(JSON.parse(data)); } catch { /* ignore */ }
                    break;
                case 'error':
                    try { callbacks?.onError?.(JSON.parse(data)); } catch { callbacks?.onError?.(data); }
                    break;
            }
        }
    }
}

export async function getSessionHistory(sessionId: string): Promise<MessageResponse[]> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/sessions/${sessionId}/messages`, {
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        throw new Error('Failed to fetch session history');
    }

    return response.json();
}

// Entity (Character, Location, Wardrobe) APIs
// Uses user-based endpoint - entities are GLOBAL across all projects for a user
export async function getEntities(sessionId: string): Promise<Entity[]> {
    // Use /entities/ endpoint which returns ALL user entities (not session-specific)
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/entities/?session_id=${sessionId}`, {
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        throw new Error('Failed to fetch entities');
    }

    const data = await response.json();

    // Backend returns paginated response: {items: [], total: number, ...}
    // Extract items array for backwards compatibility
    if (data && Array.isArray(data.items)) {
        return data.items;
    }

    // Fallback: if already an array (old format), return as-is
    if (Array.isArray(data)) {
        return data;
    }

    // If neither, return empty array
    console.warn('Unexpected entities response format:', data);
    return [];
}

export async function createEntity(
    sessionId: string,
    entity: Omit<Entity, 'id'>
): Promise<Entity> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/sessions/${sessionId}/entities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entity),
    });

    if (!response.ok) {
        throw new Error('Failed to create entity');
    }

    return response.json();
}

// Asset APIs
export async function getAssets(sessionId: string): Promise<GeneratedAsset[]> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/sessions/${sessionId}/assets`, {
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        throw new Error('Failed to fetch assets');
    }

    return response.json();
}

// Health check
export async function checkHealth(): Promise<boolean> {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        return response.ok;
    } catch {
        return false;
    }
}

// Delete Entity
export async function deleteEntity(entityId: string): Promise<boolean> {
    try {
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}/entities/${entityId}`, {
            method: 'DELETE',
            headers: getAuthHeaders(),
        });
        return response.ok;
    } catch {
        return false;
    }
}

// Update Entity Name
export async function updateEntityName(entityId: string, name: string): Promise<Entity | null> {
    try {
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}/entities/${entityId}?name=${encodeURIComponent(name)}`, {
            method: 'PUT',
            headers: getAuthHeaders(),
        });
        if (!response.ok) return null;
        return await response.json();
    } catch {
        return null;
    }
}

// Delete Asset
export async function deleteAsset(assetId: string): Promise<boolean> {
    try {
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}/sessions/assets/${assetId}`, {
            method: 'DELETE',
            headers: getAuthHeaders(),
        });
        return response.ok;
    } catch {
        return false;
    }
}

// Rename Asset
export async function renameAsset(assetId: string, newName: string): Promise<boolean> {
    try {
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}/sessions/assets/${assetId}/rename`, {
            method: 'PATCH',
            headers: getAuthHeaders(),
            body: JSON.stringify({ prompt: newName }),
        });
        return response.ok;
    } catch {
        return false;
    }
}

// Save Asset to Wardrobe (creates a wardrobe entity from asset)
export async function saveAssetToWardrobe(
    sessionId: string,
    assetUrl: string,
    assetName?: string
): Promise<Entity> {
    const entityData = {
        entity_type: 'wardrobe' as const,
        name: assetName || `Wardrobe_${Date.now()}`,
        description: 'Asset panelinden kaydedildi',
        reference_image_url: assetUrl,
    };

    // Use /entities/ endpoint with session_id as query param
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/entities/?session_id=${sessionId}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(entityData),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to save to wardrobe');
    }

    return response.json();
}

// ============== ADMIN APIs ==============

// AI Models
export interface AIModel {
    id: string;
    name: string;
    display_name: string;
    model_type: string;
    provider: string;
    description?: string;
    icon: string;
    is_enabled: boolean;
}

export async function getAIModels(): Promise<AIModel[]> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/models`);
    if (!response.ok) throw new Error('Failed to fetch AI models');
    return response.json();
}

export async function toggleAIModel(modelId: string, isEnabled: boolean): Promise<AIModel> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/models/${modelId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_enabled: isEnabled }),
    });
    if (!response.ok) throw new Error('Failed to toggle AI model');
    return response.json();
}

// Installed Plugins
export interface InstalledPlugin {
    id: string;
    plugin_id: string;
    name: string;
    description?: string;
    icon: string;
    category: string;
    is_enabled: boolean;
}

export async function getInstalledPlugins(): Promise<InstalledPlugin[]> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/plugins/installed`);
    if (!response.ok) throw new Error('Failed to fetch installed plugins');
    return response.json();
}

export async function installPlugin(plugin: {
    plugin_id: string;
    name: string;
    description?: string;
    icon: string;
    category: string;
    api_key?: string;
}): Promise<InstalledPlugin> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/plugins/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(plugin),
    });
    if (!response.ok) throw new Error('Failed to install plugin');
    return response.json();
}

export async function uninstallPlugin(pluginId: string): Promise<boolean> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/plugins/${pluginId}`, {
        method: 'DELETE',
    });
    return response.ok;
}

// Marketplace
export interface MarketplacePlugin {
    id: string;
    name: string;
    description: string;
    author: string;
    icon: string;
    color: string;
    style: string;
    rating: number;
    downloads: number;
    created_at: string;
    source: 'official' | 'community';
    config: Record<string, unknown>;
    is_installed: boolean;
}

export async function getMarketplacePlugins(
    sort: 'downloads' | 'rating' | 'recent' = 'downloads',
    category: 'all' | 'community' | 'official' = 'all',
    search: string = ''
): Promise<MarketplacePlugin[]> {
    const params = new URLSearchParams({ sort, category });
    if (search) params.set('search', search);
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/marketplace/plugins?${params}`);
    if (!response.ok) throw new Error('Failed to fetch marketplace plugins');
    return response.json();
}

export async function publishPlugin(pluginId: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/presets/${pluginId}/publish`, {
        method: 'PATCH',
    });
    if (!response.ok) throw new Error('Failed to publish plugin');
    return response.json();
}

export async function installMarketplacePlugin(pluginId: string, sessionId: string): Promise<{ success: boolean; error?: string; message?: string; plugin_id?: string; installed_name?: string }> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/marketplace/plugins/${pluginId}/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
    });
    if (!response.ok) throw new Error('Failed to install plugin');
    return response.json();
}

// User Settings
export interface UserSettings {
    id: string;
    theme: string;
    language: string;
    notifications_enabled: boolean;
    auto_save: boolean;
    default_model: string;
}

export async function getUserSettings(): Promise<UserSettings> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/settings`);
    if (!response.ok) throw new Error('Failed to fetch user settings');
    return response.json();
}

export async function updateUserSettings(settings: Partial<UserSettings>): Promise<UserSettings> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
    });
    if (!response.ok) throw new Error('Failed to update user settings');
    return response.json();
}

// Usage Stats
export interface UsageStats {
    date: string;
    api_calls: number;
    images_generated: number;
    videos_generated: number;
}

export async function getUsageStats(days: number = 7): Promise<UsageStats[]> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/stats/usage?days=${days}`);
    if (!response.ok) throw new Error('Failed to fetch usage stats');
    return response.json();
}

export interface OverviewStats {
    total_sessions: number;
    total_assets: number;
    total_messages: number;
    active_models: number;
    total_images: number;
    total_videos: number;
}

export async function getOverviewStats(): Promise<OverviewStats> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/stats/overview`);
    if (!response.ok) throw new Error('Failed to fetch overview stats');
    return response.json();
}

// Model Distribution
export interface ModelDistributionItem {
    name: string;
    value: number;
    color: string;
}

export async function getModelDistribution(): Promise<ModelDistributionItem[]> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/stats/model-distribution`);
    if (!response.ok) throw new Error('Failed to fetch model distribution');
    return response.json();
}

// Creative Plugins
export interface PresetData {
    id: string;
    name: string;
    description?: string;
    icon: string;
    color: string;
    style?: string;
    system_prompt?: string;
    is_public: boolean;
    usage_count: number;
    created_at: string;
    downloads?: number;
    author?: string;
}

export async function getPresets(sessionId?: string): Promise<PresetData[]> {
    const url = sessionId
        ? `${API_BASE_URL}${API_PREFIX}/admin/presets?session_id=${sessionId}`
        : `${API_BASE_URL}${API_PREFIX}/admin/presets`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch creative plugins');
    return response.json();
}

export async function createPreset(plugin: {
    name: string;
    description?: string;
    icon?: string;
    color?: string;
    system_prompt?: string;
    is_public?: boolean;
}, sessionId?: string): Promise<PresetData> {
    const url = sessionId
        ? `${API_BASE_URL}${API_PREFIX}/admin/presets?session_id=${sessionId}`
        : `${API_BASE_URL}${API_PREFIX}/admin/presets`;
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(plugin),
    });
    if (!response.ok) throw new Error('Failed to create creative plugin');
    return response.json();
}

export async function deletePreset(pluginId: string): Promise<boolean> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/presets/${pluginId}`, {
        method: 'DELETE',
    });
    return response.ok;
}

// Trash
export interface TrashItemData {
    id: string;
    item_type: string;
    item_id: string;
    item_name: string;
    original_data?: TrashOriginalData;
    deleted_at: string;
    expires_at: string;
}

export async function getTrashItems(): Promise<TrashItemData[]> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/trash`, {
        headers: getAuthHeaders(),
    });
    if (!response.ok) throw new Error('Failed to fetch trash items');
    return response.json();
}

export async function restoreTrashItem(itemId: string): Promise<{
    success: boolean;
    message: string;
    restored?: {
        type: string;
        id: string;
        title?: string;
        name?: string;
        tag?: string;
        url?: string;
    }
}> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/trash/${itemId}/restore`, {
        method: 'POST',
        headers: getAuthHeaders(),
    });
    if (!response.ok) throw new Error('Failed to restore item');
    return response.json();
}

export async function permanentDeleteTrashItem(itemId: string): Promise<boolean> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/admin/trash/${itemId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    return response.ok;
}

// Delete Session (Project)
export async function deleteSession(sessionId: string): Promise<boolean> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    return response.ok;
}

// Update Session (Rename Project)
export async function updateSession(sessionId: string, title: string): Promise<Session> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
    });
    if (!response.ok) throw new Error('Failed to update session');
    return response.json();
}

// Grid Generator
export interface GridGenerateRequest {
    image: string;  // Base64 encoded
    aspect: string;  // 16:9, 9:16, 1:1
    mode: string;  // angles, storyboard
    prompt?: string;
}

export interface GridGenerateResponse {
    success: boolean;
    gridImage?: string;
    error?: string;
}

export async function generateGrid(request: GridGenerateRequest): Promise<GridGenerateResponse> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/grid/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Grid generation failed');
    }
    return response.json();
}

// ============== GERİ BİLDİRİM ==============

export async function sendFeedback(messageId: string, score: number, reason?: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/chat/feedback`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ message_id: messageId, score, reason }),
    });
    if (!response.ok) throw new Error('Failed to send feedback');
    return response.json();
}

// ============== PROMPT TEMPLATE ==============

export interface PromptTemplate {
    id: string;
    name: string;
    icon: string;
    category: string;
    template: string;
    variables: string[];
    example: string;
}

export async function getPromptTemplates(category?: string): Promise<{ templates: PromptTemplate[]; categories: string[]; total: number }> {
    const params = category ? `?category=${category}` : '';
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/chat/templates${params}`, {
        headers: getAuthHeaders(),
    });
    if (!response.ok) throw new Error('Failed to fetch prompt templates');
    return response.json();
}
