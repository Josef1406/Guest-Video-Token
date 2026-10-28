<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

- Keep Raspberry Pi guest pages as offline static assets in `web/`; nginx serves them independently of the Lovable preview.
- Decode QR photos with the vendored jsQR library and validate video URLs in `web/assets/qr-link.js`; keep its local-path rules covered by adjacent Node tests to avoid external redirects.
- Store video-link selection separately from AP/client boot state in the Pi service; this prevents boot and installer operations from resetting guest URL preferences.
- Keep certificate private keys on each Pi and transport only CSRs and public chains; renewal must stay unavailable until a domain-authorized issuer and verified activation exist.
- Render the offline welcome page in an explicitly disconnected iframe preview; the hosted preview must never pretend to control the real Pi.
