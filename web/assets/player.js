(function () {
  var q = new URLSearchParams(location.search);
  var ev = q.get("e");
  var fn = q.get("f");
  // Fallback: Pfad /v/<event>/<file>.mp4 parsen (falls nginx-Rewrite den Query nicht durchreicht)
  if (!ev || !fn) {
    var m = location.pathname.match(/^\/v\/([^\/]+)\/([^\/]+\.mp4)$/i);
    if (m) {
      ev = decodeURIComponent(m[1]);
      fn = decodeURIComponent(m[2]);
    }
  }
  if (!ev || !fn) {
    document.getElementById("meta").textContent = "Ungültiger Link.";
    return;
  }
  var mediaUrl = "/media/" + encodeURIComponent(ev) + "/" + encodeURIComponent(fn);
  var absUrl = location.origin + mediaUrl;

  var player = document.getElementById("player");
  var src = document.createElement("source");
  src.src = mediaUrl;
  src.type = "video/mp4";
  player.appendChild(src);

  var dl = document.getElementById("dl");
  dl.href = mediaUrl;
  dl.setAttribute("download", fn);

  var wa = document.getElementById("wa");
  var text = "Mein Video vom Event: " + absUrl;
  wa.href = "https://wa.me/?text=" + encodeURIComponent(text);

  var shareBtn = document.getElementById("share");
  if (navigator.share) {
    shareBtn.hidden = false;
    shareBtn.addEventListener("click", async function () {
      try {
        // Versuche, die Datei selbst zu teilen (funktioniert offline im AP-Modus)
        if (navigator.canShare) {
          try {
            var res = await fetch(mediaUrl);
            var blob = await res.blob();
            var file = new File([blob], fn, { type: blob.type || "video/mp4" });
            if (navigator.canShare({ files: [file] })) {
              await navigator.share({ files: [file], title: fn });
              return;
            }
          } catch (_) { /* Fallback unten */ }
        }
        await navigator.share({ title: fn, text: "Mein Video vom Event", url: absUrl });
      } catch (_) { /* abgebrochen */ }
    });
  }

  document.getElementById("meta").textContent = ev + " · " + fn;
  document.title = fn;
})();
