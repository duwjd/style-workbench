import { createBrowserRouter, Navigate } from "react-router";
import { Layout } from "@/routes/_layout";
import StylesPage from "@/routes/styles/index";
import NewStylePage from "@/routes/styles/new";
import StyleBuilderPage from "@/routes/styles/$styleId";
import RunDetailPage from "@/routes/runs/$runId";
import PromptsPage from "@/routes/prompts/index";
import PromptDetailPage from "@/routes/prompts/$promptId";
import PromptComparePage from "@/routes/prompts/$promptId.compare";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/styles" replace /> },
      { path: "styles", element: <StylesPage /> },
      { path: "styles/new", element: <NewStylePage /> },
      { path: "styles/:styleId", element: <StyleBuilderPage /> },
      { path: "runs/:runId", element: <RunDetailPage /> },
      { path: "prompts", element: <PromptsPage /> },
      { path: "prompts/:promptId", element: <PromptDetailPage /> },
      { path: "prompts/:promptId/compare", element: <PromptComparePage /> },
    ],
  },
]);
