'use client';

import Link from 'next/link';
import { ArrowRight, Sparkles, Video, Image, Wand2, Globe, Zap, Shield, Play, Star, Users, Layers, ChevronDown, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';

// Floating orb component for animated background
function FloatingOrb({ delay, size, color, position }: { delay: number; size: string; color: string; position: { top: string; left: string } }) {
    return (
        <div
            className={`absolute ${size} ${color} rounded-full blur-3xl opacity-30 animate-float`}
            style={{
                top: position.top,
                left: position.left,
                animationDelay: `${delay}s`,
                animationDuration: '8s',
            }}
        />
    );
}

// Animated counter component
function AnimatedCounter({ end, suffix = '', duration = 2000 }: { end: number; suffix?: string; duration?: number }) {
    const [count, setCount] = useState(0);
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setIsVisible(true);
                }
            },
            { threshold: 0.3 }
        );

        const element = document.getElementById(`counter-${end}`);
        if (element) observer.observe(element);

        return () => observer.disconnect();
    }, [end]);

    useEffect(() => {
        if (!isVisible) return;

        let startTime: number;
        const step = (timestamp: number) => {
            if (!startTime) startTime = timestamp;
            const progress = Math.min((timestamp - startTime) / duration, 1);
            setCount(Math.floor(progress * end));
            if (progress < 1) {
                requestAnimationFrame(step);
            }
        };
        requestAnimationFrame(step);
    }, [isVisible, end, duration]);

    return (
        <span id={`counter-${end}`}>
            {count}{suffix}
        </span>
    );
}

// Feature card component
function FeatureCard({ icon: Icon, title, description, color, delay }: { icon: React.ElementType; title: string; description: string; color: string; delay: number }) {
    return (
        <div
            className={`group relative bg-gray-900/50 backdrop-blur-xl rounded-2xl p-8 border border-gray-800/50 hover:border-${color}-500/50 transition-all duration-500 hover:transform hover:-translate-y-2`}
            style={{ animationDelay: `${delay}ms` }}
        >
            {/* Glow effect on hover */}
            <div className={`absolute inset-0 bg-gradient-to-br from-${color}-500/0 to-${color}-600/0 group-hover:from-${color}-500/10 group-hover:to-${color}-600/5 rounded-2xl transition-all duration-500`} />

            <div className="relative z-10">
                <div className={`w-14 h-14 bg-gradient-to-br from-${color}-500/20 to-${color}-600/10 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300`}>
                    <Icon size={28} className={`text-${color}-400`} />
                </div>
                <h3 className="text-xl font-semibold text-white mb-3">{title}</h3>
                <p className="text-gray-400 leading-relaxed">{description}</p>
            </div>
        </div>
    );
}

// Demo slides data
const demoSlides = [
    {
        title: "Karakter Oluştur",
        description: "Referans fotoğraf yükleyin veya açıklama yazın. AI karakterinizi öğrenir ve her üretimde tutarlı yüzler sağlar.",
        icon: Users,
        color: "emerald",
        example: "@johny adında sarı saçlı, mavi gözlü bir karakter oluştur"
    },
    {
        title: "Doğal Dille Üret",
        description: "Karakter etiketlerini (@johny) kullanarak istediğiniz sahneyi tanımlayın. AI doğru modeli seçer ve üretir.",
        icon: Sparkles,
        color: "cyan",
        example: "@johny'yi Paris'te Eyfel Kulesi önünde çiz"
    },
    {
        title: "Video Oluştur",
        description: "Kling 3.0 Pro, Google Veo 3.1 veya Grok Video ile görsellerinizi profesyonel videolara dönüştürün. Tek tıkla sinematik animasyon.",
        icon: Video,
        color: "purple",
        example: "Bu görseli 5 saniyelik bir videoya çevir"
    },
    {
        title: "Akıllı Düzenleme",
        description: "Face Swap, upscale, arka plan kaldırma. AI otomatik kalite kontrolü yapar ve gerekirse düzeltir.",
        icon: Wand2,
        color: "pink",
        example: "Bu görseli 4K'ya yükselt ve arka planı kaldır"
    },
    {
        title: "Web Araştırması",
        description: "İnternetten referans görseller ve marka bilgileri bulun. AI otomatik stil algılama yapar.",
        icon: Globe,
        color: "orange",
        example: "Sahibinden.com'un marka renklerini bul"
    }
];

// Demo Modal Component
function DemoModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
    const [currentSlide, setCurrentSlide] = useState(0);
    const [isAutoPlaying, setIsAutoPlaying] = useState(true);

    useEffect(() => {
        if (!isOpen) {
            setCurrentSlide(0);
            setIsAutoPlaying(true);
        }
    }, [isOpen]);

    useEffect(() => {
        if (!isOpen || !isAutoPlaying) return;

        const timer = setInterval(() => {
            setCurrentSlide((prev) => (prev + 1) % demoSlides.length);
        }, 4000);

        return () => clearInterval(timer);
    }, [isOpen, isAutoPlaying]);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (!isOpen) return;
            if (e.key === 'Escape') onClose();
            if (e.key === 'ArrowLeft') {
                setIsAutoPlaying(false);
                setCurrentSlide((prev) => (prev - 1 + demoSlides.length) % demoSlides.length);
            }
            if (e.key === 'ArrowRight') {
                setIsAutoPlaying(false);
                setCurrentSlide((prev) => (prev + 1) % demoSlides.length);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    const slide = demoSlides[currentSlide];
    const Icon = slide.icon;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-fadeIn"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="relative w-full max-w-3xl bg-gray-900/95 backdrop-blur-xl rounded-3xl border border-gray-800 shadow-2xl animate-slideUp overflow-hidden">
                {/* Close button */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 z-10 w-10 h-10 flex items-center justify-center rounded-full bg-gray-800/50 text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
                >
                    <X size={20} />
                </button>

                {/* Header */}
                <div className="px-8 pt-8 pb-4">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="flex gap-1.5">
                            <div className="w-3 h-3 rounded-full bg-red-500" />
                            <div className="w-3 h-3 rounded-full bg-yellow-500" />
                            <div className="w-3 h-3 rounded-full bg-green-500" />
                        </div>
                        <span className="text-gray-500 text-sm">Pepper Root AI Stüdyo - Demo</span>
                    </div>
                </div>

                {/* Content */}
                <div className="px-8 pb-8">
                    <div className="relative min-h-[300px]">
                        {/* Slide content */}
                        <div key={currentSlide} className="animate-fadeIn">
                            <div className="flex items-start gap-6">
                                {/* Icon */}
                                <div className={`flex-shrink-0 w-16 h-16 rounded-2xl bg-gradient-to-br from-${slide.color}-500/20 to-${slide.color}-600/10 flex items-center justify-center`}>
                                    <Icon size={32} className={`text-${slide.color}-400`} />
                                </div>

                                {/* Text */}
                                <div className="flex-1">
                                    <div className="text-xs text-gray-500 mb-2">ADIM {currentSlide + 1}/{demoSlides.length}</div>
                                    <h3 className="text-2xl font-bold text-white mb-3">{slide.title}</h3>
                                    <p className="text-gray-400 text-lg leading-relaxed mb-6">{slide.description}</p>

                                    {/* Example prompt */}
                                    <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
                                        <div className="text-xs text-gray-500 mb-2">ÖRNEK KULLANIM</div>
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center text-white text-xs font-bold">
                                                AI
                                            </div>
                                            <code className="text-emerald-400 text-sm">{slide.example}</code>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Navigation */}
                    <div className="flex items-center justify-between mt-8">
                        {/* Dots */}
                        <div className="flex items-center gap-2">
                            {demoSlides.map((_, index) => (
                                <button
                                    key={index}
                                    onClick={() => {
                                        setIsAutoPlaying(false);
                                        setCurrentSlide(index);
                                    }}
                                    className={`h-2 rounded-full transition-all duration-300 ${index === currentSlide
                                        ? 'w-8 bg-emerald-500'
                                        : 'w-2 bg-gray-700 hover:bg-gray-600'
                                        }`}
                                />
                            ))}
                        </div>

                        {/* Arrows */}
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => {
                                    setIsAutoPlaying(false);
                                    setCurrentSlide((prev) => (prev - 1 + demoSlides.length) % demoSlides.length);
                                }}
                                className="w-10 h-10 flex items-center justify-center rounded-full bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
                            >
                                <ChevronLeft size={20} />
                            </button>
                            <button
                                onClick={() => {
                                    setIsAutoPlaying(false);
                                    setCurrentSlide((prev) => (prev + 1) % demoSlides.length);
                                }}
                                className="w-10 h-10 flex items-center justify-center rounded-full bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
                            >
                                <ChevronRight size={20} />
                            </button>
                        </div>
                    </div>

                    {/* Auto-play indicator */}
                    <div className="flex items-center justify-center mt-6">
                        <button
                            onClick={() => setIsAutoPlaying(!isAutoPlaying)}
                            className="text-xs text-gray-500 hover:text-gray-400 transition-colors flex items-center gap-2"
                        >
                            <div className={`w-2 h-2 rounded-full ${isAutoPlaying ? 'bg-emerald-500 animate-pulse' : 'bg-gray-600'}`} />
                            {isAutoPlaying ? 'Otomatik oynatılıyor' : 'Duraklatıldı'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default function LandingPage() {
    const { user, isLoading } = useAuth();
    const [scrollY, setScrollY] = useState(0);
    const [isDemoOpen, setIsDemoOpen] = useState(false);

    useEffect(() => {
        const handleScroll = () => setScrollY(window.scrollY);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    // Show loading while checking auth (brief moment)
    if (isLoading) {
        return (
            <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
                <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#0a0a0f] overflow-hidden">
            {/* Demo Modal */}
            <DemoModal isOpen={isDemoOpen} onClose={() => setIsDemoOpen(false)} />

            {/* Animated Background */}
            <div className="fixed inset-0 overflow-hidden pointer-events-none">
                <FloatingOrb delay={0} size="w-96 h-96" color="bg-emerald-500" position={{ top: '10%', left: '10%' }} />
                <FloatingOrb delay={2} size="w-80 h-80" color="bg-purple-500" position={{ top: '60%', left: '70%' }} />
                <FloatingOrb delay={4} size="w-72 h-72" color="bg-cyan-500" position={{ top: '30%', left: '80%' }} />
                <FloatingOrb delay={1} size="w-64 h-64" color="bg-pink-500" position={{ top: '70%', left: '20%' }} />

                {/* Grid pattern overlay */}
                <div
                    className="absolute inset-0 opacity-[0.02]"
                    style={{
                        backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
                        backgroundSize: '50px 50px'
                    }}
                />
            </div>

            {/* Navigation */}
            <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${scrollY > 50 ? 'bg-gray-900/90 backdrop-blur-xl border-b border-gray-800/50' : 'bg-transparent'}`}>
                <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                    <Link
                        href="/"
                        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                        className="flex items-center gap-3 hover:opacity-80 transition-opacity cursor-pointer"
                    >
                        <div className="relative">
                            <img src="/logo.png" alt="Logo" className="w-16 h-16 object-contain" />
                            <div className="absolute -inset-1 bg-emerald-500/20 rounded-full blur-md -z-10" />
                        </div>
                        <div>
                            <span className="text-xl font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">Pepper Root</span>
                            <span className="text-xs text-emerald-400 block -mt-1">AI Agency</span>
                        </div>
                    </Link>
                    <div className="hidden md:flex items-center gap-8">
                        <a href="#features" className="text-gray-400 hover:text-white transition-colors text-sm">Özellikler</a>
                        <a href="#showcase" className="text-gray-400 hover:text-white transition-colors text-sm">Vitrin</a>
                        <a href="#stats" className="text-gray-400 hover:text-white transition-colors text-sm">Rakamlar</a>
                    </div>
                    <Link
                        href={user ? "/app" : "/login"}
                        className="relative group bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white px-6 py-2.5 rounded-full font-medium transition-all text-sm overflow-hidden"
                    >
                        <span className="relative z-10">{user ? "Uygulamaya Git" : "Giriş Yap"}</span>
                        <div className="absolute inset-0 bg-gradient-to-r from-emerald-400 to-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </Link>
                </div>
            </nav>

            {/* Hero Section */}
            <section className="relative pt-32 pb-24 px-6 min-h-screen flex items-center">
                <div className="max-w-7xl mx-auto w-full">
                    <div className="grid lg:grid-cols-2 gap-16 items-center">
                        {/* Left side - Content */}
                        <div className="text-left">
                            {/* Badge */}
                            <div className="inline-flex items-center gap-2 bg-gradient-to-r from-emerald-500/10 to-cyan-500/10 border border-emerald-500/20 text-emerald-400 px-4 py-2 rounded-full text-sm mb-8 animate-fadeIn">
                                <Sparkles size={16} className="animate-pulse" />
                                <span>Yapay Zeka Destekli Kreatif Stüdyo</span>
                            </div>

                            {/* Main Title */}
                            <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-white mb-6 leading-[1.1] animate-slideUp">
                                Hayal Et,
                                <br />
                                <span className="relative">
                                    <span className="bg-gradient-to-r from-emerald-400 via-cyan-400 to-purple-400 bg-clip-text text-transparent">
                                        AI Yaratsın
                                    </span>
                                    <svg className="absolute -bottom-2 left-0 w-full" viewBox="0 0 300 12" fill="none">
                                        <path d="M2 10C50 4 150 0 298 6" stroke="url(#gradient)" strokeWidth="3" strokeLinecap="round" />
                                        <defs>
                                            <linearGradient id="gradient" x1="0" y1="0" x2="300" y2="0">
                                                <stop offset="0%" stopColor="#4ade80" />
                                                <stop offset="50%" stopColor="#22d3ee" />
                                                <stop offset="100%" stopColor="#a78bfa" />
                                            </linearGradient>
                                        </defs>
                                    </svg>
                                </span>
                            </h1>

                            {/* Subtitle */}
                            <p className="text-lg md:text-xl text-gray-400 max-w-xl mb-10 leading-relaxed animate-slideUp" style={{ animationDelay: '100ms' }}>
                                Karakterler oluşturun, tutarlı görseller üretin, profesyonel videolar çıkarın.
                                <span className="text-white font-medium"> Tek bir konuşmayla.</span>
                            </p>

                            {/* CTA Buttons */}
                            <div className="flex flex-wrap items-center gap-4 mb-12 animate-slideUp" style={{ animationDelay: '200ms' }}>
                                <Link
                                    href={user ? "/app" : "/login"}
                                    className="group relative inline-flex items-center gap-3 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white px-8 py-4 rounded-2xl font-medium text-lg transition-all hover:scale-105 shadow-lg shadow-emerald-500/25 overflow-hidden"
                                >
                                    <span className="relative z-10">{user ? "Uygulamaya Git" : "Ücretsiz Dene"}</span>
                                    <ArrowRight size={20} className="relative z-10 group-hover:translate-x-1 transition-transform" />
                                    <div className="absolute inset-0 bg-gradient-to-r from-emerald-500 to-cyan-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                                </Link>
                                <button
                                    onClick={() => setIsDemoOpen(true)}
                                    className="group inline-flex items-center gap-3 text-gray-400 hover:text-white px-6 py-4 transition-colors"
                                >
                                    <div className="w-12 h-12 rounded-full bg-gray-800/50 border border-gray-700 flex items-center justify-center group-hover:border-emerald-500/50 group-hover:bg-gray-800 transition-all">
                                        <Play size={18} className="ml-0.5 group-hover:scale-110 transition-transform" />
                                    </div>
                                    <span>Demo İzle</span>
                                </button>
                            </div>

                            {/* Trust badges */}
                            <div className="flex items-center gap-6 text-sm text-gray-500 animate-slideUp" style={{ animationDelay: '300ms' }}>
                                <div className="flex items-center gap-2">
                                    <Shield size={16} className="text-emerald-500" />
                                    <span>Güvenli & Gizli</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Zap size={16} className="text-yellow-500" />
                                    <span>Anında Üretim</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Star size={16} className="text-purple-500" />
                                    <span>Premium Kalite</span>
                                </div>
                            </div>
                        </div>

                        {/* Right side - Demo Preview */}
                        <div className="relative animate-slideUp" style={{ animationDelay: '400ms' }}>
                            {/* Glowing border effect */}
                            <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500/50 via-cyan-500/50 to-purple-500/50 rounded-3xl blur-lg opacity-30" />

                            <div className="relative bg-gray-900/80 backdrop-blur-xl rounded-3xl border border-gray-800/50 p-6 shadow-2xl">
                                {/* Browser mockup header */}
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="w-3 h-3 rounded-full bg-red-500/80" />
                                    <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                                    <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                                    <div className="flex-1 mx-4 h-6 bg-gray-800/50 rounded-lg" />
                                </div>

                                {/* Demo content - Chat interface preview */}
                                <div className="bg-gray-950/50 rounded-2xl p-4 min-h-[350px] space-y-4">
                                    {/* AI Message */}
                                    <div className="flex items-start gap-3">
                                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                                            AI
                                        </div>
                                        <div className="bg-gray-800/50 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[280px]">
                                            <p className="text-gray-300 text-sm">Merhaba! @johny karakteri için görseller oluşturmaya hazırım. Nasıl bir sahne hayal ediyorsun?</p>
                                        </div>
                                    </div>

                                    {/* User Message */}
                                    <div className="flex items-start gap-3 justify-end">
                                        <div className="bg-gradient-to-r from-emerald-600 to-emerald-500 rounded-2xl rounded-tr-sm px-4 py-3 max-w-[280px]">
                                            <p className="text-white text-sm">@johny karakterini New York sokaklarında çiz</p>
                                        </div>
                                    </div>

                                    {/* Generated images preview */}
                                    <div className="grid grid-cols-3 gap-2 mt-4">
                                        <div className="aspect-square rounded-lg bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 border border-gray-700/50 flex items-center justify-center">
                                            <Image size={24} className="text-gray-600" />
                                        </div>
                                        <div className="aspect-square rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-gray-700/50 flex items-center justify-center">
                                            <Image size={24} className="text-gray-600" />
                                        </div>
                                        <div className="aspect-square rounded-lg bg-gradient-to-br from-cyan-500/20 to-emerald-500/20 border border-gray-700/50 flex items-center justify-center">
                                            <Image size={24} className="text-gray-600" />
                                        </div>
                                    </div>

                                    {/* Typing indicator */}
                                    <div className="flex items-center gap-2 text-gray-500 text-sm">
                                        <div className="flex gap-1">
                                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                                        </div>
                                        <span>AI üretiyor...</span>
                                    </div>
                                </div>
                            </div>

                            {/* Floating elements */}
                            <div className="absolute -right-4 top-20 bg-gray-900/90 backdrop-blur-xl rounded-xl border border-gray-800 p-3 shadow-xl animate-float" style={{ animationDelay: '1s' }}>
                                <div className="flex items-center gap-2">
                                    <Video size={16} className="text-cyan-400" />
                                    <span className="text-xs text-gray-300">Video Oluşturuldu</span>
                                </div>
                            </div>
                            <div className="absolute -left-4 bottom-20 bg-gray-900/90 backdrop-blur-xl rounded-xl border border-gray-800 p-3 shadow-xl animate-float" style={{ animationDelay: '2s' }}>
                                <div className="flex items-center gap-2">
                                    <Wand2 size={16} className="text-purple-400" />
                                    <span className="text-xs text-gray-300">Yüz Tutarlılığı ✓</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Scroll indicator */}
                    <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
                        <ChevronDown size={24} className="text-gray-600" />
                    </div>
                </div>
            </section>

            {/* Stats Section */}
            <section id="stats" className="relative py-20 px-6">
                <div className="max-w-6xl mx-auto">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                        <div className="text-center">
                            <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent mb-2">
                                <AnimatedCounter end={25} suffix="+" />
                            </div>
                            <p className="text-gray-400 text-sm">AI Modeli</p>
                        </div>
                        <div className="text-center">
                            <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent mb-2">
                                <AnimatedCounter end={100} suffix="x" />
                            </div>
                            <p className="text-gray-400 text-sm">Daha Hızlı</p>
                        </div>
                        <div className="text-center">
                            <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent mb-2">
                                <AnimatedCounter end={99} suffix="%" />
                            </div>
                            <p className="text-gray-400 text-sm">Yüz Tutarlılığı</p>
                        </div>
                        <div className="text-center">
                            <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-pink-400 to-emerald-400 bg-clip-text text-transparent mb-2">
                                <AnimatedCounter end={4} suffix="K" />
                            </div>
                            <p className="text-gray-400 text-sm">Çözünürlük</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section id="features" className="relative py-24 px-6">
                <div className="max-w-6xl mx-auto">
                    <div className="text-center mb-16">
                        <div className="inline-flex items-center gap-2 bg-purple-500/10 border border-purple-500/20 text-purple-400 px-4 py-2 rounded-full text-sm mb-6">
                            <Layers size={16} />
                            Tüm Araçlar Tek Yerde
                        </div>
                        <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
                            Kreatif Süper Güçler
                        </h2>
                        <p className="text-gray-400 max-w-2xl mx-auto text-lg">
                            Profesyonel içerik üretimi için ihtiyacınız olan her şey, yapay zeka destekli ve kullanımı kolay
                        </p>
                    </div>

                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        <FeatureCard
                            icon={Image}
                            title="Görsel Üretimi"
                            description="Nano Banana Pro, Flux, ve Grok Imagine ile yüksek kaliteli, tutarlı görseller. @karakter etiketiyle her zaman aynı yüz."
                            color="emerald"
                            delay={0}
                        />
                        <FeatureCard
                            icon={Video}
                            title="Sinematik Videolar"
                            description="Kling 3.0 Pro, Google Veo 3.1 ve Hailuo ile görsellerinizi destansı videolara dönüştürün. Tek tıkla kusursuz akış."
                            color="cyan"
                            delay={100}
                        />
                        <FeatureCard
                            icon={Globe}
                            title="Otonom Ajans (Swarm)"
                            description="Siz sadece hedefinizi söyleyin ('Nike yaz kampanyası'). Copywriter Agent metni yazar, AI görselleri planlar ve sunar."
                            color="orange"
                            delay={200}
                        />
                        <FeatureCard
                            icon={Wand2}
                            title="Self-Reflection (Otokontrol)"
                            description="Görsel içinde hatalı metin mi var? Asistan kendi kendine okur, hatayı fark eder ve düzeltip size sunar."
                            color="purple"
                            delay={300}
                        />
                        <FeatureCard
                            icon={Shield}
                            title="Marka Kimliği (Brand Book)"
                            description="Markanızın renklerini, yasaklı kelimelerini ve estetik zorunluluklarını sisteme öğretin, sınırların dışına asla çıkılmaz."
                            color="pink"
                            delay={400}
                        />
                        <FeatureCard
                            icon={Shield}
                            title="Güvenli Bulut"
                            description="Tüm üretimleriniz güvenle saklanır. Global Wardrobe ile projeler arası paylaşım."
                            color="pink"
                            delay={500}
                        />
                    </div>
                </div>
            </section>

            {/* Showcase Section */}
            <section id="showcase" className="relative py-24 px-6 overflow-hidden">
                <div className="max-w-6xl mx-auto">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
                            Nasıl Çalışıyor?
                        </h2>
                        <p className="text-gray-400 max-w-2xl mx-auto text-lg">
                            Üç basit adımda profesyonel içerikler üretin
                        </p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-8">
                        {/* Step 1 */}
                        <div className="relative group">
                            <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500/30 to-cyan-500/30 rounded-2xl blur opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="relative bg-gray-900/50 backdrop-blur-xl rounded-2xl p-8 border border-gray-800/50">
                                <div className="w-12 h-12 bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-xl flex items-center justify-center text-white font-bold text-xl mb-6">
                                    1
                                </div>
                                <h3 className="text-xl font-semibold text-white mb-3">Karakter Oluştur</h3>
                                <p className="text-gray-400">
                                    Referans fotoğraf yükleyin veya tanımlayın. AI karakterinizi öğrenir ve her üretimde tutarlı tutar.
                                </p>
                            </div>
                        </div>

                        {/* Step 2 */}
                        <div className="relative group">
                            <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500/30 to-purple-500/30 rounded-2xl blur opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="relative bg-gray-900/50 backdrop-blur-xl rounded-2xl p-8 border border-gray-800/50">
                                <div className="w-12 h-12 bg-gradient-to-r from-cyan-500 to-purple-500 rounded-xl flex items-center justify-center text-white font-bold text-xl mb-6">
                                    2
                                </div>
                                <h3 className="text-xl font-semibold text-white mb-3">Konuş ve Üret</h3>
                                <p className="text-gray-400">
                                    &ldquo;@johny&apos;yi Paris&apos;te çiz&rdquo; deyin. AI doğru modeli seçer, görseli üretir, kalite kontrolü yapar.
                                </p>
                            </div>
                        </div>

                        {/* Step 3 */}
                        <div className="relative group">
                            <div className="absolute -inset-1 bg-gradient-to-r from-purple-500/30 to-pink-500/30 rounded-2xl blur opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="relative bg-gray-900/50 backdrop-blur-xl rounded-2xl p-8 border border-gray-800/50">
                                <div className="w-12 h-12 bg-gradient-to-r from-purple-500 to-pink-500 rounded-xl flex items-center justify-center text-white font-bold text-xl mb-6">
                                    3
                                </div>
                                <h3 className="text-xl font-semibold text-white mb-3">Düzenle ve İndir</h3>
                                <p className="text-gray-400">
                                    Grid görünümünde düzenleyin, upscale yapın, video oluşturun. Her şey bulutta güvenle saklanır.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Final CTA Section */}
            <section className="relative py-24 px-6">
                <div className="max-w-4xl mx-auto text-center relative">
                    {/* Background glow */}
                    <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/20 via-cyan-500/20 to-purple-500/20 blur-3xl -z-10" />

                    <div className="bg-gradient-to-br from-gray-900/90 to-gray-800/90 backdrop-blur-xl rounded-3xl p-12 md:p-16 border border-gray-700/50">
                        <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-4 py-2 rounded-full text-sm mb-8">
                            <Users size={16} />
                            Hemen Katıl
                        </div>
                        <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
                            Yaratmaya Hazır mısınız?
                        </h2>
                        <p className="text-gray-400 mb-10 max-w-xl mx-auto text-lg">
                            Ücretsiz hesap oluşturun ve yapay zeka destekli kreatif stüdyonuzu keşfedin.
                        </p>
                        <Link
                            href="/login"
                            className="group relative inline-flex items-center gap-3 bg-white text-gray-900 px-10 py-5 rounded-2xl font-semibold text-lg transition-all hover:scale-105 shadow-2xl shadow-white/10 overflow-hidden"
                        >
                            <img src="/logo.png" alt="Logo" className="w-12 h-12 object-contain" />
                            <span className="relative z-10">Ücretsiz Başla</span>
                            <ArrowRight size={22} className="relative z-10 group-hover:translate-x-1 transition-transform" />
                        </Link>
                        <p className="text-gray-500 text-sm mt-6">
                            Anında erişim
                        </p>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer className="py-12 px-6 border-t border-gray-800/50">
                <div className="max-w-6xl mx-auto">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                        <div className="flex items-center gap-3">
                            <img src="/logo.png" alt="Logo" className="w-10 h-10 object-contain" />
                            <div>
                                <span className="text-white font-semibold">Pepper Root AI Agency</span>
                                <span className="text-gray-500 text-sm block">Pepper Root gücüyle.</span>
                            </div>
                        </div>

                        <p className="text-gray-600 text-sm">
                            © 2026 Tüm hakları saklıdır.
                        </p>
                    </div>
                </div>
            </footer>

            {/* CSS Animations */}
            <style jsx global>{`
                @keyframes float {
                    0%, 100% { transform: translateY(0) rotate(0deg); }
                    50% { transform: translateY(-20px) rotate(5deg); }
                }
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @keyframes slideUp {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .animate-float {
                    animation: float 6s ease-in-out infinite;
                }
                .animate-fadeIn {
                    animation: fadeIn 0.6s ease-out forwards;
                }
                .animate-slideUp {
                    animation: slideUp 0.6s ease-out forwards;
                }
            `}</style>
        </div>
    );
}
