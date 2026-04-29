'use client';

import { createContext, useContext, ReactNode } from 'react';

interface User {
    id: string;
    email: string;
    full_name: string | null;
    avatar_url: string | null;
}

interface AuthContextType {
    user: User;
    isLoading: boolean;
}

// Sabit kullanıcı — auth gereksiz, direkt studio açılır
const DEFAULT_USER: User = {
    id: 'studio-user',
    email: 'studio@neropanthero.ai',
    full_name: 'Studio User',
    avatar_url: null,
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    return (
        <AuthContext.Provider value={{
            user: DEFAULT_USER,
            isLoading: false,
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
