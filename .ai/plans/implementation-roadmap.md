# Implementation Roadmap

- [x] P0 repeated empty notifications — merged [PR #1](https://github.com/milan483/Youtube-Uploader/pull/1).
- [x] P1A recursive scanning and centralized archive — merged [PR #2](https://github.com/milan483/Youtube-Uploader/pull/2).
- [ ] P1B safe Uploaded Clips Manager — implementation in [PR #3](https://github.com/milan483/Youtube-Uploader/pull/3), Windows/Linux CI and review gate.
- [ ] P1C SSL EOF recovery, resumable retries and retry counters — implementation in [PR #4](https://github.com/milan483/Youtube-Uploader/pull/4), Windows/Linux CI and review gate.
- [ ] P1D Linux desktop integration — implementation in branch `feat/p1d-linux-desktop`, CI and KDE Wayland smoke pending. See [.ai/tasks/p1d-linux-desktop.md](../tasks/p1d-linux-desktop.md).

Merging remains under the user's explicit approval. Reconcile any conflicts between concurrent P1B/P1C/P1D branches before merging; source files were reviewed against the merged P1A main.
