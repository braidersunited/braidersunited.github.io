# Braiders United: Russian copy

Static copy of https://braidersunited.com/ru/ for visitors from Russia, where Cloudflare is restricted.
Operator: Dream braids s.r.o. Privacy notice: https://braidersunited.github.io/ru/privacy.html

This repository holds code only. Every hour a GitHub Action (`postav.py`) downloads the public cards
from braidersunited.com, builds the static page and deploys it as a Pages artifact. No card data is
ever committed here, so a deleted card disappears from the copy within an hour.
