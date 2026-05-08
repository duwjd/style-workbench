import { Outlet, Link } from "react-router";
import { Moon, Sun, Settings, Layers } from "lucide-react";
import { useUiStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Layout() {
  const { theme, toggleTheme } = useUiStore();

  return (
    <div
      className={cn("min-h-screen bg-bg-base text-text-primary")}
      data-theme={theme}
    >
      {/* 1280px 미만 경고 */}
      <div className="flex lg:hidden items-center justify-center h-screen px-6">
        <p className="text-text-secondary text-sm text-center">
          Style Workbench는 1280px 이상 데스크톱 환경을 권장합니다.
        </p>
      </div>

      {/* 실제 앱 */}
      <div className="hidden lg:flex flex-col h-screen">
        <header className="h-12 border-b border-border-subtle bg-bg-surface flex items-center px-4 gap-4 shrink-0">
          <Link
            to="/styles"
            className="flex items-center gap-2 text-text-primary hover:text-accent-300 transition-colors"
          >
            <Layers className="h-4 w-4" aria-hidden="true" />
            <span className="font-semibold text-sm">Style Workbench</span>
          </Link>

          <nav className="flex-1 flex items-center gap-1" aria-label="주 내비게이션">
            <Link
              to="/styles"
              className="text-sm text-text-secondary hover:text-text-primary px-2 py-1 rounded hover:bg-bg-hover transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500"
            >
              Styles
            </Link>
          </nav>

          <Button
            variant="ghost"
            size="icon-sm"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "라이트 모드로 전환" : "다크 모드로 전환"}
          >
            {theme === "dark" ? (
              <Sun className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Moon className="h-4 w-4" aria-hidden="true" />
            )}
          </Button>

          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="설정"
          >
            <Settings className="h-4 w-4" aria-hidden="true" />
          </Button>
        </header>

        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
