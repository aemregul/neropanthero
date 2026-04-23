'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function LandingPage() {
    const router = useRouter();

    useEffect(() => {
        router.replace('/app');
    }, [router]);

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
