/**
 * Phase 1 happy path — 브리프 → 변주 선택 → DAG 저장 → 실행 다이얼로그 열기
 *
 * 모든 API 호출은 page.route()로 stub합니다.
 * 백엔드 없이도 CI에서 안정적으로 실행됩니다.
 *
 * Stub 대상 엔드포인트:
 *   POST /api/variants          → [StyleSummary]        (변주 생성)
 *   GET  /api/styles/test-001   → StyleDetail            (빌더 진입 시 로드)
 *   POST /api/styles/test-001/versions → SaveDagResponse (Cmd+S 저장)
 *   GET  /api/styles            → StyleListItem[]        (목록 페이지 진입 시)
 */

import { test, expect, type Page, type Route } from "@playwright/test";

// ─────────────────────────────────────────────
// Fixture 데이터 (snake_case — 백엔드 형식)
// ─────────────────────────────────────────────

const STYLE_ID = "test-001";
const VERSION_ID = "v1";

const VARIANT_LIST_RESPONSE = [
  {
    id: STYLE_ID,
    name: "공포 키링 광고 v1",
    version_id: VERSION_ID,
    tags: ["공포", "키링", "소품광고"],
    created_at: "2026-05-08T00:00:00.000Z",
  },
];

const STYLE_DETAIL_RESPONSE = {
  id: STYLE_ID,
  name: "공포 키링 광고 v1",
  concept: "공포 키링 광고",
  vertical: "소품광고",
  tags: ["공포", "키링"],
  status: "draft",
  current_version: 1,
  version_id: VERSION_ID,
  created_at: "2026-05-08T00:00:00.000Z",
  dag: {
    nodes: [
      {
        id: "node-text-1",
        type: "text_generation",
        model: { provider: "anthropic", model_id: "claude-3-5-haiku-20241022" },
        prompt_template: "공포스러운 키링 광고 카피를 작성해주세요.",
        inputs: [],
        variable_mapping: {},
      },
    ],
    edges: [],
    variables: [],
  },
};

const SAVE_DAG_RESPONSE = {
  version_id: "v2",
  version: 2,
  current_version: 2,
  created_at: "2026-05-08T01:00:00.000Z",
};

const STYLES_LIST_RESPONSE = [
  {
    id: STYLE_ID,
    name: "공포 키링 광고 v1",
    concept: "공포 키링 광고",
    vertical: "소품광고",
    tags: ["공포", "키링"],
    status: "draft",
    current_version: 1,
    version_id: VERSION_ID,
    created_at: "2026-05-08T00:00:00.000Z",
  },
];

// ─────────────────────────────────────────────
// Helper — API stub 설정
// ─────────────────────────────────────────────

async function stubApis(page: Page) {
  // GET /api/styles — 목록 (배열 또는 styles 키로 감싼 객체 모두 처리)
  await page.route("**/api/styles", async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(STYLES_LIST_RESPONSE),
      });
      return;
    }
    await route.continue();
  });

  // POST /api/variants — 변주 생성
  await page.route("**/api/variants", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(VARIANT_LIST_RESPONSE),
    });
  });

  // GET /api/styles/test-001 — style detail
  await page.route(`**/api/styles/${STYLE_ID}`, async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(STYLE_DETAIL_RESPONSE),
      });
      return;
    }
    await route.continue();
  });

  // POST /api/styles/test-001/versions — DAG 저장
  await page.route(`**/api/styles/${STYLE_ID}/versions`, async (route: Route) => {
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(SAVE_DAG_RESPONSE),
    });
  });
}

// ─────────────────────────────────────────────
// Phase 1 happy path
// ─────────────────────────────────────────────

test.describe("Phase 1 happy path", () => {
  test.beforeEach(async ({ page }) => {
    await stubApis(page);
  });

  test("designer can create a style, edit DAG, save, and open run dialog", async ({ page }) => {
    // ── Step 1: /styles 목록 페이지에서 새 Style 버튼 클릭 ──────────
    await page.goto("/styles");

    // 헤더의 "새 Style" 버튼이 보여야 한다
    const newStyleBtn = page.getByRole("button", { name: /새 Style/i }).first();
    await expect(newStyleBtn).toBeVisible({ timeout: 10_000 });
    await newStyleBtn.click();

    // /styles/new 라우트로 이동
    await expect(page).toHaveURL(/\/styles\/new$/);

    // ── Step 2: BriefForm — 필드 입력 후 변주 생성 ──────────────────
    // 페이지 제목 확인
    await expect(
      page.getByRole("heading", { name: /새 Style 만들기/i })
    ).toBeVisible({ timeout: 5_000 });

    // 컨셉 입력 — placeholder로 locator (shadcn FormControl이 div로 감싸 getByLabel이 동작하지 않음)
    await page.getByPlaceholder("예: 자연 속의 고요한 명상").fill("공포 키링 광고");

    // 버티컬 입력
    await page.getByPlaceholder("예: wellness, fashion, travel").fill("소품광고");

    // 톤 입력
    await page.getByPlaceholder("예: 따뜻하고 몽환적인").fill("어둑한, 긴장감, 차가운 색온도");

    // 단계 구성 체크박스 — Text Generation 선택
    // sr-only input의 부모 label 텍스트로 클릭
    await page.getByText("Text Generation").click();

    // 생성 개수를 1로 줄여 테스트 시간 단축
    await page.locator('input[type="number"]').fill("1");

    // 변주 생성 버튼 클릭 (POST /api/variants stub)
    await page.getByRole("button", { name: /변주 생성/i }).click();

    // ── Step 3: VariantPicker — 변주 카드 선택 ──────────────────────
    // "변주 선택" 제목이 등장해야 한다
    await expect(
      page.getByRole("heading", { name: /변주 선택/i })
    ).toBeVisible({ timeout: 10_000 });

    // 첫 번째 변주 카드가 렌더링된다
    const variantCard = page.getByRole("button", { name: /변주 1/i });
    await expect(variantCard).toBeVisible({ timeout: 5_000 });

    // 첫 번째 변주 선택 → /styles/test-001 로 이동
    await variantCard.click();
    await expect(page).toHaveURL(/\/styles\/test-001$/);

    // ── Step 4: StyleBuilder — 노드 확인 후 Ctrl+S 저장 ─────────────
    // ReactFlow 캔버스가 마운트될 때까지 대기
    // 저장 상태 인디케이터 span (aria-label="저장됨" 또는 "저장되지 않은 변경 있음")
    const saveIndicator = page.getByLabel(/저장됨|저장되지 않은 변경 있음/);
    await expect(saveIndicator).toBeVisible({ timeout: 10_000 });

    // 노드가 캔버스에 렌더링되는지 확인
    // TextNode는 "Text Generation" 텍스트를 포함한다
    await expect(page.getByText("Text Generation").first()).toBeVisible({ timeout: 5_000 });

    // Ctrl+S 저장 — stub이 201을 반환하므로 toast가 뜬다
    await page.keyboard.press("Control+s");

    // 저장 toast가 표시된다 ("저장되었습니다.")
    await expect(page.getByText("저장되었습니다.")).toBeVisible({ timeout: 5_000 });

    // ── Step 5: 실행 버튼 → RunStartDialog 열림 ─────────────────────
    const runBtn = page.getByRole("button", { name: /실행/i });
    await expect(runBtn).toBeVisible({ timeout: 5_000 });
    await runBtn.click();

    // 다이얼로그가 열린다
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 5_000 });

    // 다이얼로그 제목 확인
    await expect(dialog.getByText("실행 시작")).toBeVisible();

    // Escape로 다이얼로그 닫기
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible({ timeout: 3_000 });
  });
});
