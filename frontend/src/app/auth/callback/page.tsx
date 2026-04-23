'use client';

import { useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

function CallbackHandler() {
    const searchParams = useSearchParams();

    useEffect(() => {
        const token = searchParams.get('token');

        if (token) {
            // Check rememberMe preference (saved before OAuth redirect)
            const rememberMe = localStorage.getItem('rememberMe') !== 'false'; // Default to true

            // Clear any existing tokens
            localStorage.removeItem('token');
            sessionStorage.removeItem('token');

            // Save token to appropriate storage based on preference
            if (rememberMe) {
                localStorage.setItem('token', token);
            } else {
                sessionStorage.setItem('token', token);
            }

            // Use window.location for full page reload to ensure AuthContext picks up the token
            window.location.href = '/app';
        } else {
            // No token, redirect to login
            window.location.href = '/login';
        }
    }, [searchParams]);

    return (
        <div className="min-h-screen bg-[#0A0908] flex items-center justify-center">
            <div className="text-center">
                <div style={{ width: 48, height: 48, borderRadius: 12, background: 'linear-gradient(135deg, #D4B85C, #8B6D28)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="black"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5m14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>
                </div>
                <p className="text-gray-400">Giriş yapılıyor...</p>
                <div className="flex items-center justify-center gap-2 mt-4">
                    <div className="w-2 h-2 rounded-full bg-[#C9A84C] animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 rounded-full bg-[#C9A84C] animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 rounded-full bg-[#C9A84C] animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
            </div>
        </div>
    );
}

export default function AuthCallbackPage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-[#0A0908] flex items-center justify-center">
                <div className="text-center">
                    <div style={{ width: 48, height: 48, borderRadius: 12, background: 'linear-gradient(135deg, #D4B85C, #8B6D28)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="black"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5m14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>
                    </div>
                    <p className="text-gray-400">Yükleniyor...</p>
                </div>
            </div>
        }>
            <CallbackHandler />
        </Suspense>
    );
}

