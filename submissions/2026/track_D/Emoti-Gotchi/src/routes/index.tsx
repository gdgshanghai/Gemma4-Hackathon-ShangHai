import { createFileRoute } from "@tanstack/react-router";
import EmotiGotchiDashboard from "@/components/emoti-gotchi/EmotiGotchiDashboard";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Emoti-Gotchi | Privacy-First Edge Emotional Support" },
      {
        name: "description",
        content:
          "A privacy-first edge emotional support system for children, using Gemma 4 for structured understanding, realtime edge response, and parent-facing review.",
      },
      { property: "og:title", content: "Emoti-Gotchi | Privacy-First Edge Emotional Support" },
      {
        property: "og:description",
        content:
          "Gemma 4 structured reasoning for child-safe realtime support and parent-facing emotional review.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  return <EmotiGotchiDashboard />;
}
