/**
 * Keith Enterprises — Lightweight WhatsApp Bridge
 *
 * A minimal Express server that wraps Baileys (WhatsApp Web library).
 * Provides REST endpoints for the Dash dashboard to:
 *   - Get QR code for linking personal WhatsApp
 *   - Receive incoming messages (forwarded to dashboard webhook)
 *   - Send messages
 *
 * Usage:
 *   npm install && npm start
 *   (or via Docker: docker compose -f docker-compose.whatsapp.yml up -d)
 */

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
} = require("baileys");
const express = require("express");
const QRCode = require("qrcode");
const pino = require("pino");
const fs = require("fs");
const path = require("path");

const PORT = process.env.BRIDGE_PORT || 8085;
const WEBHOOK_URL =
  process.env.WEBHOOK_URL || "http://localhost:8080/api/whatsapp/webhook";
const AUTH_DIR = process.env.AUTH_DIR || path.join(__dirname, "auth_state");
const MEDIA_DIR = process.env.MEDIA_DIR || path.join(__dirname, "media");
const API_KEY = process.env.API_KEY || "keith-enterprises-wa-key";

const logger = pino({ level: "warn" });
const app = express();
app.use(express.json({ limit: "50mb" }));

// State
let sock = null;
let qrCode = null; // base64 PNG of QR code
let qrRaw = null; // raw QR string
let connectionState = "disconnected"; // disconnected | connecting | connected
let connectedPhone = "";

// ── Auth middleware ──
function authMiddleware(req, res, next) {
  const key = req.headers["apikey"] || req.query.apikey;
  if (key !== API_KEY) {
    return res.status(401).json({ error: "Invalid API key" });
  }
  next();
}
app.use(authMiddleware);

// ── WhatsApp Connection ──
async function startWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    logger,
    printQRInTerminal: false,
    generateHighQualityLinkPreview: false,
    syncFullHistory: false,
    shouldSyncHistoryMessage: () => false,
    fireInitQueries: false,
  });

  // Handle connection updates
  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      // Generate QR code as base64 PNG
      qrRaw = qr;
      connectionState = "connecting";
      try {
        qrCode = await QRCode.toDataURL(qr, { width: 300, margin: 2 });
        console.log("[WhatsApp] QR code generated — scan with your phone");
      } catch (err) {
        console.error("[WhatsApp] QR generation error:", err);
      }
    }

    if (connection === "close") {
      const statusCode =
        lastDisconnect?.error?.output?.statusCode ||
        lastDisconnect?.error?.output?.payload?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

      console.log(
        `[WhatsApp] Connection closed. Status: ${statusCode}. Reconnect: ${shouldReconnect}`
      );

      connectionState = "disconnected";
      qrCode = null;
      qrRaw = null;
      connectedPhone = "";

      if (shouldReconnect) {
        console.log("[WhatsApp] Reconnecting in 3 seconds...");
        setTimeout(startWhatsApp, 3000);
      } else {
        // Logged out — clear auth state
        console.log(
          "[WhatsApp] Logged out. Clear auth state and restart to re-link."
        );
        try {
          fs.rmSync(AUTH_DIR, { recursive: true, force: true });
        } catch (e) {}
      }
    }

    if (connection === "open") {
      connectionState = "connected";
      qrCode = null;
      qrRaw = null;
      connectedPhone = sock.user?.id?.split(":")[0] || "";
      console.log(`[WhatsApp] Connected! Phone: ${connectedPhone}`);
    }
  });

  // Save credentials on update
  sock.ev.on("creds.update", saveCreds);

  // Handle incoming messages
  sock.ev.on("messages.upsert", async (upsert) => {
    const messages = upsert.messages || upsert;
    const type = upsert.type || "notify";

    console.log(`[WhatsApp] messages.upsert: type=${type}, count=${Array.isArray(messages) ? messages.length : '?'}`);

    for (const msg of (Array.isArray(messages) ? messages : [])) {
      // Skip our own messages
      if (msg.key.fromMe) {
        console.log(`[WhatsApp] Skipping own message: ${msg.key.id}`);
        continue;
      }

      console.log(`[WhatsApp] Incoming message from ${msg.key.remoteJid}: ${JSON.stringify(msg.message || {}).substring(0, 100)}`);

      // Forward to dashboard webhook
      try {
        const payload = {
          event: "messages.upsert",
          instance: "keith-wa",
          data: {
            key: msg.key,
            message: msg.message,
            messageTimestamp: msg.messageTimestamp,
            pushName: msg.pushName || "",
          },
        };

        // Download media if present and attach as base64
        const mediaTypes = [
          "imageMessage",
          "documentMessage",
          "videoMessage",
          "audioMessage",
          "stickerMessage",
        ];
        const msgContent = msg.message || {};
        let mediaType = mediaTypes.find((t) => msgContent[t]);

        if (mediaType && sock) {
          try {
            const { downloadMediaMessage } = require("baileys");
            const buffer = await downloadMediaMessage(msg, "buffer", {}, {
              logger,
              reuploadRequest: sock.updateMediaMessage,
            });
            if (buffer) {
              // Save to media dir
              fs.mkdirSync(MEDIA_DIR, { recursive: true });
              const ext = getExtension(msgContent[mediaType]?.mimetype);
              const filename = `wa_${Date.now()}.${ext}`;
              const filepath = path.join(MEDIA_DIR, filename);
              fs.writeFileSync(filepath, buffer);

              // Add file path to payload for the Python side to pick up
              payload.data._mediaFile = filepath;
              payload.data._mediaFilename = filename;
            }
          } catch (dlErr) {
            console.error("[WhatsApp] Media download error:", dlErr.message);
          }
        }

        await fetch(WEBHOOK_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } catch (err) {
        console.error("[WhatsApp] Webhook forward error:", err.message);
      }
    }
  });
}

function getExtension(mimetype) {
  const map = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "video/mp4": "mp4",
    "audio/ogg; codecs=opus": "ogg",
    "audio/mpeg": "mp3",
    "application/pdf": "pdf",
  };
  return map[mimetype] || "bin";
}

// ── REST API ──

// Health / status
app.get("/status", (req, res) => {
  res.json({
    state: connectionState,
    phone: connectedPhone,
    hasQR: !!qrCode,
  });
});

// Get QR code
app.get("/qr", (req, res) => {
  if (connectionState === "connected") {
    return res.json({ connected: true, phone: connectedPhone });
  }
  if (qrCode) {
    return res.json({ qr: qrCode, raw: qrRaw });
  }
  return res.json({ waiting: true, state: connectionState });
});

// Send text message
app.post("/send", async (req, res) => {
  if (!sock || connectionState !== "connected") {
    return res
      .status(503)
      .json({ error: "WhatsApp not connected", state: connectionState });
  }

  const { to, message } = req.body;
  if (!to || !message) {
    return res.status(400).json({ error: "Missing 'to' or 'message'" });
  }

  // Format number: strip +, spaces, dashes
  const jid =
    to.replace(/[^0-9]/g, "") + "@s.whatsapp.net";

  try {
    const result = await sock.sendMessage(jid, { text: message });
    res.json({ success: true, id: result.key.id });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Send image
app.post("/send-image", async (req, res) => {
  if (!sock || connectionState !== "connected") {
    return res
      .status(503)
      .json({ error: "WhatsApp not connected", state: connectionState });
  }

  const { to, imageUrl, caption } = req.body;
  if (!to || !imageUrl) {
    return res.status(400).json({ error: "Missing 'to' or 'imageUrl'" });
  }

  const jid = to.replace(/[^0-9]/g, "") + "@s.whatsapp.net";

  try {
    const result = await sock.sendMessage(jid, {
      image: { url: imageUrl },
      caption: caption || "",
    });
    res.json({ success: true, id: result.key.id });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Disconnect / logout
app.post("/logout", async (req, res) => {
  if (sock) {
    try {
      await sock.logout();
    } catch (e) {}
  }
  res.json({ success: true });
});

// Restart connection
app.post("/restart", async (req, res) => {
  if (sock) {
    try {
      sock.end();
    } catch (e) {}
  }
  setTimeout(startWhatsApp, 1000);
  res.json({ success: true, message: "Restarting..." });
});

// ── Start ──
app.listen(PORT, () => {
  console.log(`[Bridge] WhatsApp bridge running on port ${PORT}`);
  startWhatsApp();
});
