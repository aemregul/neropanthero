"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { ChatPanel } from "@/components/ChatPanel";
import { AssetsPanel } from "@/components/AssetsPanel";
import { NewProjectModal } from "@/components/NewProjectModal";
import { createSession, getSessions } from "@/lib/api";
import { FolderPlus, Sparkles } from "lucide-react";

export default function Home() {
  const router = useRouter();

  const [assetsCollapsed, setAssetsCollapsed] = useState(false);

  // === PROJE-BAZLI CHAT MİMARİSİ ===
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [pendingInputText, setPendingInputText] = useState<string | null>(null);
  const [pendingAssetUrl, setPendingAssetUrl] = useState<{ url: string; type: "image" | "video" | "audio" | "uploaded" } | null>(null);
  const [incomingAsset, setIncomingAsset] = useState<{ url: string; type: "image" | "video" | "audio" | "uploaded" } | null>(null);
  const [installedPlugins, setInstalledPlugins] = useState<Array<{ id: string; name: string; promptText: string }>>([]);
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [newProjectModalOpen, setNewProjectModalOpen] = useState(false);
  const [hasNoProjects, setHasNoProjects] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [assetRefreshKey, setAssetRefreshKey] = useState(0);

  // === PROJE LİSTESİ BAŞLAT ===
  useEffect(() => {
    const init = async () => {
      try {
        const sessions = await getSessions();
        const projects = sessions.filter(s => s.category !== 'main_chat');

        if (projects.length > 0) {
          const savedProjectId = localStorage.getItem('nero_active_project');
          const savedProject = savedProjectId ? projects.find(p => p.id === savedProjectId) : null;
          setActiveProjectId(savedProject ? savedProject.id : projects[0].id);
          setHasNoProjects(false);
        } else {
          setActiveProjectId(null);
          setHasNoProjects(true);
        }
      } catch (error) {
        console.error("Başlatma hatası:", error);
        setHasNoProjects(true);
      } finally {
        setIsLoading(false);
      }
    };

    init();
  }, [refreshKey]);

  const handleProjectChange = (projectId: string) => {
    setActiveProjectId(projectId);
    localStorage.setItem('nero_active_project', projectId);
    setHasNoProjects(false);
  };

  const handleProjectDelete = useCallback(() => {
    setActiveProjectId(null);
    setHasNoProjects(true);
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleNewAsset = useCallback((asset?: { url: string; type: string }) => {
    if (asset?.url && asset.type !== "refresh") {
      setIncomingAsset({
        url: asset.url,
        type: asset.type as "image" | "video" | "audio" | "uploaded",
      });
    }
    setAssetRefreshKey(prev => prev + 1);
  }, []);

  const handleCreateProject = async (name: string, description?: string, category?: string) => {
    setIsCreatingProject(true);
    try {
      const newSession = await createSession(name, description, category);
      setActiveProjectId(newSession.id);
      localStorage.setItem('nero_active_project', newSession.id);
      setHasNoProjects(false);
      setRefreshKey(prev => prev + 1);
    } catch (error) {
      console.error("Proje oluşturulamadı:", error);
    } finally {
      setIsCreatingProject(false);
    }
  };

  if (isLoading) {
    return (
      <main className="flex h-screen items-center justify-center" style={{ background: "var(--background)" }}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[var(--accent)] mx-auto mb-4"></div>
          <p style={{ color: "var(--foreground-muted)" }}>Yükleniyor...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        activeProjectId={activeProjectId || ""}
        onProjectChange={handleProjectChange}
        onProjectDelete={handleProjectDelete}
        sessionId={activeProjectId}
        refreshKey={refreshKey}
        onSendPrompt={setPendingPrompt}
        onSetInputText={setPendingInputText}
        onPluginsLoaded={setInstalledPlugins}
      />

      {/* Chat — proje seçili değilse hoşgeldin ekranı */}
      {!activeProjectId && hasNoProjects ? (
        <div className="flex-1 flex items-center justify-center" style={{ background: "var(--background)" }}>
          <div className="text-center max-w-md px-6">
            <div
              className="w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6"
              style={{
                background: "linear-gradient(135deg, #D4B85C 0%, #8B6D28 100%)",
                boxShadow: "0 10px 40px rgba(201, 168, 76, 0.3)"
              }}
            >
              <Sparkles size={40} className="text-white" />
            </div>
            <h1 className="text-2xl font-bold mb-3" style={{ color: "var(--foreground)", fontFamily: "var(--font-cormorant, 'Cormorant Garamond', serif)" }}>
              Nero Panthero AI Studio&apos;ya Hoş Geldiniz
            </h1>
            <p className="mb-8" style={{ color: "var(--foreground-muted)" }}>
              AI destekli iç mekan tasarımı için yeni bir proje oluşturun.
            </p>
            <button
              onClick={() => setNewProjectModalOpen(true)}
              disabled={isCreatingProject}
              className="inline-flex items-center gap-3 px-8 py-4 rounded-xl font-medium text-lg transition-all hover:scale-105 disabled:opacity-50"
              style={{
                background: "var(--accent)",
                color: "var(--background)",
                boxShadow: "0 4px 20px rgba(201, 168, 76, 0.4)"
              }}
            >
              {isCreatingProject ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-current"></div>
                  Oluşturuluyor...
                </>
              ) : (
                <>
                  <FolderPlus size={24} />
                  Yeni Proje Oluştur
                </>
              )}
            </button>
            <div className="mt-8 p-4 rounded-lg" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
              <p className="text-sm" style={{ color: "var(--foreground-muted)" }}>
                💡 <strong>İpucu:</strong> Sol menüdeki &quot;+&quot; butonuyla da yeni proje oluşturabilirsiniz.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <ChatPanel
          sessionId={activeProjectId || undefined}
          onNewAsset={handleNewAsset}
          onEntityChange={() => {}}
          pendingPrompt={pendingPrompt}
          onPromptConsumed={() => setPendingPrompt(null)}
          pendingInputText={pendingInputText}
          onInputTextConsumed={() => setPendingInputText(null)}
          installedPlugins={installedPlugins}
          pendingAssetUrl={pendingAssetUrl}
          onAssetUrlConsumed={() => setPendingAssetUrl(null)}
        />
      )}

      {/* Assets Panel — oluşturulan görselleri gösterir */}
      <AssetsPanel
        collapsed={assetsCollapsed}
        onToggle={() => setAssetsCollapsed(!assetsCollapsed)}
        sessionId={activeProjectId}
        refreshKey={assetRefreshKey}
        incomingAsset={incomingAsset}
        onIncomingAssetConsumed={() => setIncomingAsset(null)}
        onAssetDeleted={() => setRefreshKey(prev => prev + 1)}
        onAttachAssetUrl={(url, type) => setPendingAssetUrl({ url, type })}
      />

      {/* New Project Modal */}
      <NewProjectModal
        isOpen={newProjectModalOpen}
        onClose={() => setNewProjectModalOpen(false)}
        onSubmit={handleCreateProject}
      />
    </main>
  );
}
