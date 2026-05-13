import { useNavigate } from "react-router";
import { CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface PassBannerProps {
  /**
   * Run.status가 'succeeded' 이고
   * RetryAttemptListResponse.succeeded === true (모든 노드 PASS) 일 때 표시.
   */
  styleId: string;
}

/**
 * F01 §7.2 — 모든 노드 PASS 시 검수 안내 배너.
 *
 * AC-7 설계 원칙:
 *   - 이 컴포넌트는 절대 style.status='approved'를 자동으로 전이하지 않는다.
 *   - CTA는 /styles/:id/review 라우트로 이동만 한다.
 *   - 사람 verdict 없이는 approved 상태가 될 수 없음을 문구로 명시.
 */
export function PassBanner({ styleId }: PassBannerProps) {
  const navigate = useNavigate();

  return (
    <div
      role="status"
      aria-label="모든 노드 PASS — 검수 필요"
      className={cn(
        "flex items-center justify-between gap-4",
        "border-b border-info/20 bg-info/10",
        "px-4 py-3"
      )}
    >
      <div className="flex items-center gap-2">
        {/* 색에만 의존하지 않도록 아이콘 + 텍스트 동반 */}
        <CheckCircle2
          className="h-4 w-4 shrink-0 text-info"
          aria-hidden="true"
        />
        <p className="text-sm text-text-primary">
          모든 노드 PASS —{" "}
          <span className="text-text-secondary">
            디자이너 검수 후 &apos;approved&apos; 버튼으로 운영 승인하세요.
            <span className="ml-1 text-text-tertiary text-xs">
              (자동 승인 0건 — 사람 검수 필요)
            </span>
          </span>
        </p>
      </div>

      <Button
        size="sm"
        onClick={() => navigate(`/styles/${styleId}/review`)}
        aria-label="스타일 검수 화면으로 이동"
        className={cn(
          "shrink-0",
          "bg-info/20 text-info hover:bg-info/30 border border-info/40",
          "focus-visible:ring-1 focus-visible:ring-info"
        )}
      >
        검수 시작
      </Button>
    </div>
  );
}
