/**
 * F01 — Auto Evaluation Loop e2e (AC-10)
 *
 * 모든 API / SSE 호출은 page.route() 및 EventSource mock으로 stub합니다.
 * 백엔드 없이 CI에서 안정적으로 실행됩니다.
 *
 * Stub 대상:
 *   GET  /api/styles/style-001           → StyleDetail
 *   GET  /api/runs/run-001               → Run (succeeded)
 *   GET  /api/runs/run-001/retry-attempts → RetryAttemptListResponse
 *   POST /api/runs                        → Run (pending)
 *   GET  /api/runs/run-001/events         → SSE mock (EventSource)
 */

import { test, expect, type Page, type Route } from "@playwright/test";

// ─── Fixture 데이터 ───────────────────────────────────────────────────────────

const STYLE_ID = "style-001";
const RUN_ID = "run-001";
const VERSION_ID = "v1";

const STYLE_DETAIL = {
  id: STYLE_ID,
  name: "테스트 스타일",
  concept: "테스트",
  vertical: "테스트",
  tags: [],
  status: "draft",
  current_version: 1,
  version_id: VERSION_ID,
  created_at: "2026-05-08T00:00:00.000Z",
  dag: {
    nodes: [
      {
        id: "img1",
        type: "image_generation",
        model: { provider: "replicate", model_id: "flux-dev" },
        prompt_template: "테스트 이미지 생성",
        inputs: [],
        variable_mapping: {},
      },
    ],
    edges: [],
    variables: [],
  },
};

const RUN_PENDING = {
  id: RUN_ID,
  style_version_id: VERSION_ID,
  style_id: STYLE_ID,
  status: "pending",
  total_cost: null,
  created_at: "2026-05-08T03:10:00.000Z",
  started_at: "2026-05-08T03:10:01.000Z",
  finished_at: null,
  node_executions: [],
};

const RUN_SUCCEEDED = {
  id: RUN_ID,
  style_version_id: VERSION_ID,
  style_id: STYLE_ID,
  status: "succeeded",
  total_cost: 0.025,
  created_at: "2026-05-08T03:10:00.000Z",
  started_at: "2026-05-08T03:10:01.000Z",
  finished_at: "2026-05-08T03:16:10.000Z",
  node_executions: [
    {
      id: "nexec-1",
      node_id: "img1",
      node_type: "image_generation",
      model_provider: "replicate",
      model_id: "flux-dev",
      artifact_url: null,
      cost: 0.025,
      status: "succeeded",
      started_at: "2026-05-08T03:10:05.000Z",
      finished_at: "2026-05-08T03:16:08.000Z",
    },
  ],
};

const RETRY_ATTEMPTS = {
  run_id: RUN_ID,
  attempts: [
    {
      id: "rta-1",
      node_id: "img1",
      attempt_number: 0,
      prompt_version_id_used: null,
      retry_guidance: null,
      evaluation_id: "eval-1",
      cost_won: "12500.00",
      passed: false,
      failed_dimensions: ["composition", "lighting"],
      started_at: "2026-05-08T03:14:22Z",
      finished_at: "2026-05-08T03:15:01Z",
    },
    {
      id: "rta-2",
      node_id: "img1",
      attempt_number: 1,
      prompt_version_id_used: "pmv_01JX000001",
      retry_guidance: {
        instruction: "주광원을 좌측 45도에서 우측 정면으로 변경, 배경 단순화",
        confidence: 0.82,
      },
      evaluation_id: "eval-2",
      cost_won: "12500.00",
      passed: true,
      failed_dimensions: [],
      started_at: "2026-05-08T03:15:30Z",
      finished_at: "2026-05-08T03:16:08Z",
    },
  ],
  total_attempts: 2,
  succeeded: true,
};

// ─── API stub helper ──────────────────────────────────────────────────────────

async function stubApis(page: Page) {
  // GET /api/styles/style-001
  await page.route(`**/api/styles/${STYLE_ID}`, async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(STYLE_DETAIL),
      });
      return;
    }
    await route.continue();
  });

  // POST /api/runs → pending
  await page.route("**/api/runs", async (route: Route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(RUN_PENDING),
      });
      return;
    }
    await route.continue();
  });

  // GET /api/runs/run-001 → succeeded
  await page.route(`**/api/runs/${RUN_ID}`, async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(RUN_SUCCEEDED),
      });
      return;
    }
    await route.continue();
  });

  // GET /api/runs/run-001/retry-attempts
  await page.route(
    `**/api/runs/${RUN_ID}/retry-attempts`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(RETRY_ATTEMPTS),
      });
    }
  );

  // SSE: /api/runs/run-001/events — EventSource를 시뮬레이션
  // EventSource는 page.route로 직접 stub하기 어려우므로
  // page.addInitScript로 EventSource를 가로채 즉시 run_completed를 방출한다.
  await page.addInitScript(() => {
    const OriginalEventSource = window.EventSource;
    (window as Window & typeof globalThis & { EventSource: typeof EventSource }).EventSource = class MockEventSource extends EventTarget {
      static readonly CONNECTING = 0;
      static readonly OPEN = 1;
      static readonly CLOSED = 2;
      readonly CONNECTING = 0;
      readonly OPEN = 1;
      readonly CLOSED = 2;

      readyState: number = MockEventSource.CONNECTING;
      url: string;
      withCredentials: boolean = false;
      onerror: ((ev: Event) => void) | null = null;
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onopen: ((ev: Event) => void) | null = null;

      constructor(url: string | URL, _init?: EventSourceInit) {
        super();
        this.url = url.toString();

        // run detail SSE만 mock
        if (this.url.includes("/events")) {
          this.readyState = MockEventSource.OPEN;
          // 순서대로 이벤트 방출
          setTimeout(() => this._emit("node_started", { node_id: "img1", node_type: "image_generation" }), 10);
          setTimeout(() => this._emit("node_retry", { run_id: "run-001", node_id: "img1", attempt_number: 1, retry_guidance: { instruction: "테스트" }, failed_dimensions: ["composition"] }), 20);
          setTimeout(() => this._emit("node_completed", { node_id: "img1" }), 30);
          setTimeout(() => this._emit("run_completed", {}), 40);
        } else {
          // 실제 EventSource 사용
          return new OriginalEventSource(url, _init) as unknown as MockEventSource;
        }
      }

      _emit(type: string, data: unknown) {
        const ev = new MessageEvent(type, {
          data: JSON.stringify(data),
        });
        this.dispatchEvent(ev);
      }

      close() {
        this.readyState = MockEventSource.CLOSED;
      }
    } as unknown as typeof EventSource;
  });
}

// ─── 테스트 ───────────────────────────────────────────────────────────────────

test.describe("F01 — Auto Evaluation Loop (AC-10)", () => {
  test.beforeEach(async ({ page }) => {
    await stubApis(page);
  });

  test("retry timeline에 attempt 카드가 2개 이상 표시된다", async ({
    page,
  }) => {
    // Run detail 페이지 직접 진입
    await page.goto(`/runs/${RUN_ID}`);

    // retry timeline 섹션이 렌더링될 때까지 대기
    await expect(
      page.getByRole("region", { name: /재시도 타임라인/ })
    ).toBeVisible({ timeout: 10_000 });

    // Attempt #1, #2 카드가 모두 표시된다
    await expect(page.getByText("Attempt #1")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Attempt #2")).toBeVisible({ timeout: 5_000 });
  });

  test("FAIL attempt에 실패 차원 chip이 표시된다", async ({ page }) => {
    await page.goto(`/runs/${RUN_ID}`);

    await expect(
      page.getByRole("region", { name: /재시도 타임라인/ })
    ).toBeVisible({ timeout: 10_000 });

    // Attempt #1은 FAIL이며 composition, lighting 차원 표시
    await expect(page.getByText("composition")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("lighting")).toBeVisible({ timeout: 5_000 });
  });

  test("모든 노드 PASS 시 검수 안내 배너가 표시된다", async ({ page }) => {
    await page.goto(`/runs/${RUN_ID}`);

    // PassBanner가 표시된다 (succeeded=true, run.status='succeeded')
    await expect(
      page.getByRole("status", { name: /모든 노드 PASS/ })
    ).toBeVisible({ timeout: 10_000 });

    // "검수 시작" CTA가 존재한다
    await expect(
      page.getByRole("button", { name: /검수 시작/ })
    ).toBeVisible({ timeout: 5_000 });
  });

  test("'검수 시작' CTA 클릭 시 /styles/:id/review 로 이동한다", async ({
    page,
  }) => {
    await page.goto(`/runs/${RUN_ID}`);

    await expect(
      page.getByRole("status", { name: /모든 노드 PASS/ })
    ).toBeVisible({ timeout: 10_000 });

    await page.getByRole("button", { name: /검수 시작/ }).click();

    // /styles/style-001/review 로 이동 확인
    await expect(page).toHaveURL(new RegExp(`/styles/${STYLE_ID}/review`), {
      timeout: 5_000,
    });
  });

  test("AC-7: 배너가 style.status를 자동으로 'approved'로 전이하지 않는다", async ({
    page,
  }) => {
    // PATCH /api/styles/*/status 요청 감지
    const statusRequests: string[] = [];
    await page.route("**/api/styles/*/status", async (route: Route) => {
      statusRequests.push(route.request().postData() ?? "");
      await route.fulfill({ status: 200, body: "{}" });
    });

    await page.goto(`/runs/${RUN_ID}`);

    await expect(
      page.getByRole("status", { name: /모든 노드 PASS/ })
    ).toBeVisible({ timeout: 10_000 });

    // 배너 렌더링 후 자동 approved 요청이 0건이어야 함
    // eslint-disable-next-line playwright/no-wait-for-timeout
    await page.waitForTimeout(500);
    const approvedRequests = statusRequests.filter((body) =>
      body.includes("approved")
    );
    expect(approvedRequests).toHaveLength(0);
  });
});
