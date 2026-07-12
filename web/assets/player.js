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

  var player = document.getElementById("player");
  var src = document.createElement("source");
  src.src = mediaUrl;
  src.type = "video/mp4";
  player.appendChild(src);

  var dl = document.getElementById("dl");
  dl.href = mediaUrl;
  dl.setAttribute("download", fn);

  document.getElementById("meta").textContent = ev + " · " + fn;
  document.title = fn;
})();
