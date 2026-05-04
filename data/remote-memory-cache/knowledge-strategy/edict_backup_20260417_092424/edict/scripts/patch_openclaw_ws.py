#!/usr/bin/env python3
"""
Patch OpenClaw gateway-cli bundle to fix WebSocket ERR_CONNECTION_RESET (794).
Root cause: canvasHost closes WebSocket with code 1000, then immediately calls
socket.destroy() → TCP RST sent before browser can ack the close frame.
Fix: wrap socket.destroy() in the upgrade handler with a drain delay (~50ms),
     giving the TCP close handshake time to complete gracefully.
Run once after each `openclaw` upgrade.
"""
import re, sys
from pathlib import Path

SRC = Path("/opt/homebrew/lib/node_modules/openclaw/dist/gateway-cli-CuZs0RlJ.js")
BACKUP = SRC.with_suffix(".js.bak")

src = SRC.read_text()

if "_WS_DRAIN_PATCH" in src:
    print("Already patched, skipping.")
    sys.exit(0)

# Backup
BACKUP.write_bytes(SRC.read_bytes())
print(f"Backed up to {BACKUP}")

# The patch: inject a drain wrapper at the start of attachGatewayUpgradeHandler
# that makes socket.destroy() wait 50ms before actually destroying.
# This ensures TCP FIN/ACK completes before RST is sent.
drain_patch = """
// [TianFu WS Drain Patch] Prevent ERR_CONNECTION_RESET (794) by draining socket before destroy
function _wsDrainDestroy(s) { const orig = s.destroy.bind(s); let drained = false; s.destroy = function() { if (!drained) { drained = true; setTimeout(orig, 50); return; } return orig.apply(this, arguments); }; }
// [TianFu WS Drain Patch]
"""

# Find the function signature and inject the patch after it
target = "function attachGatewayUpgradeHandler(opts) {"
if target not in src:
    print("ERROR: attachGatewayUpgradeHandler not found")
    sys.exit(1)

# Inject after the function opening brace
src = src.replace(target, target + "\n" + drain_patch, 1)
print("Injected drain wrapper after attachGatewayUpgradeHandler")

# Now find the `httpServer.on("upgrade"` block and add the drain wrapper call
# Pattern: httpServer.on("upgrade", (req, socket, head) => {
target2 = 'httpServer.on("upgrade", (req, socket, head) => {'
if target2 not in src:
    print("ERROR: httpServer upgrade handler not found")
    sys.exit(1)

src = src.replace(target2, target2 + '\n\t\t_wsDrainDestroy(socket);', 1)
print("Added _wsDrainDestroy call after httpServer.on('upgrade')")

# Verify the patch was applied
if "_wsDrainDestroy" in src and "_WS_DRAIN_PATCH" not in src:
    # Mark as patched
    src = src.replace('// [TianFu WS Drain Patch]', '// [TianFu WS Drain Patch] _WS_DRAIN_PATCH')
    SRC.write_text(src)
    print(f"Patched successfully: {SRC}")
    print("\nRestart the OpenClaw gateway with: openclaw gateway restart")
    print("Or: kill the gateway PID and start again.")
else:
    print("Patch application uncertain, please verify manually.")
    sys.exit(1)
