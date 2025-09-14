# HTTPS Development Setup Guide

This guide shows you how to set up HTTPS for local development using `mkcert` to create locally-trusted SSL certificates.

## 🚀 Quick Start

If you just want to get HTTPS running quickly:

```bash
make dev-https
```

This command will automatically:
- Check if mkcert is installed (with installation instructions if needed)
- Generate SSL certificates if they don't exist
- Start the HTTPS development server on https://localhost:8443

## 📋 Step-by-Step Setup

### 1️⃣ Install mkcert

mkcert is a tool that creates locally-trusted development certificates without requiring configuration.

**macOS:**
```bash
brew install mkcert
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install libnss3-tools
wget -O mkcert https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-v*-linux-amd64
chmod +x mkcert && sudo mv mkcert /usr/local/bin/
```

**Windows:**
```bash
choco install mkcert
```

Or download directly from the [mkcert releases page](https://github.com/FiloSottile/mkcert/releases).

### 2️⃣ Generate SSL Certificates

```bash
make dev-certs
```

This will:
- Install the local Certificate Authority (CA) in your system trust stores
- Generate SSL certificates for localhost and common development domains
- Set appropriate file permissions

### 3️⃣ Start HTTPS Development Server

```bash
make dev-https
```

The server will start on https://localhost:8443 with:
- Hot reload enabled
- No browser security warnings
- Automatic certificate trust across all browsers

## 🌐 Access Your Application

Once the server is running, you can access:

- **Main Server**: https://localhost:8443
- **API Documentation**: https://localhost:8443/docs
- **OpenAPI Specification**: https://localhost:8443/openapi.json

## ✨ Why Use HTTPS in Development?

### Production Parity
Match your production environment to catch issues early.

### Modern Browser Features
Many browser APIs require HTTPS:
- Camera and microphone access
- Geolocation API
- Push notifications
- Service workers
- Secure storage APIs

### Security Testing
Test authentication flows and secure cookie behavior in a realistic environment.

### Service Worker Development
Service workers require HTTPS (except on localhost), making HTTPS essential for PWA development.

### No Browser Warnings
mkcert eliminates the need to accept self-signed certificate warnings in your browser.

## 🛠️ Troubleshooting

### Check Certificate Status
```bash
make dev-certs-trust
```

This command will:
- Verify mkcert is installed and configured
- Check if certificates exist and are valid
- Show troubleshooting tips

### Regenerate Certificates
```bash
make dev-certs-force
```

This will delete existing certificates and generate new ones.

### View All Development Commands
```bash
make help | grep dev
```

### Enable Verbose Logging
```bash
make dev-https VERBOSE=1
```

### Browser Still Shows Warnings?

1. **Restart your browser** after installing certificates
2. **Corporate networks** may require additional configuration
3. **Firefox users**: mkcert automatically installs certificates for Firefox
4. **Clear browser cache** if you previously visited with self-signed certificates

### Remove mkcert (if needed)
```bash
mkcert -uninstall
```

This removes the local CA from your system trust stores.

## 🔄 Development Options

| Command | Protocol | Port | Description |
|---------|----------|------|-------------|
| `make dev` | HTTP | 8000 | Standard development server |
| `make dev-https` | HTTPS | 8443 | HTTPS development server with SSL |

Both servers support:
- Hot reload on file changes
- Verbose logging with `VERBOSE=1`
- FastAPI automatic documentation

## 📁 Certificate Files

Certificates are stored in the `certs/` directory:

- `certs/localhost.crt` - SSL certificate
- `certs/localhost.key` - Private key

These files are:
- Valid for 2+ years
- Automatically trusted by your system
- Excluded from version control (`.gitignore`)

## 🔒 Certificate Details

The generated certificates include these domains:
- `localhost`
- `127.0.0.1`
- `::1` (IPv6 localhost)
- `*.localhost` (wildcard for subdomains)

## 📚 Additional Resources

- **mkcert GitHub**: https://github.com/FiloSottile/mkcert
- **FastAPI HTTPS Documentation**: https://fastapi.tiangolo.com/deployment/https/
- **uvicorn SSL Documentation**: https://www.uvicorn.org/#running-with-https
- **Mozilla Web Security Guidelines**: https://wiki.mozilla.org/Security/Guidelines/Web_Security

## 💡 Tips

- **Use HTTPS by default** in development to match production
- **Keep certificates updated** - they expire after 2+ years
- **Test with different browsers** to ensure compatibility
- **Use the same port consistently** to avoid bookmark issues
- **Consider HTTPS redirects** in your application for production parity

---

For more development commands and options, run:
```bash
make help
```