# Yearly Yields — Frontend

Angular v21 + Angular Material

## Structure

See architecture plan — features are lazy-loaded modules under `src/app/features/`.
NgRx used only for `auth` and `alerts` global state.

## Requirements

- Node.js 18+ (LTS recommended)

## First-time setup

### 1. Install dependencies

From `frontend/yearly-yields-ui/`:

```bash
cd frontend/yearly-yields-ui
npm install
```

### 2. SSL certificates (local HTTPS)

This project uses mkcert-generated certificates for local HTTPS
(`localhost+1.pem` / `localhost+1-key.pem`). These are **gitignored** —
every machine needs to generate its own.

1. Install mkcert: https://github.com/FiloSottile/mkcert
2. Install the local CA (one-time per machine):
```bash
   mkcert -install
```
3. Generate the certs for this project (from `frontend/yearly-yields-ui/`):
```bash
   mkcert localhost 127.0.0.1
```
   This produces `localhost+1.pem` and `localhost+1-key.pem` in the current
   directory, matching the filenames already referenced in this project's
   dev server config.

**Common gotchas:**
- If the browser still shows an untrusted-certificate warning after this,
  restart the browser — `mkcert -install` requires a restart to pick up
  the new trust store entry.
- If `mkcert -install` silently fails to register a browser's trust store
  (notably Firefox, which uses its own store instead of the OS one), you
  may need `certutil`/`libnss3-tools` installed first — see the mkcert
  README for your OS.
- Filenames matter: `mkcert localhost 127.0.0.1` (2 names) produces
  `localhost+1.*`. Passing a different number/order of hostnames will
  produce differently-named files and break the config reference.
- These certs are not permanent. The certs currently in this project were
  generated for ~5-year validity, so expiration isn't an immediate concern —
  but if HTTPS suddenly stops trusting after a long gap without touching
  this project, check the cert's expiration before assuming it's a config
  issue:
```bash
  openssl x509 -enddate -noout -in localhost+1.pem
```

### 3. Start the dev server

```bash
npm start
```

Frontend is available at: http://localhost:4200
(check `proxy.conf.json` / `angular.json` if a different port or HTTPS is configured)

> ⚠️ The backend must be running (see backend README) for API calls to succeed.

## Restarting the dev server

Once first-time setup is done, subsequent restarts only need:

### 1. Confirm you're in the right folder

```bash
cd frontend/yearly-yields-ui
```

### 2. Start the server

```bash
npm start
```

## Stopping the dev server

Press **Ctrl+C** in the terminal running `npm start`.

## Project origin

This project was originally scaffolded with:

```bash
ng new yearly-yields-ui --routing --style=scss --standalone
ng add @angular/material
npm install @ngrx/store @ngrx/effects @ngrx/entity @ngrx/router-store @ngrx/store-devtools
```

These commands are historical — **do not re-run `ng new` in this folder**;
it will conflict with existing project files. This section is kept for
reference only.