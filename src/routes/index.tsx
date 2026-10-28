import { createFileRoute } from "@tanstack/react-router";
import welcomeHtml from "../../web/index.html?raw";
import welcomeCss from "../../web/assets/welcome.css?raw";
import welcomeJs from "../../web/assets/welcome.js?raw";

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

const previewDocument = welcomeHtml
  .replace('<html lang="de">', '<html lang="de" data-preview="true">')
  .replace('<link rel="stylesheet" href="/assets/welcome.css" />', `<style>${welcomeCss}</style>`)
  .replace('<script src="/assets/certificate-bridge.js"></script>', '')
  .replace('<script src="/assets/welcome.js"></script>', `<script>${welcomeJs}</script>`);

function Index() {
  return (
    <iframe title="Video_GB Gäste-Startseite – Vorschau ohne Pi-Verbindung" srcDoc={previewDocument}
      sandbox="allow-scripts" className="block h-dvh min-h-[700px] w-full border-0 bg-background" />
  );
}
