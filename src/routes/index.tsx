import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [
    { title: "Guest Video Token – Raspberry Pi" },
    { name: "description", content: "Offline-Video-Token für Video-Gästebuch-Botschaften auf dem Raspberry Pi." },
    { property: "og:title", content: "Guest Video Token – Raspberry Pi" },
    { property: "og:description", content: "Video-Botschaften lokal ansehen und aufs Handy laden." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  component: Index,
});

// IMPORTANT: Replace this placeholder. See ./README.md for routing conventions.
function Index() {
  return (
    <div
      className="flex min-h-screen items-center justify-center"
      style={{ backgroundColor: "#fcfbf8" }}
    >
      <img
        data-lovable-blank-page-placeholder="REMOVE_THIS"
        src="https://cdn.gpteng.co/blank-app-v1.svg"
        alt="Your app will live here!"
      />
    </div>
  );
}
