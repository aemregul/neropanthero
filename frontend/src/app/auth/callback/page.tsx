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
        <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
            <div className="text-center">
                <span className="text-6xl mb-4 animate-pulse">🫑</span>
                <p className="text-gray-400">Giriş yapılıyor...</p>
                <div className="flex items-center justify-center gap-2 mt-4">
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
            </div>
        </div>
    );
}

export default function AuthCallbackPage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
                <div className="text-center">
                    <span className="text-6xl mb-4 animate-pulse">🫑</span>
                    <p className="text-gray-400">Yükleniyor...</p>
                </div>
            </div>
        }>
            <CallbackHandler />
        </Suspense>
    );
}

