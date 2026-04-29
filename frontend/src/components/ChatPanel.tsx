"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import ReactMarkdown from "react-markdown";

import { Send, Paperclip, Loader2, MoreHorizontal, ChevronDown, AlertCircle, Sparkles, X, ZoomIn, Download, ThumbsUp, ThumbsDown } from "lucide-react";
import { useToast } from "./ToastProvider";
import { sendMessage, sendMessageStream, checkHealth, getSessionHistory, sendFeedback, type MessageResponse as ApiMessageResponse } from "@/lib/api";
import { GenerationProgressCard } from "./GenerationProgressCard";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
    image_url?: string;
    image_urls?: string[];
    video_url?: string;
    audio_url?: string;
    audio_label?: string;
}

interface ChatPanelProps {
    sessionId?: string;  // Proje session ID — hem chat hem asset
    onNewAsset?: (asset: { url: string; type: string }) => void;
    onEntityChange?: () => void;
    pendingPrompt?: string | null;
    onPromptConsumed?: () => void;
    pendingInputText?: string | null;
    onInputTextConsumed?: () => void;
    installedPlugins?: Array<{ id: string; name: string; promptText: string; emoji?: string }>;
    pendingAssetUrl?: { url: string; type: "image" | "video" | "audio" | "uploaded" } | null;
    onAssetUrlConsumed?: () => void;
}

function mapApiMessageToChatMessage(msg: ApiMessageResponse): Message {
    const metadata = (msg.metadata_ || {}) as {
        images?: { url: string }[];
        videos?: { url: string }[];
        has_reference_image?: boolean;
        reference_url?: string;
        reference_urls?: string[];
        reference_video_url?: string;
        reference_audio_url?: string;
    };

    let imageUrl = metadata.images?.[0]?.url;
    let imageUrls: string[] | undefined;

    if (!imageUrl && msg.content) {
        const match = msg.content.match(/\[(?:ÜRETİLEN GÖRSELLER|Bu mesajda üretilen görseller):\s*([^\]]+)\]/i);
        if (match) {
            imageUrl = match[1].split(',')[0].trim();
        }
    }

    if (msg.role === 'user' && metadata.reference_urls) {
        imageUrls = metadata.reference_urls;
        if (!imageUrl) imageUrl = imageUrls[0];
    } else if (!imageUrl && msg.role === 'user' && metadata.reference_url) {
        imageUrl = metadata.reference_url;
        imageUrls = [imageUrl];
    }

    const videoUrl = (() => {
        if (msg.role === 'user' && metadata.reference_video_url) {
            return metadata.reference_video_url;
        }
        if (msg.role !== 'assistant') return undefined;
        return metadata.videos?.[0]?.url;
    })();

    return {
        id: msg.id,
        role: msg.role as 'user' | 'assistant',
        content: (msg.content?.replace(/\n\n\[(?:ÜRETİLEN (?:GÖRSELLER|VİDEOLAR)|Bu mesajda üretilen (?:görseller|videolar)):\s*[^\]]+\]/gi, '') || msg.content) ?? '',
        timestamp: new Date(msg.created_at),
        image_url: imageUrl,
        image_urls: imageUrls,
        video_url: videoUrl,
    };
}



// Markdown renderer for assistant messages — renders bold, italic, headings, lists, code, etc.
function MarkdownContent({ content, onImageClick }: { content: string; onImageClick?: (url: string) => void }) {
    // Memoize components to avoid re-renders
    const components = useMemo(() => ({
        // Headings
        h1: ({ children, ...props }: React.ComponentPropsWithRef<'h1'>) => (
            <h3 className="text-base font-bold mt-3 mb-1.5" {...props}>{children}</h3>
        ),
        h2: ({ children, ...props }: React.ComponentPropsWithRef<'h2'>) => (
            <h4 className="text-[15px] font-bold mt-2.5 mb-1" {...props}>{children}</h4>
        ),
        h3: ({ children, ...props }: React.ComponentPropsWithRef<'h3'>) => (
            <h5 className="text-sm font-bold mt-2 mb-1" {...props}>{children}</h5>
        ),
        // Paragraphs
        p: ({ children, ...props }: React.ComponentPropsWithRef<'p'>) => (
            <p className="mb-1.5 last:mb-0 leading-relaxed" {...props}>{children}</p>
        ),
        // Bold
        strong: ({ children, ...props }: React.ComponentPropsWithRef<'strong'>) => (
            <strong className="font-semibold" {...props}>{children}</strong>
        ),
        // Lists
        ul: ({ children, ...props }: React.ComponentPropsWithRef<'ul'>) => (
            <ul className="list-disc list-outside ml-4 mb-1.5 space-y-0.5" {...props}>{children}</ul>
        ),
        ol: ({ children, ...props }: React.ComponentPropsWithRef<'ol'>) => (
            <ol className="list-decimal list-outside ml-4 mb-1.5 space-y-0.5" {...props}>{children}</ol>
        ),
        li: ({ children, ...props }: React.ComponentPropsWithRef<'li'>) => (
            <li className="leading-relaxed" {...props}>{children}</li>
        ),
        // Code
        code: ({ children, className, ...props }: React.ComponentPropsWithRef<'code'> & { className?: string }) => {
            const isInline = !className;
            return isInline ? (
                <code className="bg-white/10 px-1.5 py-0.5 rounded text-[13px] font-mono" {...props}>{children}</code>
            ) : (
                <code className={`block bg-white/5 rounded-lg p-3 text-[13px] font-mono overflow-x-auto my-1.5 ${className || ''}`} {...props}>{children}</code>
            );
        },
        pre: ({ children, ...props }: React.ComponentPropsWithRef<'pre'>) => (
            <pre className="bg-white/5 rounded-lg p-3 overflow-x-auto my-1.5" {...props}>{children}</pre>
        ),
        // Links
        a: ({ href, children, ...props }: React.ComponentPropsWithRef<'a'>) => {
            if (!href) return <span {...props}>{children}</span>;
            // @mention link (from pre-processing)
            if (href === '#mention') {
                return <span className="mention">{children}</span>;
            }
            // Video link
            if (href.match(/\.(mp4|mov|webm)(\?.*)?$/i)) {
                return (
                    <div className="mt-2 mb-2">
                        <video src={`${href}#t=0.1`} controls playsInline muted preload="metadata"
                            className="rounded-lg max-w-full max-h-80 border border-[var(--border)] bg-black/10" />
                    </div>
                );
            }
            // Audio link
            if (href.match(/\.(wav|mp3|ogg|aac|flac)(\?.*)?$/i)) {
                return (
                    <div className="mt-2 mb-2 rounded-2xl overflow-hidden" style={{ maxWidth: '360px' }}>
                        <div className="bg-gradient-to-br from-amber-900/60 via-[#1A1815] to-stone-900/50 p-4">
                            <div className="flex items-center gap-3 mb-3">
                                <span className="text-xl">🎵</span>
                                <span className="text-sm font-medium text-white">{children || 'Müzik'}</span>
                            </div>
                            <audio src={href} controls preload="none" className="w-full rounded-lg" style={{ height: '36px' }} />
                        </div>
                    </div>
                );
            }
            // Image link
            if (href.match(/\.(png|jpg|jpeg|webp|gif|bmp|svg)(\?.*)?$/i)) {
                return (
                    <img src={href} alt={String(children) || 'Görsel'}
                        className="mt-2 mb-2 rounded-xl max-w-[280px] max-h-[280px] object-cover cursor-pointer hover:opacity-90 transition-all border border-white/10"
                        onClick={() => onImageClick ? onImageClick(href) : window.open(href, '_blank')}
                        loading="lazy" />
                );
            }
            // Normal link
            return (
                <a href={href} target="_blank" rel="noopener noreferrer"
                    className="text-[var(--accent)] underline hover:opacity-80" {...props}>{children}</a>
            );
        },
        // Images
        img: ({ src, alt, ...props }: React.ComponentPropsWithRef<'img'>) => (
            <img src={src as string} alt={alt || 'Görsel'}
                className="mt-2 mb-2 rounded-xl max-w-[280px] max-h-[280px] object-cover cursor-pointer hover:opacity-90 transition-all border border-white/10"
                onClick={() => src && (onImageClick ? onImageClick(src as string) : window.open(src as string, '_blank'))}
                loading="lazy" {...props} />
        ),
        // Blockquote
        blockquote: ({ children, ...props }: React.ComponentPropsWithRef<'blockquote'>) => (
            <blockquote className="border-l-2 border-[var(--accent)] pl-3 my-1.5 opacity-80" {...props}>{children}</blockquote>
        ),
        // Horizontal rule
        hr: (props: React.ComponentPropsWithRef<'hr'>) => (
            <hr className="border-white/10 my-2" {...props} />
        ),
    }), [onImageClick]);

    // Pre-process content: convert @mentions to markdown links for green mention styling
    const processedContent = useMemo(() => {
        if (!content) return '';
        // Convert @tag_name to [@tag_name](#mention) — the 'a' component renders #mention links with .mention class
        return content.replace(/@([\w_]+)/g, '[@$1](#mention)');
    }, [content]);

    return (
        <div className="markdown-content">
            <ReactMarkdown components={components}>{processedContent}</ReactMarkdown>
        </div>
    );
}

// Helper to render @mentions, markdown images, links, and VIDEOS
function renderContent(content: string | undefined | null, onImageClick?: (url: string) => void) {
    if (!content || typeof content !== 'string') {
        return content ?? '';
    }

    const elements: React.ReactNode[] = [];
    let lastIndex = 0;

    // Combined regex for all patterns
    // 1. Markdown images: ![alt](url)
    // 2. Markdown links: [text](url)
    // 3. @mentions: @word
    // 4. Video URLs (simple detection for standalone URLs ending with video extensions)
    //    Note: This is a basic regex, might need refinement for complex URLs
    const combinedRegex = /!\[([^\]]*)\]\(([^)]+)\)|\[([^\]]+)\]\(([^)]+)\)|@[\w_]+|(https?:\/\/[^\s]+\.(?:mp4|mov|webm)(?:\?[^\s]*)?)/g;

    let match;
    let key = 0;

    while ((match = combinedRegex.exec(content)) !== null) {
        // Add text before the match
        if (match.index > lastIndex) {
            elements.push(content.slice(lastIndex, match.index));
        }

        if (match[0].startsWith('![')) {
            // Markdown image: ![alt](url)
            const alt = match[1] || 'Görsel';
            const url = match[2];
            elements.push(
                <img
                    key={key++}
                    src={url}
                    alt={alt}
                    className="mt-2 mb-2 rounded-xl max-w-[280px] max-h-[280px] object-cover cursor-pointer hover:opacity-90 hover:shadow-xl transition-all border border-white/10"
                    onClick={() => onImageClick ? onImageClick(url) : window.open(url, '_blank')}
                    loading="lazy"
                    decoding="async"
                    onError={(e) => {
                        const target = e.currentTarget;
                        target.style.display = 'none';
                        const fallback = document.createElement('a');
                        fallback.href = url;
                        fallback.target = '_blank';
                        fallback.textContent = `🔗 ${alt}`;
                        fallback.className = 'text-[var(--accent)] underline';
                        target.parentNode?.insertBefore(fallback, target);
                    }}
                />
            );
        } else if (match[0].startsWith('[')) {
            // Markdown link: [text](url)
            const text = match[3];
            const url = match[4];

            // Check if it's a video link inside markdown syntax
            if (url.match(/\.(mp4|mov|webm)(\?.*)?$/i)) {
                elements.push(
                    <div key={key++} className="mt-2 mb-2">
                        <video
                            src={`${url}#t=0.1`}
                            controls
                            playsInline
                            muted
                            preload="metadata"
                            className="rounded-lg max-w-full max-h-80 border border-[var(--border)] bg-black/10"
                            onLoadedData={e => {
                                const v = e.currentTarget;
                                v.currentTime = 0.1;
                            }}
                        />
                        <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-[var(--foreground-muted)]">📹 {text}</span>
                            <a href={url} target="_blank" rel="noopener noreferrer" className="text-xs text-[var(--accent)] hover:underline">
                                (Yeni sekmede aç)
                            </a>
                        </div>
                    </div>
                );
            } else if (url.match(/\.(wav|mp3|ogg|aac|flac)(\?.*)?$/i)) {
                // Audio player — premium card
                elements.push(
                    <div key={key++} className="mt-3 mb-2 rounded-2xl overflow-hidden" style={{ maxWidth: '360px' }}>
                        <div className="bg-gradient-to-br from-amber-900/60 via-[#1A1815] to-stone-900/50 p-4 relative">
                            {/* Download — top right */}
                            <a
                                href={url}
                                download
                                className="absolute top-3 right-3 p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
                                title="İndir"
                            >
                                <Download size={14} className="text-white/70" />
                            </a>
                            <div className="flex items-center gap-3 mb-4 pr-10">
                                <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center shrink-0">
                                    <span className="text-xl">🎵</span>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <span className="text-sm font-medium text-white block truncate">{text || 'Müzik'}</span>
                                    <span className="text-xs text-white/40">AI Generated</span>
                                </div>
                            </div>
                            {/* Audio controls — bottom */}
                            <audio
                                src={url}
                                controls
                                preload="none"
                                className="w-full rounded-lg"
                                style={{ height: '36px' }}
                                onError={(e) => {
                                    const el = e.currentTarget;
                                    el.style.display = 'none';
                                    const msg = document.createElement('div');
                                    msg.style.cssText = 'color:rgba(255,255,255,0.5);font-size:12px;text-align:center;padding:8px 0';
                                    msg.textContent = '⚠️ Bu ses dosyası artık mevcut değil';
                                    el.parentElement?.appendChild(msg);
                                }}
                                onPlay={(e) => {
                                    // Timeout: if still not playing after 8s, show error
                                    const el = e.currentTarget;
                                    const timer = setTimeout(() => {
                                        if (el.readyState < 2) {
                                            el.style.display = 'none';
                                            const msg = document.createElement('div');
                                            msg.style.cssText = 'color:rgba(255,255,255,0.5);font-size:12px;text-align:center;padding:8px 0';
                                            msg.textContent = '⚠️ Ses dosyası yüklenemedi';
                                            el.parentElement?.appendChild(msg);
                                        }
                                    }, 8000);
                                    el.addEventListener('playing', () => clearTimeout(timer), { once: true });
                                }}
                            />
                        </div>
                    </div>
                );
            } else if (url.match(/\.(png|jpg|jpeg|webp|gif|bmp|svg)(\?.*)?$/i)) {
                // Image link rendered as inline image
                elements.push(
                    <img
                        key={key++}
                        src={url}
                        alt={text || 'Görsel'}
                        className="mt-2 mb-2 rounded-xl max-w-[280px] max-h-[280px] object-cover cursor-pointer hover:opacity-90 hover:shadow-xl transition-all border border-white/10"
                        onClick={() => onImageClick ? onImageClick(url) : window.open(url, '_blank')}
                        loading="lazy"
                        decoding="async"
                        onError={(e) => {
                            const target = e.currentTarget;
                            target.style.display = 'none';
                            const fallback = document.createElement('a');
                            fallback.href = url;
                            fallback.target = '_blank';
                            fallback.textContent = `🔗 ${text}`;
                            fallback.className = 'text-[var(--accent)] underline';
                            target.parentNode?.insertBefore(fallback, target);
                        }}
                    />
                );
            } else {
                elements.push(
                    <a
                        key={key++}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[var(--accent)] underline hover:opacity-80"
                    >
                        {text}
                    </a>
                );
            }
        } else if (match[0].startsWith('@')) {
            // @mention
            elements.push(
                <span key={key++} className="mention">
                    {match[0]}
                </span>
            );
        } else if (match[5]) {
            // Standalone Video URL
            const url = match[5];
            elements.push(
                <div key={key++} className="mt-2 mb-2">
                    <video
                        src={`${url}#t=0.1`}
                        controls
                        playsInline
                        muted
                        preload="metadata"
                        className="rounded-lg max-w-full max-h-80 border border-[var(--border)] bg-black/10"
                        onLoadedData={e => {
                            const v = e.currentTarget;
                            v.currentTime = 0.1;
                        }}
                    />
                    <div className="flex items-center gap-2 mt-1">
                        <a href={url} target="_blank" rel="noopener noreferrer" className="text-xs text-[var(--accent)] hover:underline">
                            📹 Videoyu İndir / Aç
                        </a>
                    </div>
                </div>
            );
        }

        lastIndex = match.index + match[0].length;
    }

    // Add remaining text after last match (skip lone punctuation/whitespace)
    if (lastIndex < content.length) {
        const remaining = content.slice(lastIndex);
        if (remaining.trim() && remaining.trim() !== '.' && remaining.trim() !== ',') {
            elements.push(remaining);
        }
    }

    return elements.length > 0 ? elements : content;
}

function escapeRegExp(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function stripInlineMediaContent(
    content: string,
    media: { image_url?: string; video_url?: string; audio_url?: string }
): string {
    let cleaned = content || '';
    const hasAttachedMedia = Boolean(media.image_url || media.video_url || media.audio_url);

    const assetUrls = [media.image_url, media.video_url, media.audio_url].filter(Boolean) as string[];

    cleaned = cleaned.replace(/\n?\n?\[(?:ÜRETİLEN (?:GÖRSELLER|VİDEOLAR)|Bu mesajda üretilen (?:görseller|videolar)):\s*[^\]]+\]/gi, '').trim();
    cleaned = cleaned.replace(/<img[^>]*>/gi, '').trim();
    cleaned = cleaned.replace(/<video[\s\S]*?<\/video>/gi, '').trim();
    cleaned = cleaned.replace(/<audio[\s\S]*?<\/audio>/gi, '').trim();

    for (const url of assetUrls) {
        const escapedUrl = escapeRegExp(url);
        cleaned = cleaned.replace(new RegExp(`!\\[[^\\]]*\\]\\(${escapedUrl}\\)`, 'gi'), '');
        cleaned = cleaned.replace(new RegExp(`\\[[^\\]]*\\]\\(${escapedUrl}\\)`, 'gi'), '');
        cleaned = cleaned.replace(new RegExp(escapedUrl, 'gi'), '');
    }

    if (hasAttachedMedia) {
        cleaned = cleaned.replace(/!\[[^\]]*\]\([^)]+\)/g, '').trim();
        cleaned = cleaned.replace(/\[[^\]]*\]\([^)]*\.(?:png|jpg|jpeg|webp|gif|bmp|svg|mp4|mov|webm|wav|mp3|ogg|aac|flac)(?:\?[^)]*)?\)/gi, '').trim();
        cleaned = cleaned.replace(/https?:\/\/[^\s]+\.(?:png|jpg|jpeg|webp|gif|bmp|svg|mp4|mov|webm|wav|mp3|ogg|aac|flac)(?:\?[^\s]*)?/gi, '').trim();
    }

    if (media.video_url) {
        cleaned = cleaned.replace(/\[[^\]]*\]\([^)]*\.(?:mp4|mov|webm)(?:\?[^)]*)?\)/gi, '').trim();
    }

    if (media.audio_url) {
        cleaned = cleaned.replace(/\[[^\]]*\]\([^)]*\.(?:wav|mp3|ogg|aac|flac)(?:\?[^)]*)?\)/gi, '').trim();
    }

    cleaned = cleaned.replace(/\n{3,}/g, '\n\n').trim();
    return cleaned;
}

export function ChatPanel({ sessionId: initialSessionId, onNewAsset, onEntityChange, pendingPrompt, onPromptConsumed, pendingInputText, onInputTextConsumed, installedPlugins = [], pendingAssetUrl, onAssetUrlConsumed }: ChatPanelProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [activeGenerations, setActiveGenerations] = useState<Array<{ type: string; prompt?: string; duration?: string | number }>>([]);
    const [videoProgress, setVideoProgress] = useState(0);
    const [videoGenStatus, setVideoGenStatus] = useState<"generating" | "complete" | "error">("generating");
    const [productionLogs, setProductionLogs] = useState<Array<{ id: string; message: string; timestamp: Date }>>([]); 
    const [completedScenes, setCompletedScenes] = useState(0);
    const [totalScenes, setTotalScenes] = useState(0);
    const [sessionId, setSessionId] = useState<string | null>(initialSessionId || null);
    const [isConnected, setIsConnected] = useState<boolean | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
    const [filePreviews, setFilePreviews] = useState<string[]>([]);
    const [attachedVideoUrl, setAttachedVideoUrl] = useState<string | null>(null);
    const [attachedAudioUrl, setAttachedAudioUrl] = useState<string | null>(null);
    const [attachedAudioLabel, setAttachedAudioLabel] = useState<string>('');
    const MAX_FILES = 10;
    const [isDragOver, setIsDragOver] = useState(false);
    const [lightboxImage, setLightboxImage] = useState<string | null>(null);
    const [lightboxVideo, setLightboxVideo] = useState<string | null>(null);
    const [loadingStatus, setLoadingStatus] = useState<string>("Düşünüyor...");
    const loadingTimerRef = useRef<NodeJS.Timeout | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);
    const [offlineQueue, setOfflineQueue] = useState<{ message: string, timestamp: number }[]>([]);
    const [isOffline, setIsOffline] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const toast = useToast();
    const [feedbackState, setFeedbackState] = useState<Record<string, 'up' | 'down' | null>>({});

    // === PROJE BAZLI CHAT STATE SAKLA/GERİ YÜKLE ===
    const projectStateRef = useRef<Record<string, {
        input: string;
        videoUrl: string | null;
        audioUrl: string | null;
        audioLabel: string;
    }>>({});
    const prevSessionRef = useRef<string | null>(null);

    useEffect(() => {
        const prevId = prevSessionRef.current;

        // Önceki projenin state'ini kaydet
        if (prevId) {
            projectStateRef.current[prevId] = {
                input,
                videoUrl: attachedVideoUrl,
                audioUrl: attachedAudioUrl,
                audioLabel: attachedAudioLabel,
            };
        }

        // Yeni projeye geç
        setSessionId(initialSessionId || null);
        setMessages([]);
        hasInitialScrolled.current = false;
        setError(null);
        setIsLoading(false);
        setLoadingStatus("Düşünüyor...");
        // File attachments temizle (blob referansları proje arası taşınamaz)
        setAttachedFiles([]);
        filePreviews.forEach(url => URL.revokeObjectURL(url));
        setFilePreviews([]);
        if (fileInputRef.current) fileInputRef.current.value = '';

        // Yeni projenin kaydedilmiş state'ini geri yükle
        const saved = initialSessionId ? projectStateRef.current[initialSessionId] : null;
        if (saved) {
            setInput(saved.input);
            setAttachedVideoUrl(saved.videoUrl);
            setAttachedAudioUrl(saved.audioUrl);
            setAttachedAudioLabel(saved.audioLabel);
        } else {
            setInput("");
            setAttachedVideoUrl(null);
            setAttachedAudioUrl(null);
            setAttachedAudioLabel('');
        }

        prevSessionRef.current = initialSessionId || null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [initialSessionId]);

    // === AUTO-SAVE DRAFT TO LOCALSTORAGE ===
    const DRAFT_KEY = `pepper_draft_${initialSessionId || 'default'}`;

    // Load draft from localStorage on mount
    useEffect(() => {
        if (typeof window === 'undefined') return;
        const savedDraft = localStorage.getItem(DRAFT_KEY);
        if (savedDraft && !input) {
            setInput(savedDraft);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [initialSessionId]);

    // Save draft to localStorage on input change (debounced)
    useEffect(() => {
        if (typeof window === 'undefined') return;
        const timer = setTimeout(() => {
            if (input.trim()) {
                localStorage.setItem(DRAFT_KEY, input);
            } else {
                localStorage.removeItem(DRAFT_KEY);
            }
        }, 500); // 500ms debounce
        return () => clearTimeout(timer);
    }, [input, DRAFT_KEY]);

    // === OFFLINE DETECTION ===
    useEffect(() => {
        if (typeof window === 'undefined') return;

        const handleOnline = () => {
            setIsOffline(false);
            // Retry queued messages when back online
            if (offlineQueue.length > 0) {
                offlineQueue.forEach((item) => {
                    // Re-add to input for user to send
                    setInput(item.message);
                });
                setOfflineQueue([]);
                localStorage.removeItem('pepper_offline_queue');
            }
        };

        const handleOffline = () => {
            setIsOffline(true);
        };

        window.addEventListener('online', handleOnline);
        window.addEventListener('offline', handleOffline);

        // Load any saved offline queue
        const savedQueue = localStorage.getItem('pepper_offline_queue');
        if (savedQueue) {
            try {
                setOfflineQueue(JSON.parse(savedQueue));
            } catch (_e) {
                console.error('Failed to parse offline queue');
            }
        }

        return () => {
            window.removeEventListener('online', handleOnline);
            window.removeEventListener('offline', handleOffline);
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Handle entity and asset drag & drop
    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        if (e.dataTransfer.types.includes('application/x-entity-tag') ||
            e.dataTransfer.types.includes('application/x-asset-url')) {
            setIsDragOver(true);
            e.dataTransfer.dropEffect = 'copy';
        }
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
    };

    const attachImageFromUrl = useCallback(async (assetUrl: string) => {
        if (attachedFiles.length >= MAX_FILES) {
            toast.error(`Maksimum ${MAX_FILES} dosya ekleyebilirsiniz`);
            return false;
        }

        try {
            const response = await fetch(assetUrl);
            if (!response.ok) {
                throw new Error(`Asset fetch failed: ${response.status}`);
            }

            const blob = await response.blob();
            const fileType = blob.type || "image/png";
            const extension = fileType.split("/")[1] || "png";
            const file = new File([blob], `reference_image_${Date.now()}.${extension}`, { type: fileType });

            setAttachedFiles((prev) => [...prev, file]);
            const previewUrl = URL.createObjectURL(file);
            setFilePreviews((prev) => [...prev, previewUrl]);
            inputRef.current?.focus();
            return true;
        } catch (error) {
            console.error("Error loading reference image:", error);
            toast.error("Referans görsel yüklenemedi");
            return false;
        }
    }, [attachedFiles.length, toast]);

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);

        // Entity tag drop (karakterler, mekanlar)
        const entityTag = e.dataTransfer.getData('application/x-entity-tag');
        if (entityTag) {
            setInput((prev) => {
                const newValue = prev.trim() ? `${prev} ${entityTag}` : entityTag;
                return newValue;
            });
            inputRef.current?.focus();
            return;
        }

        // Asset drop (image or video)
        const assetUrl = e.dataTransfer.getData('application/x-asset-url');
        const assetType = e.dataTransfer.getData('application/x-asset-type'); // 'video' | 'image'

        if (assetUrl) {
            // Eğer video ise URL referansı olarak ekle (dosya indirme yapma)
            if (assetType === 'video' || assetUrl.match(/\.(mp4|mov|webm)(\?.*)?$/i)) {
                setAttachedVideoUrl(assetUrl);
                inputRef.current?.focus();
                toast.success("Video eklendi");
                return;
            }

            // Eğer audio ise URL referansı olarak ekle
            if (assetType === 'audio' || assetUrl.match(/\.(wav|mp3|ogg|aac|flac)(\?.*)?$/i)) {
                const assetLabel = e.dataTransfer.getData('application/x-asset-label') || '';
                setAttachedAudioUrl(assetUrl);
                setAttachedAudioLabel(assetLabel);
                inputRef.current?.focus();
                toast.success("Ses dosyası eklendi");
                return;
            }

            // Image ise — dosyayı indirip attach et
            await attachImageFromUrl(assetUrl);
            return;
        }
    };

    // Handle file selection — multiple images
    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files) return;

        const remaining = MAX_FILES - attachedFiles.length;
        if (remaining <= 0) {
            toast.error(`Maksimum ${MAX_FILES} dosya ekleyebilirsiniz`);
            return;
        }

        const newFiles: File[] = [];
        const newPreviews: string[] = [];
        const filesToProcess = Array.from(files).slice(0, remaining);

        for (const file of filesToProcess) {
            if (file.type.startsWith('image/')) {
                newFiles.push(file);
                newPreviews.push(URL.createObjectURL(file));
            } else {
                toast.error(`"${file.name}" desteklenmiyor — sadece görseller`);
            }
        }

        if (newFiles.length > 0) {
            setAttachedFiles(prev => [...prev, ...newFiles]);
            setFilePreviews(prev => [...prev, ...newPreviews]);
        }

        if (files.length > remaining) {
            toast.error(`${files.length - remaining} dosya eklenmedi (limit: ${MAX_FILES})`);
        }

        // Reset input so same file can be re-selected
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    // Remove single file by index
    const removeFileAt = (index: number) => {
        setAttachedFiles(prev => prev.filter((_, i) => i !== index));
        setFilePreviews(prev => {
            // Revoke ObjectURL to prevent memory leak
            URL.revokeObjectURL(prev[index]);
            return prev.filter((_, i) => i !== index);
        });
    };

    const removeAllAttachments = () => {
        filePreviews.forEach(url => URL.revokeObjectURL(url));
        setAttachedFiles([]);
        setFilePreviews([]);
        setAttachedVideoUrl(null);
        setAttachedAudioUrl(null);
        setAttachedAudioLabel('');
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    // Check backend connection
    useEffect(() => {
        const checkConnection = async () => {
            const healthy = await checkHealth();
            setIsConnected(healthy);
            if (!healthy) {
                setError("Backend bağlantısı kurulamadı. Sunucunun çalıştığından emin olun.");
            }
        };
        checkConnection();
    }, []);

    // initialSessionId değiştiğinde veya ilk yüklemede mesaj geçmişini yükle
    useEffect(() => {
        const loadHistory = async () => {
            if (!initialSessionId) return;

            // SessionId'yi güncelle
            setSessionId(initialSessionId);
            setIsLoading(true);

            try {
                // Backend'den mesaj geçmişini yükle
                const history = await getSessionHistory(initialSessionId);
                const formattedMessages: Message[] = history.map(mapApiMessageToChatMessage);
                setMessages(formattedMessages);
            } catch (err) {
                console.error('Mesaj geçmişi yüklenemedi:', err);
                setMessages([]);
            } finally {
                setIsLoading(false);
            }
        };
        loadHistory();
    }, [initialSessionId]);

    // Background processing WebSockets (progress, error, complete)
    useEffect(() => {
        if (!sessionId) return;

        let ws: WebSocket | null = null;
        let pingInterval: NodeJS.Timeout;
        let reconnectTimeout: NodeJS.Timeout;
        let reconnectAttempts = 0;
        let isClosed = false;

        const connect = () => {
            if (isClosed) return;

            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const wsUrl = apiUrl.replace(/^http/, 'ws');

            try {
                ws = new WebSocket(`${wsUrl}/ws/progress/${sessionId}`);
            } catch (e) {
                console.error('[WS] Connection failed:', e);
                scheduleReconnect();
                return;
            }

            ws.onopen = () => {
                console.log('[WS] Connected to progress channel:', sessionId);
                reconnectAttempts = 0;
            };

            ws.onmessage = (event) => {
                if (event.data === 'pong') return;

                try {
                    const data = JSON.parse(event.data);
                    console.log('[WS] Received:', data.type, data);

                    if (data.type === 'progress') {
                        // 🛡️ Stale guard: eski progress event'lerini yoksay (sayfa yenileme sonrası zombie card önleme)
                        if (data.timestamp) {
                            const eventTime = new Date(data.timestamp).getTime();
                            const now = Date.now();
                            const MAX_AGE_MS = 5 * 60 * 1000; // 5 dakika
                            if (now - eventTime > MAX_AGE_MS) {
                                console.warn('[WS] Stale progress event ignored (age:', Math.round((now - eventTime) / 1000), 's)');
                                return;
                            }
                        }
                        
                        setLoadingStatus(data.message);
                        // Real progress from backend (0.0-1.0 → 0-100)
                        if (typeof data.progress === 'number') {
                            setVideoProgress(Math.round(data.progress * 100));
                        }
                        setVideoGenStatus("generating");
                        // Ensure video progress card is visible
                        setActiveGenerations(prev => {
                            if (prev.length === 0) {
                                return [{ type: 'video', duration: data.duration }];
                            }
                            return prev;
                        });
                    } else if (data.type === 'error') {
                        setMessages(prev => [...prev, {
                            id: Date.now().toString(),
                            role: 'assistant',
                            content: data.message || "Video üretimi başarısız oldu.",
                            timestamp: new Date()
                        }]);
                        setLoadingStatus("");
                        setActiveGenerations([]);
                        setVideoProgress(0);
                        setVideoGenStatus("error");
                    } else if (data.type === 'reassurance') {
                        // Production card mini-log'a ekle (chat'e değil)
                        const msgId = data.message_id || Date.now().toString();
                        setProductionLogs(prev => {
                            if (prev.some(l => l.id === msgId)) return prev;
                            return [...prev, { id: msgId, message: data.message, timestamp: new Date() }];
                        });
                        // Scene data güncelle
                        if (typeof data.completed_scenes === 'number') setCompletedScenes(data.completed_scenes);
                        if (typeof data.total_scenes === 'number' && data.total_scenes > 0) setTotalScenes(data.total_scenes);
                    } else if (data.type === 'complete') {
                        if (data.result?.message) {
                            const msgId = data.result.message_id || Date.now().toString();
                            setMessages(prev => {
                                // Aynı message_id varsa güncelle, yoksa ekle (duplicate önleme)
                                const exists = prev.some(m => m.id === msgId);
                                if (exists) {
                                    return prev.map(m => m.id === msgId
                                        ? { ...m, video_url: data.result.video_url || m.video_url }
                                        : m
                                    );
                                }
                                return [...prev, {
                                    id: msgId,
                                    role: 'assistant' as const,
                                    content: data.result.message,
                                    video_url: data.result.video_url,
                                    timestamp: new Date()
                                }];
                            });
                            if (data.result.video_url && onNewAsset) {
                                onNewAsset({ url: data.result.video_url, type: 'video' });
                            }
                        }
                        setLoadingStatus("");
                        setActiveGenerations([]);
                        setVideoProgress(0);
                        setVideoGenStatus("complete");
                        setProductionLogs([]);
                        setCompletedScenes(0);
                        setTotalScenes(0);
                    }
                } catch (err) {
                    console.error("[WS] Parse error", err);
                }
            };

            ws.onclose = (event) => {
                console.log(`[WS] Disconnected (code: ${event.code}). Reconnecting...`);
                scheduleReconnect();
            };

            ws.onerror = () => {
                console.warn('[WS] Connection error — will retry via onclose');
                // onclose will fire after onerror, so reconnect is handled there
            };

            // Ping every 25 seconds to keep alive
            if (pingInterval) clearInterval(pingInterval);
            pingInterval = setInterval(() => {
                if (ws?.readyState === WebSocket.OPEN) {
                    ws.send('ping');
                }
            }, 25000);
        };

        const scheduleReconnect = () => {
            if (isClosed) return;
            // Exponential backoff: 1s, 2s, 4s, 8s, max 10s
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
            reconnectAttempts++;
            console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})...`);
            reconnectTimeout = setTimeout(connect, delay);
        };

        connect();

        return () => {
            isClosed = true;
            if (pingInterval) clearInterval(pingInterval);
            if (reconnectTimeout) clearTimeout(reconnectTimeout);
            if (ws) ws.close();
        };
    }, [sessionId, onNewAsset]);

    // Workflow'dan gelen prompt'u otomatik gönder
    useEffect(() => {
        if (pendingPrompt && sessionId && !isLoading) {
            setInput(pendingPrompt);
            onPromptConsumed?.();
            // Küçük bir gecikmeyle formu submit et
            setTimeout(() => {
                const form = document.querySelector('form');
                if (form) {
                    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                }
            }, 100);
        }
    }, [pendingPrompt, sessionId, isLoading, onPromptConsumed]);

    // Plugin/Stil şablonu → sadece input'a yaz, gönderme
    useEffect(() => {
        if (pendingInputText && sessionId) {
            setInput(pendingInputText);
            onInputTextConsumed?.();
            // Focus ve textarea height ayarla
            setTimeout(() => {
                if (inputRef.current) {
                    inputRef.current.focus();
                    inputRef.current.style.height = 'auto';
                    inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px';
                }
            }, 50);
        }
    }, [pendingInputText, sessionId, onInputTextConsumed]);

    // Auto-resize textarea when input changes (e.g. from QuickAction cards)
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = 'auto';
            inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + 'px';
        }
    }, [input]);

    // Asset URL ekleme (Medya Panelinden gelen)
    useEffect(() => {
        if (!pendingAssetUrl || !sessionId) {
            return;
        }

        const applyPendingAsset = async () => {
            const { url, type } = pendingAssetUrl;
            if (type === "video") {
                setAttachedVideoUrl(url);
            } else if (type === "audio") {
                setAttachedAudioUrl(url);
                setAttachedAudioLabel("Medya Paneli");
            } else {
                const attached = await attachImageFromUrl(url);
                if (!attached) {
                    onAssetUrlConsumed?.();
                    return;
                }
            }
            onAssetUrlConsumed?.();
            // Focus input
            setTimeout(() => inputRef.current?.focus(), 50);
        };

        void applyPendingAsset();
    }, [attachImageFromUrl, pendingAssetUrl, sessionId, onAssetUrlConsumed]);



    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const hasInitialScrolled = useRef(false);

    const scrollToBottom = useCallback((instant?: boolean) => {
        if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTo({
                top: scrollContainerRef.current.scrollHeight,
                behavior: instant ? 'instant' : 'smooth'
            });
        }
    }, []);

    // Scroll on messages change
    useEffect(() => {
        if (messages.length === 0) return;
        if (!hasInitialScrolled.current) {
            // First load — instant scroll + delayed re-scroll for lazy media
            hasInitialScrolled.current = true;
            scrollToBottom(true);
            setTimeout(() => scrollToBottom(true), 300);
            setTimeout(() => scrollToBottom(true), 800);
        } else {
            // New messages — smooth scroll
            scrollToBottom(false);
        }
    }, [messages, scrollToBottom]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const hasContent = input.trim() || attachedFiles.length > 0 || attachedVideoUrl || attachedAudioUrl;
        if (!hasContent || isLoading || !sessionId) return;

        // If offline, queue the message
        if (isOffline || !navigator.onLine) {
            const queueItem = { message: input, timestamp: Date.now() };
            const newQueue = [...offlineQueue, queueItem];
            setOfflineQueue(newQueue);
            localStorage.setItem('pepper_offline_queue', JSON.stringify(newQueue));
            setError("Çevrimdışısınız. Mesaj bağlantı geldiğinde gönderilecek.");
            return;
        }

        const userMessage: Message = {
            id: Date.now().toString(),
            role: "user",
            content: input || (attachedFiles.length > 0 ? `[${attachedFiles.length} Referans Görsel]` : attachedAudioUrl ? '[🎵 Ses Referansı]' : attachedVideoUrl ? '[📹 Video Referansı]' : ""),
            timestamp: new Date(),
            image_url: filePreviews[0] || undefined,
            image_urls: filePreviews.length > 0 ? [...filePreviews] : undefined,
            video_url: attachedVideoUrl || undefined,
            audio_url: attachedAudioUrl || undefined,
            audio_label: attachedAudioLabel || undefined
        };

        setMessages((prev) => [...prev, userMessage]);

        // Audio URL'yi content içine ekle — backend henüz bunu structured alan olarak almıyor
        let contentToSend = input;
        if (attachedAudioUrl) {
            contentToSend += `\n\n[Referans Ses](${attachedAudioUrl})`;
        }

        const currentInput = contentToSend || (attachedFiles.length > 0 ? `[${attachedFiles.length} Referans Görsel]` : attachedVideoUrl ? '[📹 Video Referansı]' : attachedAudioUrl ? '[🎵 Ses Referansı]' : "");
        const currentDraftInput = input;
        const currentFiles = [...attachedFiles];
        const currentFilePreviews = [...filePreviews];
        const currentAttachedVideoUrl = attachedVideoUrl;
        const currentAttachedAudioUrl = attachedAudioUrl;
        const currentAttachedAudioLabel = attachedAudioLabel;

        setInput("");
        // Reset textarea height after clearing
        if (inputRef.current) {
            inputRef.current.style.height = '24px';
        }
        // Clear draft from localStorage after successful send start
        localStorage.removeItem(DRAFT_KEY);
        // Dosyaları temizle — URL'leri revoke etme, mesaj state'inde hâlâ kullanılıyor
        setAttachedFiles([]);
        setFilePreviews([]);
        setAttachedVideoUrl(null);
        setAttachedAudioUrl(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        setIsLoading(true);
        setError(null);

        // Smart loading status — sadece uzun işlemlerde göster (görsel/video/düzenleme)
        const lowerMsg = currentInput.toLowerCase();
        const hasImage = currentFiles.length > 0;
        const isLongOperation = hasImage || lowerMsg.match(
            /görsel|resim|fotoğraf|image|çiz|oluştur.*görsel|generate.*image|illustration|poster|logo|video|animasyon|klip|sinema|cinematic|düzenle|edit|değiştir|kaldır|ekle.*görsel|remove|change|tanı|kaydet|karakter|entity|lokasyon|mekan/
        );

        let statusPhases: { text: string; delay: number }[] = [];

        if (isLongOperation) {
            if (lowerMsg.match(/görsel|resim|fotoğraf|image|çiz|oluştur.*görsel|generate.*image|illustration|poster|logo/)) {
                statusPhases = [
                    { text: "🎨 Prompt analiz ediliyor...", delay: 0 },
                    { text: "🖌️ Görsel oluşturuluyor...", delay: 3000 },
                    { text: "✨ Son rötuşlar yapılıyor...", delay: 12000 },
                ];
                // Card erken açılmaz — backend generation_start event'i ile açılır
            } else if (lowerMsg.match(/video|animasyon|klip|sinema|cinematic/)) {
                statusPhases = [
                    { text: "🎬 Video senaryosu hazırlanıyor...", delay: 0 },
                    { text: "🎥 Video üretiliyor...", delay: 3000 },
                    { text: "🎞️ Video işleniyor...", delay: 15000 },
                ];
                // Card erken açılmaz — backend generation_start/progress event'i ile açılır
            } else if (lowerMsg.match(/düzenle|edit|değiştir|kaldır|ekle.*görsel|remove|change/)) {
                statusPhases = [
                    { text: "🔍 Görsel analiz ediliyor...", delay: 0 },
                    { text: "✏️ Düzenleme yapılıyor...", delay: 3000 },
                    { text: "✨ Sonuç hazırlanıyor...", delay: 10000 },
                ];
                // Card erken açılmaz — backend generation_start event'i ile açılır
            } else if (hasImage) {
                statusPhases = [
                    { text: "📷 Görsel inceleniyor...", delay: 0 },
                    { text: "🧠 Analiz ediliyor...", delay: 2000 },
                    { text: "💬 Yanıt hazırlanıyor...", delay: 5000 },
                ];
            } else {
                statusPhases = [
                    { text: "🧠 Bilgi analiz ediliyor...", delay: 0 },
                    { text: "💾 Kayıt yapılıyor...", delay: 2000 },
                ];
            }
            setLoadingStatus(statusPhases[0].text);
        }

        // Sade metin sohbetlerde metin yerine sadece animasyonlu simge göster
        if (!isLongOperation) {
            setLoadingStatus("");
        }

        // Schedule phase transitions
        const timers: NodeJS.Timeout[] = [];
        statusPhases.slice(1).forEach((phase) => {
            const timer = setTimeout(() => setLoadingStatus(phase.text), phase.delay);
            timers.push(timer);
        });
        loadingTimerRef.current = timers[timers.length - 1] || null;

        // Store timers for cleanup
        const cleanupTimers = () => timers.forEach(t => clearTimeout(t));

        try {
            // Reference images varsa FormData endpoint kullan
            if (currentFiles.length > 0) {
                // 📊 Dosyalı isteklerde progress kartı simülasyonu
                // with-files endpoint SSE kullanmadığı için yapay progress göster
                // Video olmayan isteklerde progress kartı gösterme
                // setActiveGenerations([{ type: 'image', prompt: currentInput.slice(0, 80) }]);

                const response = await sendMessage(sessionId, currentInput, currentFiles, sessionId);

                // Progress kartını kapat
                // setActiveGenerations([]);
                const serverUserMessage = response.message ? mapApiMessageToChatMessage(response.message) : null;
                const assistantMessage = response.response
                    ? mapApiMessageToChatMessage(response.response)
                    : {
                        id: (Date.now() + 1).toString(),
                        role: "assistant" as const,
                        content: "Yanıt alınamadı",
                        timestamp: new Date(),
                    };

                setMessages((prev) => {
                    const reconciled = prev.map((msg) =>
                        msg.id === userMessage.id && serverUserMessage ? serverUserMessage : msg
                    );
                    return [...reconciled, assistantMessage];
                });
                if (response.assets && response.assets.length > 0) {
                    response.assets.forEach((asset: { url: string; asset_type: string }) => {
                        onNewAsset?.({ url: asset.url, type: asset.asset_type });
                    });
                }
                if (response.entities_created && response.entities_created.length > 0) {
                    onEntityChange?.();
                }
            } else {
                // 🔥 SSE Streaming — ChatGPT tarzı token token yanıt
                const messageId = (Date.now() + 1).toString();
                let messageCreated = false;
                const charQueue: string[] = [];
                let isProcessingQueue = false;
                let streamErrorText: string | null = null;

                // Karakter kuyruğunu ChatGPT hızında işle (harf harf)
                const processCharQueue = () => {
                    if (isProcessingQueue) return;
                    isProcessingQueue = true;

                    const flush = () => {
                        if (charQueue.length === 0) {
                            isProcessingQueue = false;
                            return;
                        }
                        // Her seferde 1 karakter al (harf harf yazım)
                        const chars = charQueue.splice(0, 1).join('');
                        setMessages((prev) =>
                            prev.map((msg) =>
                                msg.id === messageId
                                    ? { ...msg, content: msg.content + chars }
                                    : msg
                            )
                        );
                        // ChatGPT benzeri hız: normalde 30-45ms, kuyruk birikmişse hızlan
                        const delay = charQueue.length > 200 ? 8 : charQueue.length > 80 ? 15 : 25 + Math.random() * 5;
                        setTimeout(flush, delay);
                    };
                    flush();
                };

                abortControllerRef.current = new AbortController();
                await sendMessageStream(sessionId, currentInput, sessionId, {
                    onToken: (token: string) => {
                        // İlk token geldiğinde mesaj oluştur ve loading'i kapat
                        if (!messageCreated) {
                            messageCreated = true;
                            setIsLoading(false); // Loading box'ı kapat
                            cleanupTimers();
                            const assistantMessage: Message = {
                                id: messageId,
                                role: "assistant",
                                content: "",
                                timestamp: new Date(),
                            };
                            setMessages((prev) => [...prev, assistantMessage]);
                        }
                        // Tokeni karakterlere böl ve kuyruğa ekle
                        charQueue.push(...token.split(''));
                        processCharQueue();
                    },
                    onAssets: (assets) => {
                        // İlk image'ı mesaja ekle
                        if (!messageCreated) {
                            messageCreated = true;
                            setIsLoading(false);
                            cleanupTimers();
                            const assistantMessage: Message = {
                                id: messageId,
                                role: "assistant",
                                content: "",
                                timestamp: new Date(),
                            };
                            setMessages((prev) => [...prev, assistantMessage]);
                        }
                        const firstImage = assets.find((a) => a.url);
                        if (firstImage) {
                            setMessages((prev) =>
                                prev.map((msg) =>
                                    msg.id === messageId
                                        ? { ...msg, image_url: firstImage.url }
                                        : msg
                                )
                            );
                        }
                        // Asset panel'i refresh et
                        assets.forEach((asset) => {
                            onNewAsset?.({ url: asset.url, type: 'image' });
                        });
                        // Görsel üretim bitti — image card'ını kaldır
                        setActiveGenerations(prev => prev.filter(g => g.type === 'video' || g.type === 'long_video'));
                    },
                    onVideos: (videos) => {
                        videos.forEach((video) => {
                            onNewAsset?.({ url: video.url, type: 'video' });
                        });
                    },
                    onEntities: () => {
                        onEntityChange?.();
                    },
                    onStatus: (status: string) => {
                        setLoadingStatus(status);
                        // Status mesajı üretim başladığını gösteriyorsa, card'ı erken göster
                        const lower = status.toLowerCase();
                        const genPatterns = ['oluşturuluyor', 'üretiliyor', 'generating', 'render'];
                        const isGenStatus = genPatterns.some(p => lower.includes(p));
                        if (isGenStatus) {
                            setActiveGenerations(prev => {
                                if (prev.length > 0) return prev; // Zaten var
                                // Hangi tip olduğunu tahmin et
                                const type = lower.includes('görsel') || lower.includes('image') ? 'image'
                                    : lower.includes('video') ? 'video' : 'image';
                                return [{ type }];
                            });
                            setVideoGenStatus("generating");
                        }
                    },
                    onGenerationStart: (generations) => {
                        if (generations.length > 0) {
                            setVideoProgress(0);
                            setVideoGenStatus("generating");
                            setActiveGenerations(generations);
                        }
                    },
                    onGenerationComplete: () => {
                        // Senkron tool bitti — image/audio card'larını kaldır (video arka planda devam eder)
                        setActiveGenerations((prev) => prev.filter((g) => g.type === "video" || g.type === "long_video"));
                    },
                    onDone: () => {
                        // Stream tamamlandı — tüm loading state temizle + stale card temizle
                        cleanupTimers();
                        setIsLoading(false);
                        setLoadingStatus("");
                        // Senkron üretimler bittiyse card'ları temizle (video hariç — WS ile yönetilir)
                        setActiveGenerations(prev => prev.filter(g => g.type === "video" || g.type === "long_video"));
                    },
                    onError: (error: string) => {
                        console.error('Stream error:', error);
                        streamErrorText = error || "Mesaj işlenirken bir hata oluştu.";
                        cleanupTimers();
                        setIsLoading(false);
                        setLoadingStatus("");
                        setError(streamErrorText);
                        // Hata durumunda progress card'ı temizle
                        setActiveGenerations([]);
                        setVideoProgress(0);
                        setProductionLogs([]);
                        setCompletedScenes(0);
                        setTotalScenes(0);

                        if (!messageCreated) {
                            messageCreated = true;
                            const assistantMessage: Message = {
                                id: messageId,
                                role: "assistant",
                                content: streamErrorText,
                                timestamp: new Date(),
                            };
                            setMessages((prev) => [...prev, assistantMessage]);
                            return;
                        }

                        setMessages((prev) =>
                            prev.map((msg) =>
                                msg.id === messageId && !msg.content.trim()
                                    ? { ...msg, content: streamErrorText ?? '' }
                                    : msg
                            )
                        );
                    },
                }, abortControllerRef.current.signal, {
                    referenceVideoUrl: attachedVideoUrl || undefined,
                });

                // Kuyruktaki kalan tokenları flush et (maks 10 saniye timeout)
                await new Promise<void>((resolve) => {
                    const startTime = Date.now();
                    const checkQueue = () => {
                        if (charQueue.length === 0 && !isProcessingQueue) {
                            resolve();
                        } else if (Date.now() - startTime > 10000) {
                            // 10 saniye timeout — sonsuz beklemeyi engelle
                            console.warn('[Chat] charQueue flush timeout — forcing resolve');
                            resolve();
                        } else {
                            setTimeout(checkQueue, 30);
                        }
                    };
                    checkQueue();
                });

                // Stream bitti — inline asset tag'lerini temizle (thumbnail olarak render edilecek)
                setMessages((prev) =>
                    prev.map((msg) =>
                        msg.id === messageId
                            ? {
                                ...msg,
                                content: msg.content.replace(/\n\n\[(?:ÜRETİLEN (?:GÖRSELLER|VİDEOLAR)|Bu mesajda üretilen (?:görseller|videolar)):\s*[^\]]+\]/gi, '').trim(),
                            }
                            : msg
                    )
                );

                // Assets panelini yenile (audio gibi SSE ile gönderilmeyen asset'ler için)
                onNewAsset?.({ url: '', type: 'refresh' });
            }
        } catch (err) {
            // User-initiated stop — don't show error
            if (err instanceof DOMException && err.name === 'AbortError') {
                console.log('Stream cancelled by user');
                return;
            }
            console.error("Chat error:", err);
            // Save failed message back to draft for retry
            localStorage.setItem(DRAFT_KEY, currentDraftInput);
            setInput(currentDraftInput);
            setAttachedFiles(currentFiles);
            setFilePreviews(currentFilePreviews);
            setAttachedVideoUrl(currentAttachedVideoUrl);
            setAttachedAudioUrl(currentAttachedAudioUrl);
            setAttachedAudioLabel(currentAttachedAudioLabel);
            setError("Mesaj gönderilemedi. Referanslar korundu, tekrar deneyin.");

            // Fallback message
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: "Üzgünüm, bir hata oluştu. Referanslar korundu, lütfen tekrar deneyin.",
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
        } finally {
            abortControllerRef.current = null;
            setIsLoading(false);
            setLoadingStatus("Düşünüyor...");
            cleanupTimers();
            // Safety net: senkron üretim card'larını temizle (video WS ile yönetilir)
            setActiveGenerations(prev => prev.filter(g => g.type === 'video' || g.type === 'long_video'));
        }
    };

    return (
        <div
            className={`flex-1 flex flex-col h-screen ${isDragOver ? 'ring-2 ring-[var(--accent)] ring-inset' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            {/* Header */}
            <header
                className="h-14 px-4 lg:px-6 flex items-center justify-between border-b shrink-0"
                style={{
                    background: "var(--background-secondary)",
                    borderColor: "var(--border)"
                }}
            >
                <div className="flex items-center gap-3 pl-12 lg:pl-0">
                    <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center"
                        style={{ background: 'linear-gradient(135deg, #D4B85C, #8B6D28)' }}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="black"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5m14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>
                    </div>
                    <div className="flex items-center gap-1">
                        <span className="font-medium" style={{ fontFamily: "var(--font-cormorant, 'Cormorant Garamond', serif)" }}>Nero Panthero</span>
                        <span style={{ color: '#C9A84C' }}>AI Studio</span>
                        <ChevronDown size={16} style={{ color: "var(--foreground-muted)" }} />
                    </div>

                    {/* Connection status */}
                    <div className="ml-2">
                        {isConnected === null ? (
                            <Loader2 className="w-4 h-4 animate-spin" style={{ color: "var(--foreground-muted)" }} />
                        ) : isConnected && !isOffline ? (
                            <div className="w-2 h-2 rounded-full bg-green-500" title="Bağlı" />
                        ) : (
                            <div className="w-2 h-2 rounded-full bg-red-500" title="Bağlantı yok" />
                        )}
                    </div>
                </div>

                <button className="p-2 rounded-lg hover:bg-[var(--card)]">
                    <MoreHorizontal size={20} style={{ color: "var(--foreground-muted)" }} />
                </button>
            </header>

            {/* Offline banner */}
            {isOffline && (
                <div
                    className="px-4 py-2 flex items-center gap-2 text-sm"
                    style={{ background: "rgba(234, 179, 8, 0.1)", color: "#eab308" }}
                >
                    <AlertCircle size={16} />
                    Çevrimdışı - İnternet bağlantınız yok. Mesajlar bağlantı geldiğinde gönderilecek.
                </div>
            )}

            {/* Error banner */}
            {error && (
                <div
                    className="px-4 py-2 flex items-center gap-2 text-sm"
                    style={{ background: "rgba(239, 68, 68, 0.1)", color: "#ef4444" }}
                >
                    <AlertCircle size={16} />
                    {error}
                </div>
            )}

            {/* Messages */}
            <div
                ref={scrollContainerRef}
                className="flex-1 overflow-y-auto p-4 lg:p-6"
                style={{ background: "var(--background)" }}
            >
                <div className="max-w-3xl mx-auto space-y-4">
                    {messages.length === 0 && !isLoading && (
                        <div className="flex flex-col items-center justify-center py-16">
                            {/* Logo & Title */}
                            <div style={{ width: 48, height: 48, borderRadius: 12, background: 'linear-gradient(135deg, #D4B85C, #8B6D28)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="black"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5m14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>
                            </div>
                            <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: "var(--font-cormorant, 'Cormorant Garamond', serif)" }}>Nero Panthero AI</h2>
                            <p className="text-sm mb-8" style={{ color: "var(--foreground-muted)" }}>
                                AI destekli iç mekan tasarım asistanınız
                            </p>

                            {/* Quick Actions */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-md">
                                <button
                                    onClick={() => setInput("Modern minimalist tarzda bir oturma odası tasarımı oluştur. Açık tonlarda, geniş pencereli, doğal ışık alan bir mekan olsun.")}
                                    className="p-4 rounded-xl text-left transition-all hover:scale-[1.02]"
                                    style={{ background: "var(--card)", border: "1px solid var(--border)" }}
                                >
                                    <span className="text-lg mb-2 block">🏠</span>
                                    <span className="text-sm font-medium">Oda Tasarımı</span>
                                    <p className="text-xs mt-1" style={{ color: "var(--foreground-muted)" }}>
                                        Fotorealistik iç mekan üret
                                    </p>
                                </button>
                                <button
                                    onClick={() => setInput("Bir salon için mobilya önerileri ver. Modern tarzdaki bir oturma odasına uygun koltuk, sehpa ve TV ünitesi seçenekleri olsun.")}
                                    className="p-4 rounded-xl text-left transition-all hover:scale-[1.02]"
                                    style={{ background: "var(--card)", border: "1px solid var(--border)" }}
                                >
                                    <span className="text-lg mb-2 block">🛋️</span>
                                    <span className="text-sm font-medium">Mobilya Önerisi</span>
                                    <p className="text-xs mt-1" style={{ color: "var(--foreground-muted)" }}>
                                        Tarza uygun mobilya seç
                                    </p>
                                </button>
                                <button
                                    onClick={() => setInput("Lamel panel tasarımı yapmak istiyorum. 15cm genişlik, 2cm aralık, meşe rengi, TV ünitesinin yan duvarına uygun olsun.")}
                                    className="p-4 rounded-xl text-left transition-all hover:scale-[1.02]"
                                    style={{ background: "var(--card)", border: "1px solid var(--border)" }}
                                >
                                    <span className="text-lg mb-2 block">🏛️</span>
                                    <span className="text-sm font-medium">Duvar Paneli</span>
                                    <p className="text-xs mt-1" style={{ color: "var(--foreground-muted)" }}>
                                        Parametrik lamel tasarımı
                                    </p>
                                </button>
                                <button
                                    onClick={() => setInput("Merhaba! Tüm yeteneklerini ve yapabileceklerini detaylı olarak açıkla. Görsel üretimi, karakter yönetimi, video oluşturma ve diğer özelliklerini anlat.")}
                                    className="p-4 rounded-xl text-left transition-all hover:scale-[1.02]"
                                    style={{ background: "var(--card)", border: "1px solid var(--border)" }}
                                >
                                    <span className="text-lg mb-2 block">💡</span>
                                    <span className="text-sm font-medium">Ne Yapabilirim?</span>
                                    <p className="text-xs mt-1" style={{ color: "var(--foreground-muted)" }}>
                                        Tüm özellikleri keşfet
                                    </p>
                                </button>
                                <button
                                    onClick={() => setInput("Bu odanın renk paletini değiştirmek istiyorum. Duvarları su yeşili, zemini açık meşe olsun. Fotorealistik render al.")}
                                    className="p-4 rounded-xl text-left transition-all hover:scale-[1.02]"
                                    style={{ background: "var(--card)", border: "1px solid var(--border)" }}
                                >
                                    <span className="text-lg mb-2 block">🎨</span>
                                    <span className="text-sm font-medium">Renk & Malzeme</span>
                                    <p className="text-xs mt-1" style={{ color: "var(--foreground-muted)" }}>
                                        Fotorealistik render al
                                    </p>
                                </button>
                            </div>
                        </div>
                    )}

                    {messages.map((msg) => (
                        <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            {msg.role === "user" ? (
                                <div className="flex flex-col items-end gap-2 max-w-[75%]">
                                    {/* Media — outside bubble */}
                                    {msg.image_urls && msg.image_urls.length > 1 ? (
                                        <div className="flex flex-wrap gap-1.5 justify-end">
                                            {msg.image_urls.map((url, i) => (
                                                <img
                                                    key={i}
                                                    src={url}
                                                    alt={`Referans görsel ${i + 1}`}
                                                    className="object-cover rounded-xl cursor-pointer hover:opacity-90 hover:shadow-lg transition-all"
                                                    style={{ width: '100px', height: '100px' }}
                                                    onClick={() => setLightboxImage(url)}
                                                    loading="lazy"
                                                    decoding="async"
                                                />
                                            ))}
                                        </div>
                                    ) : msg.image_url && (
                                        <img
                                            src={msg.image_url}
                                            alt="Referans görsel"
                                            className="object-cover rounded-xl cursor-pointer hover:opacity-90 hover:shadow-lg transition-all"
                                            style={{ width: '200px', height: '300px' }}
                                            onLoad={e => {
                                                const img = e.currentTarget;
                                                if (img.naturalWidth > img.naturalHeight) {
                                                    img.style.width = '300px';
                                                    img.style.height = '200px';
                                                }
                                            }}
                                            onClick={() => setLightboxImage(msg.image_url!)}
                                            loading="lazy"
                                            decoding="async"
                                        />
                                    )}
                                    {msg.video_url && (
                                        <div
                                            className="relative group/vid cursor-pointer rounded-xl overflow-hidden"
                                            onClick={() => setLightboxVideo(msg.video_url!)}
                                        >
                                            <video
                                                src={`${msg.video_url}#t=0.1`}
                                                playsInline
                                                muted
                                                loop
                                                preload="metadata"
                                                className="object-cover rounded-xl"
                                                style={{ width: '200px', height: '300px' }}
                                                onLoadedMetadata={e => {
                                                    const v = e.currentTarget;
                                                    if (v.videoWidth > v.videoHeight) {
                                                        v.style.width = '300px';
                                                        v.style.height = '200px';
                                                    }
                                                }}
                                                onMouseOver={e => { e.currentTarget.play().catch(() => { }); }}
                                                onMouseOut={e => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }}
                                            />
                                            <div className="absolute bottom-2 left-2 w-7 h-7 rounded-full bg-black/60 flex items-center justify-center group-hover/vid:bg-white/20 transition-colors">
                                                <svg width="12" height="12" viewBox="0 0 24 24" fill="white"><polygon points="5,3 19,12 5,21" /></svg>
                                            </div>
                                        </div>
                                    )}
                                    {msg.audio_url && (
                                        <div className="w-36 h-24 rounded-xl flex flex-col items-center justify-center bg-gradient-to-br from-amber-900/40 to-stone-900/40 overflow-hidden px-1" style={{ border: '1px solid var(--border)' }}>
                                            <span className="text-lg mb-0.5">🎵</span>
                                            {msg.audio_label && (
                                                <span className="text-[9px] text-white/80 text-center leading-tight line-clamp-2 mb-0.5">{msg.audio_label}</span>
                                            )}
                                            <audio src={msg.audio_url} controls className="w-[120px] h-6" style={{ transform: 'scale(0.85)' }}
                                                onError={(e) => { (e.currentTarget as HTMLAudioElement).style.display = 'none'; }}
                                            />
                                        </div>
                                    )}
                                    {/* Text bubble */}
                                    {msg.content && (
                                        <div className="message-bubble message-user">
                                            <div className="text-sm lg:text-[15px] leading-relaxed">
                                                {renderContent(msg.content, setLightboxImage)}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="flex gap-3 max-w-[85%] group/feedback">
                                    <div style={{ width: 24, height: 24, borderRadius: 6, background: 'linear-gradient(135deg, #D4B85C, #8B6D28)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 4 }}>
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="black"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5m14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>
                                    </div>
                                    <div className="flex-1 flex flex-col gap-2">
                                        {/* Text bubble — strip inline images if image_url exists */}
                                        {(() => {
                                            const displayContent = stripInlineMediaContent(msg.content || '', {
                                                image_url: msg.image_url,
                                                video_url: msg.video_url,
                                                audio_url: msg.audio_url,
                                            });
                                            return displayContent ? (
                                                <div className="message-bubble message-ai">
                                                    <div className="text-sm lg:text-[15px] leading-relaxed">
                                                        <MarkdownContent content={displayContent} onImageClick={setLightboxImage} />
                                                    </div>
                                                </div>
                                            ) : null;
                                        })()}

                                        {/* Media — outside bubble */}
                                        {msg.image_url && (
                                            <img
                                                src={msg.image_url}
                                                alt="Üretilen görsel"
                                                className="rounded-xl object-cover cursor-pointer hover:opacity-90 hover:shadow-xl transition-all"
                                                style={{ width: '280px', height: '420px' }}
                                                onLoad={e => {
                                                    const img = e.currentTarget;
                                                    if (img.naturalWidth > img.naturalHeight) {
                                                        img.style.width = '420px';
                                                        img.style.height = '280px';
                                                    }
                                                }}
                                                onClick={() => setLightboxImage(msg.image_url!)}
                                                loading="lazy"
                                                decoding="async"
                                            />
                                        )}

                                        {msg.video_url && (
                                            <div
                                                className="relative group/vid cursor-pointer rounded-xl overflow-hidden inline-block"
                                                onClick={() => setLightboxVideo(msg.video_url!)}
                                            >
                                                <video
                                                    src={`${msg.video_url}#t=0.1`}
                                                    playsInline
                                                    muted
                                                    loop
                                                    preload="metadata"
                                                    className="object-cover rounded-xl"
                                                    style={{ width: '280px', height: '420px' }}
                                                    onLoadedMetadata={e => {
                                                        const v = e.currentTarget;
                                                        if (v.videoWidth > v.videoHeight) {
                                                            v.style.width = '420px';
                                                            v.style.height = '280px';
                                                        }
                                                    }}
                                                    onMouseOver={e => { e.currentTarget.play().catch(() => { }); }}
                                                    onMouseOut={e => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }}
                                                />
                                                <div className="absolute bottom-2 left-2 w-8 h-8 rounded-full bg-black/60 flex items-center justify-center group-hover/vid:bg-white/20 transition-colors">
                                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="white"><polygon points="5,3 19,12 5,21" /></svg>
                                                </div>
                                            </div>
                                        )}

                                        {/* 👍/👎 Feedback buttons */}
                                        {msg.id && (
                                            <div className="flex items-center gap-1 mt-1 pl-1">
                                                {feedbackState[msg.id] !== 'down' && (
                                                    <button
                                                        onClick={async () => {
                                                            setFeedbackState(prev => ({ ...prev, [msg.id]: 'up' }));
                                                            try { await sendFeedback(msg.id, 1); } catch (e) { console.error(e); }
                                                        }}
                                                        className={`p-1 rounded-md transition-all ${feedbackState[msg.id] === 'up'
                                                            ? 'text-green-500 bg-green-500/10'
                                                            : 'text-white/30 hover:text-green-400 hover:bg-green-500/10 opacity-0 group-hover/feedback:opacity-100'
                                                            }`}
                                                        title="Beğen"
                                                        disabled={feedbackState[msg.id] === 'up'}
                                                    >
                                                        <ThumbsUp className="w-3.5 h-3.5" />
                                                    </button>
                                                )}
                                                {feedbackState[msg.id] !== 'up' && (
                                                    <button
                                                        onClick={async () => {
                                                            setFeedbackState(prev => ({ ...prev, [msg.id]: 'down' }));
                                                            try { await sendFeedback(msg.id, -1, 'other'); } catch (e) { console.error(e); }
                                                        }}
                                                        className={`p-1 rounded-md transition-all ${feedbackState[msg.id] === 'down'
                                                            ? 'text-red-400 bg-red-500/10'
                                                            : 'text-white/30 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover/feedback:opacity-100'
                                                            }`}
                                                        title="Beğenme"
                                                        disabled={feedbackState[msg.id] === 'down'}
                                                    >
                                                        <ThumbsDown className="w-3.5 h-3.5" />
                                                    </button>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}

                    {isLoading && (
                        <div className="flex gap-3">
                            <div style={{ width: 24, height: 24, borderRadius: 6, background: 'linear-gradient(135deg, #D4B85C, #8B6D28)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="black"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5m14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>
                            </div>
                            <div className="message-bubble message-ai">
                                {loadingStatus ? (
                                    <div className="flex items-center gap-2">
                                        <Loader2 className="w-4 h-4 animate-spin" style={{ color: "var(--accent)" }} />
                                        <span
                                            className="text-sm"
                                            style={{ transition: "opacity 0.3s ease" }}
                                            key={loadingStatus}
                                        >
                                            {loadingStatus}
                                        </span>
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-1 py-1 px-1">
                                        {[0, 1, 2].map(i => (
                                            <div
                                                key={i}
                                                className="w-2 h-2 rounded-full"
                                                style={{
                                                    background: "var(--accent)",
                                                    opacity: 0.6,
                                                    animation: `typing-dot 1.4s ease-in-out ${i * 0.2}s infinite`,
                                                }}
                                            />
                                        ))}
                                        <style>{`
                                            @keyframes typing-dot {
                                                0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
                                                30% { transform: translateY(-6px); opacity: 1; }
                                            }
                                        `}</style>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Generation Progress Cards */}
                    {activeGenerations.length > 0 && (
                        <div className="flex gap-3 mb-4">
                            <div className="chat-avatar assistant-avatar shrink-0">
                                <span>🤖</span>
                            </div>
                            <div className="flex flex-col gap-2">
                                {activeGenerations.map((gen, i) => (
                                    <GenerationProgressCard
                                        key={`gen-${i}`}
                                        type={gen.type}
                                        duration={gen.duration}
                                        progress={videoProgress}
                                        status={videoGenStatus}
                                        productionLogs={productionLogs}
                                        completedScenes={completedScenes}
                                        totalScenes={totalScenes}
                                        onCancel={async () => {
                                            // 1. SSE stream kes (senkron üretimler)
                                            abortControllerRef.current?.abort();
                                            abortControllerRef.current = null;

                                            // 2. Backend BG task iptal (arka plan üretimler)
                                            if (sessionId) {
                                                try {
                                                    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
                                                    const formData = new FormData();
                                                    formData.append('session_id', sessionId);
                                                    await fetch(`${apiUrl}/api/v1/chat/cancel-task`, {
                                                        method: 'POST',
                                                        body: formData,
                                                        credentials: 'include',
                                                    });
                                                } catch (err) {
                                                    console.warn('[Cancel] Backend cancel error:', err);
                                                }
                                            }

                                            // 3. UI temizle
                                            setActiveGenerations([]);
                                            setVideoProgress(0);
                                            setVideoGenStatus("generating");
                                            setIsLoading(false);
                                            setProductionLogs([]);

                                            // 4. İptal mesajı ekle
                                            setMessages(prev => [...prev, {
                                                id: Date.now().toString(),
                                                role: 'assistant' as const,
                                                content: '🛑 İşlem iptal edildi.',
                                                timestamp: new Date(),
                                            }]);
                                        }}
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Input — ChatGPT Style */}
            <div
                className="p-3 lg:p-4 shrink-0"
                style={{ background: "var(--background-secondary)" }}
            >
                <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
                    <div
                        className="chat-input rounded-2xl overflow-hidden"
                        style={{
                            background: "var(--card)",
                            border: "1px solid var(--border)",
                        }}
                    >
                        {/* Inline Image Previews — Multi-Image Grid */}
                        {filePreviews.length > 0 && (
                            <div className="p-3 pb-0">
                                <div className="flex items-center gap-2 mb-1.5">
                                    <span className="text-xs font-medium" style={{ color: 'var(--foreground-muted)' }}>
                                        {filePreviews.length}/{MAX_FILES} görsel
                                    </span>
                                    {filePreviews.length > 1 && (
                                        <button
                                            type="button"
                                            onClick={removeAllAttachments}
                                            className="text-xs px-1.5 py-0.5 rounded hover:bg-red-500/20 transition-colors"
                                            style={{ color: 'var(--foreground-muted)' }}
                                        >
                                            Tümünü kaldır
                                        </button>
                                    )}
                                </div>
                                <div className="flex gap-2 overflow-x-auto pb-1" style={{ scrollbarWidth: 'thin' }}>
                                    {filePreviews.map((preview, index) => {
                                        const isAudioPreview = preview.match(/\.(wav|mp3|ogg|aac|flac)(\?.*)?$/i);
                                        return (
                                            <div key={index} className="relative shrink-0">
                                                {isAudioPreview ? (
                                                    <div
                                                        className="w-20 h-20 rounded-lg flex flex-col items-center justify-center bg-gradient-to-br from-amber-900/40 to-stone-900/40"
                                                        style={{ border: '1px solid var(--border)' }}
                                                    >
                                                        <span className="text-2xl">🎵</span>
                                                        <span className="text-[9px] text-white/60 mt-1">Ses</span>
                                                    </div>
                                                ) : (
                                                    <img
                                                        src={preview}
                                                        alt={`Referans görsel ${index + 1}`}
                                                        className="w-20 h-20 object-cover rounded-lg"
                                                        style={{ border: '1px solid var(--border)' }}
                                                    />
                                                )}
                                                <button
                                                    type="button"
                                                    onClick={() => removeFileAt(index)}
                                                    className="absolute -top-1.5 -right-1.5 p-1 rounded-full transition-colors hover:bg-red-500/80"
                                                    style={{ background: 'rgba(0,0,0,0.6)' }}
                                                    title="Kaldır"
                                                >
                                                    <X size={10} className="text-white" />
                                                </button>
                                            </div>
                                        );
                                    })}
                                    {/* Add more button */}
                                    {filePreviews.length < MAX_FILES && (
                                        <button
                                            type="button"
                                            onClick={() => fileInputRef.current?.click()}
                                            className="w-20 h-20 rounded-lg flex items-center justify-center shrink-0 hover:bg-[var(--background-secondary)] transition-colors"
                                            style={{ border: '1px dashed var(--border)' }}
                                            title="Daha fazla görsel ekle"
                                        >
                                            <span className="text-xl" style={{ color: 'var(--foreground-muted)' }}>+</span>
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Inline Video & Audio Previews — Side by Side */}
                        {(attachedVideoUrl || attachedAudioUrl) && (
                            <div className="p-3 pb-0 flex gap-3">
                                {attachedVideoUrl && (
                                    <div className="relative inline-block">
                                        <div
                                            className="w-36 h-24 bg-black rounded-xl overflow-hidden flex items-center justify-center"
                                            style={{ border: "1px solid var(--border)" }}
                                        >
                                            <video
                                                src={attachedVideoUrl}
                                                className="w-full h-full object-cover opacity-80"
                                            />
                                            <div className="absolute inset-0 flex items-center justify-center">
                                                <span className="text-white text-xs font-medium bg-black/50 px-2 py-1 rounded">📹 VİDEO</span>
                                            </div>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => setAttachedVideoUrl(null)}
                                            className="absolute top-1.5 right-1.5 p-1.5 rounded-full backdrop-blur-sm transition-colors hover:bg-black/60"
                                            style={{ background: "rgba(0,0,0,0.5)" }}
                                            title="Videoyu kaldır"
                                        >
                                            <X size={13} className="text-white" />
                                        </button>
                                    </div>
                                )}
                                {attachedAudioUrl && (
                                    <div className="relative inline-block">
                                        <div
                                            className="w-36 h-24 rounded-xl overflow-hidden flex flex-col items-center justify-center bg-gradient-to-br from-amber-900/40 to-stone-900/40"
                                            style={{ border: "1px solid var(--border)" }}
                                        >
                                            <span className="text-3xl">🎵</span>
                                            {attachedAudioLabel ? (
                                                <span className="text-white text-[9px] font-medium mt-0.5 text-center leading-tight line-clamp-2 px-1">{attachedAudioLabel}</span>
                                            ) : (
                                                <span className="text-white text-xs font-medium mt-1">SES DOSYASI</span>
                                            )}
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => { setAttachedAudioUrl(null); setAttachedAudioLabel(''); }}
                                            className="absolute top-1.5 right-1.5 p-1.5 rounded-full backdrop-blur-sm transition-colors hover:bg-black/60"
                                            style={{ background: "rgba(0,0,0,0.5)" }}
                                            title="Ses dosyasını kaldır"
                                        >
                                            <X size={13} className="text-white" />
                                        </button>
                                    </div>
                                )}
                            </div>
                        )}


                        {/* Text Input Row */}
                        <div className="flex items-end gap-2 p-2">
                            <button
                                type="button"
                                onClick={() => fileInputRef.current?.click()}
                                className={`p-2 rounded-lg transition-colors shrink-0 mb-0.5 ${attachedFiles.length > 0 ? 'bg-[var(--accent)]/20' : 'hover:bg-[var(--background-secondary)]'}`}
                                title="Referans görsel ekle (maks. 10)"
                            >
                                <Paperclip size={20} style={{ color: attachedFiles.length > 0 ? 'var(--accent)' : 'var(--foreground-muted)' }} />
                            </button>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="image/*"
                                multiple
                                onChange={handleFileSelect}
                                className="hidden"
                            />

                            <textarea
                                ref={inputRef}
                                value={input}
                                onChange={(e) => {
                                    setInput(e.target.value);
                                    // Auto-resize
                                    e.target.style.height = 'auto';
                                    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
                                }}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        if (input.trim() || attachedFiles.length > 0 || attachedVideoUrl || attachedAudioUrl) {
                                            handleSubmit(e as unknown as React.FormEvent);
                                        }
                                    }
                                }}
                                placeholder={isDragOver ? "Buraya bırak..." : isConnected ? "Herhangi bir şey sor" : "Backend bağlantısı bekleniyor..."}
                                className={`flex-1 bg-transparent outline-none text-sm lg:text-[15px] px-1 resize-none ${isDragOver ? 'text-[var(--accent)]' : ''}`}
                                style={{ color: "var(--foreground)", minHeight: '24px', maxHeight: '200px', overflowY: 'auto', lineHeight: '1.5' }}
                                disabled={isLoading || !isConnected}
                                rows={1}
                            />

                            <div className="flex items-end gap-1 shrink-0 mb-0.5">


                                {/* Plugin Yap Button */}
                                <button
                                    type="button"
                                    onClick={() => {
                                        const pluginMessage = "Bu sohbetteki bilgilerden bir preset oluştur.";
                                        setInput(pluginMessage);
                                        // Auto-send after a tick so React state updates first
                                        setTimeout(() => {
                                            const form = document.querySelector('form');
                                            if (form) form.requestSubmit();
                                        }, 50);
                                    }}
                                    className="p-2 rounded-lg transition-all hover:shadow-md"
                                    style={{
                                        background: "linear-gradient(135deg, rgba(201, 168, 76, 0.2) 0%, rgba(184, 150, 58, 0.15) 100%)",
                                        border: "1px solid rgba(201, 168, 76, 0.3)"
                                    }}
                                    title="Preset Oluştur"
                                    disabled={isLoading || !isConnected}
                                >
                                    <Sparkles size={18} style={{ color: '#C9A84C' }} />
                                </button>
                                {/* Mic icon removed — was non-functional */}
                                {isLoading ? (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            abortControllerRef.current?.abort();
                                            abortControllerRef.current = null;
                                            setIsLoading(false);
                                            setLoadingStatus("Düşünüyor...");
                                        }}
                                        className="p-2 rounded-full transition-all duration-200 hover:scale-110"
                                        style={{
                                            background: "#ef4444",
                                            color: "white"
                                        }}
                                        title="Durdur"
                                    >
                                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="3" width="10" height="10" rx="1.5" /></svg>
                                    </button>
                                ) : (
                                    <button
                                        type="submit"
                                        disabled={(!input.trim() && attachedFiles.length === 0 && !attachedVideoUrl && !attachedAudioUrl) || isLoading || !isConnected}
                                        className="p-2 rounded-full transition-all duration-200 disabled:opacity-40"
                                        style={{
                                            background: (input.trim() || attachedFiles.length > 0 || attachedVideoUrl || attachedAudioUrl) && isConnected ? "var(--accent)" : "var(--foreground-muted)",
                                            color: "var(--background)"
                                        }}
                                    >
                                        <Send size={16} />
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </form>
            </div>

            {/* Lightbox Modal */}
            {lightboxImage && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4"
                    style={{ background: "rgba(0, 0, 0, 0.85)", backdropFilter: "blur(8px)" }}
                    onClick={() => setLightboxImage(null)}
                    onKeyDown={(e) => e.key === 'Escape' && setLightboxImage(null)}
                    tabIndex={0}
                    ref={(el) => el?.focus()}
                >
                    {/* Close Button */}
                    <button
                        onClick={() => setLightboxImage(null)}
                        className="absolute top-4 right-4 p-2 rounded-full transition-colors hover:bg-white/20"
                        style={{ background: "rgba(255,255,255,0.1)" }}
                    >
                        <X size={24} className="text-white" />
                    </button>

                    {/* Open in New Tab */}
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            window.open(lightboxImage!, '_blank');
                        }}
                        className="absolute top-4 right-16 p-2 rounded-full transition-colors hover:bg-white/20"
                        style={{ background: "rgba(255,255,255,0.1)" }}
                        title="Yeni sekmede aç"
                    >
                        <ZoomIn size={24} className="text-white" />
                    </button>

                    {/* Image */}
                    <img
                        src={lightboxImage!}
                        alt="Büyütülmüş görsel"
                        className="max-w-[90vw] max-h-[90vh] object-contain rounded-xl shadow-2xl"
                        onClick={(e) => e.stopPropagation()}
                        style={{ animation: "fadeIn 0.2s ease-out" }}
                    />
                </div>
            )}

            {/* Video Lightbox */}
            {lightboxVideo && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4"
                    style={{ background: "rgba(0, 0, 0, 0.90)", backdropFilter: "blur(8px)" }}
                    onClick={() => setLightboxVideo(null)}
                    onKeyDown={(e) => e.key === 'Escape' && setLightboxVideo(null)}
                    tabIndex={0}
                    ref={(el) => el?.focus()}
                >
                    <button
                        onClick={() => setLightboxVideo(null)}
                        className="absolute top-4 right-4 p-2 rounded-full transition-colors hover:bg-white/20 z-10"
                        style={{ background: "rgba(255,255,255,0.1)" }}
                    >
                        <X size={24} className="text-white" />
                    </button>
                    <video
                        src={lightboxVideo}
                        controls
                        autoPlay
                        muted
                        playsInline
                        preload="metadata"
                        className="max-w-[90vw] max-h-[90vh] rounded-xl shadow-2xl"
                        onClick={(e) => e.stopPropagation()}
                        style={{ animation: "fadeIn 0.2s ease-out" }}
                    />
                </div>
            )}


        </div>
    );
}
