(function () {
  "use strict";
  var photo = document.getElementById("qr-photo");
  var status = document.getElementById("scan-status");
  var form = document.getElementById("link-form");
  var busy = false;
  function message(text) { status.textContent = text; }
  function setBusy(value) {
    busy = value;
    document.getElementById("take-photo").disabled = value;
    form.querySelector("button").disabled = value;
    status.setAttribute("aria-busy", String(value));
  }
  async function openVideo(value) {
    var link = window.TokenQr.localVideoLink(value);
    message("Video wird auf dem Token gesucht …");
    var controller = new AbortController();
    var timeout = setTimeout(function () { controller.abort(); }, 12000);
    var response;
    try { response = await fetch(link.media, { method: "HEAD", cache: "no-store", signal: controller.signal }); }
    catch (_) { throw new Error("Der Token ist nicht erreichbar. Bitte bleibe im WLAN Video_GB und versuche es erneut."); }
    finally { clearTimeout(timeout); }
    if (!response.ok || !(response.headers.get("content-type") || "").toLowerCase().startsWith("video/mp4")) {
      throw new Error("Dieses Video ist noch nicht auf dem Token vorhanden. Bitte frage den Veranstalter.");
    }
    window.location.assign(link.player);
  }
  document.getElementById("take-photo").addEventListener("click", function () { photo.click(); });
  photo.addEventListener("change", async function () {
    var file = photo.files && photo.files[0];
    if (!file || busy) return;
    setBusy(true);
    message("QR-Foto wird gelesen …");
    var objectUrl = URL.createObjectURL(file);
    try {
      var image = new Image();
      await new Promise(function (resolve, reject) {
        image.onload = resolve;
        image.onerror = function () { reject(new Error("Das Foto konnte nicht geöffnet werden. Bitte verwende ein JPEG- oder PNG-Foto.")); };
        image.src = objectUrl;
      });
      var canvas = document.createElement("canvas");
      var ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx || !image.naturalWidth) throw new Error("Das Foto konnte nicht gelesen werden.");
      if (typeof window.jsQR !== "function") throw new Error("Der QR-Leser fehlt. Bitte lasse die Token-Seiten aktualisieren.");
      var code;
      for (var limit of [1800, 2600, 1000]) {
        var scale = Math.min(1, limit / Math.max(image.naturalWidth, image.naturalHeight));
        canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
        canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
        var pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
        code = window.jsQR(pixels.data, pixels.width, pixels.height, { inversionAttempts: "attemptBoth" });
        if (code) break;
      }
      if (!code) throw new Error("Kein QR-Code erkannt. Bitte fotografiere den ganzen QR-Code scharf und möglichst gerade.");
      await openVideo(code.data);
    } catch (error) { message(error.message || "Das Foto konnte nicht gelesen werden. Bitte versuche es erneut."); }
    finally { URL.revokeObjectURL(objectUrl); photo.value = ""; setBusy(false); }
  });
  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try { await openVideo(document.getElementById("video-link").value); }
    catch (error) { message(error.message || "Der Link konnte nicht geöffnet werden."); }
    finally { setBusy(false); }
  });
})();