Status: Draft — do not post automatically

---
title: "Building a small inbound-only WhatsApp Cloud API bridge"
published: false
tags: python, docker, webhooks, selfhosted
---

This is a technical write-up draft, not a launch post.

The project receives Meta WhatsApp Cloud API webhook events, validates the raw request body with HMAC-SHA256 before JSON parsing, normalizes inbound message events, and appends them to local JSONL.

The trade-off is scope. It does not send WhatsApp messages, download media bytes, provide a UI, or become a chatbot framework. Optional examples read the JSONL file and send periodic summaries to Telegram or Discord.

The most useful design decision was splitting the code into three testable parts: HTTP/config/lifecycle, pure webhook parsing/signature validation, and durable JSONL storage.

Repo link goes here after the technical article is reviewed.
