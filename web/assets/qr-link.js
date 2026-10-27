(function (root) {
  "use strict";
  function localVideoLink(value) {
    var url;
    try { url = new URL(String(value).trim()); } catch (_) { throw new Error("Der QR-Code enthält keinen vollständigen Video-Link."); }
    if ((url.protocol !== "https:" && url.protocol !== "http:") || url.username || url.password || url.port ||
        (url.hostname !== "video.gaestebuch.cloud" && url.hostname !== "192.168.4.1")) {
      throw new Error("Dieser QR-Code gehört nicht zum Video-Gästebuch.");
    }
    var parts = url.pathname.match(/^\/v\/([^/]+)\/([^/]+\.mp4)$/i);
    if (!parts) throw new Error("Der QR-Code enthält keinen passenden Video-Link.");
    var event, file;
    try { event = decodeURIComponent(parts[1]); file = decodeURIComponent(parts[2]); }
    catch (_) { throw new Error("Der Video-Link ist beschädigt."); }
    if ([event, file].some(function (part) { return part === "." || part === ".." || /[\/\\\u0000-\u001f\u007f]/.test(part); })) {
      throw new Error("Der Video-Link ist ungültig.");
    }
    var path = encodeURIComponent(event) + "/" + encodeURIComponent(file);
    return { player: "/v/" + path, media: "/media/" + path };
  }
  root.TokenQr = { localVideoLink: localVideoLink };
  if (typeof module !== "undefined" && module.exports) module.exports = root.TokenQr;
})(typeof window !== "undefined" ? window : globalThis);