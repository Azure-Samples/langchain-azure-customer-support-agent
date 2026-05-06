#!/bin/sh
# Minimal post-provision hook. The repo ships pre-generated data + embeddings,
# so there is nothing to seed. We just print the chat URL.
set -e

if [ -n "$CHAT_URL" ]; then
  echo ""
  echo "✅ Chat ready: $CHAT_URL"
  echo "   Run 'azd deploy chat' if you've changed app code."
fi
