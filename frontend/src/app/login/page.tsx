'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

// Floating orb component for animated background (same as landing page)
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

export default function LoginPage() {
    const router = useRouter();
    const { loginWithGoogle, user, isLoading: authLoading, rememberMe, setRememberMe } = useAuth();
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    // Redirect if already logged in
    useEffect(() => {
        if (user && !authLoading) {
            router.push('/app');
        }
    }, [user, authLoading, router]);

    // Loading state while checking auth
    if (authLoading) {
        return (
            <div className="min-h-screen bg-[#0A0908] flex items-center justify-center">
                <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-[#C9A84C] animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 rounded-full bg-[#C9A84C] animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 rounded-full bg-[#C9A84C] animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
            </div>
        );
    }

    // Already logged in, show nothing while redirecting
    if (user) {
        return null;
    }

    const handleGoogleLogin = async () => {
        setError('');
        setIsLoading(true);
        try {
            await loginWithGoogle();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Giriş yapılırken bir hata oluştu');
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#0A0908] flex items-center justify-center p-4 overflow-hidden relative">
            {/* Animated Background */}
            <div className="fixed inset-0 overflow-hidden pointer-events-none">
                <FloatingOrb delay={0} size="w-96 h-96" color="bg-amber-600" position={{ top: '10%', left: '10%' }} />
                <FloatingOrb delay={2} size="w-80 h-80" color="bg-amber-800" position={{ top: '60%', left: '70%' }} />
                <FloatingOrb delay={4} size="w-72 h-72" color="bg-yellow-700" position={{ top: '30%', left: '80%' }} />
                <FloatingOrb delay={1} size="w-64 h-64" color="bg-orange-900" position={{ top: '70%', left: '20%' }} />

                {/* Grid pattern overlay */}
                <div
                    className="absolute inset-0 opacity-[0.02]"
                    style={{
                        backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
                        backgroundSize: '50px 50px'
                    }}
                />
            </div>

            <div className="w-full max-w-md relative z-10">
                {/* Logo */}
                <Link
                    href="/"
                    className="flex items-center justify-center gap-3 mb-8 hover:opacity-80 transition-opacity"
                >
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#D4B85C] to-[#8B6D28] flex items-center justify-center">
                        <svg className="w-5 h-5 text-black" viewBox="0 0 24 24" fill="currentColor"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5m14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>
                    </div>
                    <div className="text-center">
                        <h1 className="text-2xl font-bold bg-gradient-to-r from-[#E8E3D8] to-[#C9A84C] bg-clip-text text-transparent" style={{ fontFamily: "'Cormorant Garamond', serif" }}>Luxora</h1>
                        <p className="text-[#C9A84C] text-sm -mt-1">AI Studio</p>
                    </div>
                </Link>

                {/* Card */}
                <div className="relative">
                    {/* Glowing border effect */}
                    <div className="absolute -inset-1 bg-gradient-to-r from-[#C9A84C]/30 via-[#8B6D28]/20 to-[#C9A84C]/30 rounded-3xl blur-lg opacity-50" />

                    <div className="relative bg-[#12110F]/90 backdrop-blur-xl rounded-2xl p-8 border border-[#2A2620] shadow-2xl">
                        {/* Title */}
                        <div className="text-center mb-6">
                            <h2 className="text-xl font-semibold text-white mb-2">Hoş Geldin</h2>
                            <p className="text-gray-400 text-sm">Devam etmek için giriş yap</p>
                        </div>

                        {/* Error Message */}
                        {error && (
                            <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-xl text-sm flex items-center gap-2 mb-6">
                                <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                {error}
                            </div>
                        )}

                        {/* Google Login Button */}
                        <button
                            onClick={handleGoogleLogin}
                            disabled={isLoading}
                            className="w-full flex items-center justify-center gap-3 bg-white hover:bg-gray-100 text-gray-800 py-4 rounded-xl font-medium transition-all hover:scale-[1.02] shadow-lg disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                        >
                            {isLoading ? (
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-gray-600 animate-bounce" style={{ animationDelay: '0ms' }} />
                                    <div className="w-2 h-2 rounded-full bg-gray-600 animate-bounce" style={{ animationDelay: '150ms' }} />
                                    <div className="w-2 h-2 rounded-full bg-gray-600 animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                            ) : (
                                <>
                                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                                        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                                        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                                        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                                        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                                    </svg>
                                    Google ile Giriş Yap
                                </>
                            )}
                        </button>

                        {/* Remember Me Checkbox */}
                        <label className="flex items-center justify-center gap-3 mt-4 cursor-pointer group">
                            <button
                                type="button"
                                onClick={() => setRememberMe(!rememberMe)}
                                className={`w-5 h-5 rounded-md border-2 transition-all flex items-center justify-center ${rememberMe
                                    ? 'bg-[#C9A84C] border-[#C9A84C]'
                                    : 'bg-gray-800/50 border-gray-600 hover:border-gray-500'
                                    }`}
                            >
                                {rememberMe && (
                                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                    </svg>
                                )}
                            </button>
                            <span className="text-gray-400 text-sm group-hover:text-gray-300 transition-colors select-none">Hesabımı hatırla</span>
                        </label>

                        {/* Privacy Note */}
                        <p className="text-gray-500 text-xs text-center mt-6">
                            Giriş yaparak <span className="text-gray-400">Kullanım Şartları</span> ve <span className="text-gray-400">Gizlilik Politikası</span>&apos;nı kabul etmiş olursunuz.
                        </p>
                    </div>
                </div>

                {/* Back to Home */}
                <div className="text-center mt-6">
                    <Link
                        href="/"
                        className="text-gray-500 hover:text-[#C9A84C] text-sm transition-colors inline-flex items-center gap-2"
                    >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                        </svg>
                        Ana Sayfaya Dön
                    </Link>
                </div>

                {/* Footer */}
                <p className="text-center text-gray-600 text-sm mt-4">
                    © 2026 Luxora AI Studio
                </p>
            </div>

            {/* CSS Animations */}
            <style jsx global>{`
                @keyframes float {
                    0%, 100% { transform: translateY(0) rotate(0deg); }
                    50% { transform: translateY(-20px) rotate(5deg); }
                }
                .animate-float {
                    animation: float 6s ease-in-out infinite;
                }
            `}</style>
        </div>
    );
}
