(function () {
  var q = new URLSearchParams(location.search);
  var ev = q.get("e");
  var fn = q.get("f");
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

  document.getElementById("meta").textContent = ev + " · " + fn;
  document.title = fn;
})();
