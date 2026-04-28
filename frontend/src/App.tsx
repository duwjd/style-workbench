import { cn } from "@/lib/utils";

const NODE_DOTS = [
  { label: "Text",    color: "bg-node-text"   },
  { label: "Image",   color: "bg-node-image"  },
  { label: "Video",   color: "bg-node-video"  },
  { label: "Compose", color: "bg-node-comp"   },
] as const;

export function App() {
  return (
    <div className="min-h-screen bg-bg-base text-text-primary flex flex-col items-center justify-center gap-8 p-8">
      <h1 className="text-2xl font-semibold text-text-primary">
        Style Workbench — Token Check
      </h1>

      <div className="flex flex-col gap-3 w-full max-w-sm">
        {(["bg-bg-base","bg-bg-canvas","bg-bg-surface","bg-bg-elevated"] as const).map((cls) => (
          <div key={cls} className={cn("rounded-lg border border-border-default p-4", cls)}>
            <span className="text-sm text-text-secondary">{cls}</span>
          </div>
        ))}
      </div>

      <div className="flex gap-6 items-center">
        {NODE_DOTS.map(({ label, color }) => (
          <div key={label} className="flex flex-col items-center gap-2">
            <span className={cn("h-4 w-4 rounded-full", color)} />
            <span className="text-xs text-text-tertiary">{label}</span>
          </div>
        ))}
      </div>

      <div className="px-4 py-2 rounded-md bg-accent-500 text-text-on-accent font-medium">
        accent-500 CTA
      </div>
    </div>
  );
}

export default App;
