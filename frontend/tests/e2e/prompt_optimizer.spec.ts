/**
 * F02 Prompt Optimizer e2e — spec §9 AC-10
 *
 * 시나리오:
 *   1. /prompts/:id → "Optimize" 버튼 클릭 → 다이얼로그 열림
 *   2. Mode B 입력 (retry_guidance + failed_dimensions + parent_version)
 *   3. "Optimize 실행" → API stub succeeded=true → compare 페이지 이동
 *   4. compare 페이지에 "F02 자동 수정 결과" 배지 표시
 *   5. 실패 시나리오: API stub succeeded=false → toast 에러 + 다이얼로그 유지
 *
 * 모든 API는 page.route()로 stub (LLM 실제 호출 없음).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const PROMPT_ID = "prm-001";
const PARENT_VERSION_ID = "pmv-001";
const NEW_VERSION_ID = "pmv-003";
const OPTIMIZATION_ID = "po-001";

const VERSION_1_RESPONSE = {
  id: PARENT_VERSION_ID,
  version: 1,
  body: "Generate a portrait for {name}",
  declared_variables: [{ name: "name", role: "person_name", required: true }],
  model_default: null,
  parent_version_id: null,
  change_note: null,
  created_at: "2026-05-08T00:00:00.000Z",
  created_by: null,
};

const VERSION_3_RESPONSE = {
  id: NEW_VERSION_ID,
  version: 3,
  body: "Generate a portrait for {name} with improved lighting",
  declared_variables: [{ name: "name", role: "person_name", required: true }],
  model_default: null,
  parent_version_id: PARENT_VERSION_ID,
  change_note: "auto:F02 — lighting 관련 추가 지시",
  created_at: "2026-05-08T01:00:00.000Z",
  created_by: "auto:F02",
};

const PROMPT_RESPONSE = {
  id: PROMPT_ID,
  name: "Business portrait prompt",
  node_type: "image",
  status: "draft",
  owner: null,
  tags: ["portrait"],
  current_version: VERSION_1_RESPONSE,
  usages: [],
  usage_count_total: 0,
  created_at: "2026-05-08T00:00:00.000Z",
  updated_at: "2026-05-08T00:00:00.000Z",
};

const OPTIMIZE_SUCCESS_RESPONSE = {
  optimization_id: OPTIMIZATION_ID,
  prompt_id: PROMPT_ID,
  parent_version_id: PARENT_VERSION_ID,
  new_version_id: NEW_VERSION_ID,
  change_summary: "lighting 관련 추가 지시 + 주광원 방향 명시",
  cost_won: "312.50",
  latency_ms: 4523,
  succeeded: true,
  failure_reason: null,
};

const OPTIMIZE_FAILURE_RESPONSE = {
  optimization_id: "po-002",
  prompt_id: PROMPT_ID,
  parent_version_id: PARENT_VERSION_ID,
  new_version_id: null,
  change_summary: null,
  cost_won: "100.00",
  latency_ms: 2000,
  succeeded: false,
  failure_reason: "PromptOptimizerInvalidOutputError: missing placeholder {name}",
};

const OPTIMIZATION_LIST_RESPONSE = {
  items: [
    {
      optimization_id: OPTIMIZATION_ID,
      parent_version_id: PARENT_VERSION_ID,
      new_version_id: NEW_VERSION_ID,
      change_summary: "lighting 관련 추가 지시 + 주광원 방향 명시",
      cost_won: "312.50",
      succeeded: true,
      failure_reason: null,
      created_at: "2026-05-08T01:00:00.000Z",
    },
  ],
  total: 1,
  limit: 20,
  offset: 0,
};

const VERSIONS_RESPONSE = {
  items: [VERSION_1_RESPONSE],
  total: 1,
  limit: 50,
  offset: 0,
};

// ─── Setup helpers ─────────────────────────────────────────────────────────────

async function setupCommonRoutes(page: Page) {
  await page.route(`**/api/prompts/${PROMPT_ID}`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { ETag: `W/"2026-05-08T00:00:00.000Z"` },
      body: JSON.stringify(PROMPT_RESPONSE),
    });
  });

  await page.route(
    `**/api/prompts/${PROMPT_ID}/usages*`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      });
    }
  );

  await page.route(
    `**/api/prompts/${PROMPT_ID}/versions*`,
    async (route: Route) => {
      const url = route.request().url();
      if (url.includes(`/${PARENT_VERSION_ID}`)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(VERSION_1_RESPONSE),
        });
      } else if (url.includes(`/${NEW_VERSION_ID}`)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(VERSION_3_RESPONSE),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(VERSIONS_RESPONSE),
        });
      }
    }
  );

  await page.route(
    `**/api/prompts/${PROMPT_ID}/optimizations*`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(OPTIMIZATION_LIST_RESPONSE),
      });
    }
  );
}

// ─── Test Cases ────────────────────────────────────────────────────────────────

test.describe("F02 Prompt Optimizer", () => {
  test("AC-10(1): Optimize 버튼이 PromptDetail 헤더에 표시된다", async ({
    page,
  }) => {
    await setupCommonRoutes(page);
    await page.goto(`/prompts/${PROMPT_ID}`);

    await expect(
      page.getByRole("button", { name: "F02 Prompt Optimize 실행" })
    ).toBeVisible();
  });

  test("AC-10(2): Optimize 클릭 → 다이얼로그 열림 → Mode B 기본 표시", async ({
    page,
  }) => {
    await setupCommonRoutes(page);
    await page.goto(`/prompts/${PROMPT_ID}`);

    await page
      .getByRole("button", { name: "F02 Prompt Optimize 실행" })
      .click();

    await expect(page.getByText("F02 Prompt Optimize")).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "Mode B — 직접 입력" })
    ).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "Mode A — evaluation 자동" })
    ).toBeVisible();

    // Mode B 필드 표시
    await expect(page.getByLabelText("기준 버전 선택")).toBeVisible();
    await expect(page.getByLabelText("수정 지침 입력")).toBeVisible();
    await expect(page.getByLabelText("실패 차원 입력")).toBeVisible();
  });

  test("AC-10(3): Mode B 입력 → Optimize 실행 → succeeded=true → compare 이동", async ({
    page,
  }) => {
    await setupCommonRoutes(page);

    // Optimize endpoint stub (succeeded=true)
    await page.route(
      `**/api/prompts/${PROMPT_ID}/optimize`,
      async (route: Route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(OPTIMIZE_SUCCESS_RESPONSE),
        });
      }
    );

    await page.goto(`/prompts/${PROMPT_ID}`);

    await page
      .getByRole("button", { name: "F02 Prompt Optimize 실행" })
      .click();

    // 기준 버전 선택
    const versionSelect = page.getByLabel("기준 버전 선택");
    await versionSelect.selectOption(PARENT_VERSION_ID);

    // retry_guidance 입력
    await page
      .getByLabel("수정 지침 입력")
      .fill("주광원 방향을 왼쪽으로 변경");

    // dimension 추가 (quick-add 버튼 사용)
    await page
      .getByRole("button", { name: "lighting 차원 빠른 추가" })
      .click();

    // Optimize 실행
    const submitBtn = page.getByRole("button", { name: "Optimize 실행" });
    await expect(submitBtn).not.toBeDisabled();
    await submitBtn.click();

    // compare 페이지로 이동 확인
    await expect(page).toHaveURL(
      new RegExp(`/prompts/${PROMPT_ID}/compare`)
    );
    await expect(page).toHaveURL(new RegExp(`from=${PARENT_VERSION_ID}`));
    await expect(page).toHaveURL(new RegExp(`to=${NEW_VERSION_ID}`));
    await expect(page).toHaveURL(
      new RegExp(`optimization=${OPTIMIZATION_ID}`)
    );
  });

  test("AC-10(4): compare 페이지에 F02 자동 수정 결과 배지 표시", async ({
    page,
  }) => {
    await setupCommonRoutes(page);

    await page.goto(
      `/prompts/${PROMPT_ID}/compare?from=${PARENT_VERSION_ID}&to=${NEW_VERSION_ID}&optimization=${OPTIMIZATION_ID}`
    );

    // F02 배지 표시
    await expect(page.getByText("F02 자동 수정 결과")).toBeVisible({
      timeout: 5000,
    });

    // change_summary 표시
    await expect(
      page.getByText(/lighting 관련 추가 지시/)
    ).toBeVisible({ timeout: 5000 });
  });

  test("AC-10(5): succeeded=false → toast 에러 + 다이얼로그 유지", async ({
    page,
  }) => {
    await setupCommonRoutes(page);

    // Optimize endpoint stub (succeeded=false)
    await page.route(
      `**/api/prompts/${PROMPT_ID}/optimize`,
      async (route: Route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(OPTIMIZE_FAILURE_RESPONSE),
        });
      }
    );

    await page.goto(`/prompts/${PROMPT_ID}`);

    await page
      .getByRole("button", { name: "F02 Prompt Optimize 실행" })
      .click();

    const versionSelect = page.getByLabel("기준 버전 선택");
    await versionSelect.selectOption(PARENT_VERSION_ID);

    await page.getByLabel("수정 지침 입력").fill("수정 지침 텍스트");
    await page.getByRole("button", { name: "mood 차원 빠른 추가" }).click();

    await page.getByRole("button", { name: "Optimize 실행" }).click();

    // 다이얼로그 유지 확인 (compare로 이동 안됨)
    await expect(page).not.toHaveURL(/\/compare/);
    await expect(page.getByText("F02 Prompt Optimize")).toBeVisible();

    // failureReason 표시
    await expect(
      page.getByText(/PromptOptimizerInvalidOutputError/)
    ).toBeVisible({ timeout: 5000 });
  });

  test("AC-10(6): Mode A 탭 전환 → evaluation_id 입력 필드 + 안내 배지 표시", async ({
    page,
  }) => {
    await setupCommonRoutes(page);
    await page.goto(`/prompts/${PROMPT_ID}`);

    await page
      .getByRole("button", { name: "F02 Prompt Optimize 실행" })
      .click();

    await page
      .getByRole("tab", { name: "Mode A — evaluation 자동" })
      .click();

    await expect(
      page.getByRole("note", { name: "Mode A 안내" })
    ).toBeVisible();
    await expect(page.getByLabel("evaluation_id 입력")).toBeVisible();
  });

  test("AC-10(7): OptimizationHistoryPanel — 이력이 있을 때 성공/실패 배지 표시", async ({
    page,
  }) => {
    await setupCommonRoutes(page);
    await page.goto(`/prompts/${PROMPT_ID}`);

    // F02 이력 섹션 표시 확인
    await expect(page.getByText("F02 이력")).toBeVisible({ timeout: 5000 });

    // succeeded=true 배지
    await expect(page.getByText("성공")).toBeVisible({ timeout: 5000 });
  });
});
