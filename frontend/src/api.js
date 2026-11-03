/**
 * Where the backend lives.
 *
 * Empty by default, so requests go to the same origin as the page and the Vite
 * dev proxy (see vite.config.js) forwards them to the backend. That is what
 * makes `npm run dev -- --host` usable from a phone or another machine, where
 * a hard-coded "localhost" would point at that device instead of the server.
 *
 * Set VITE_API_BASE in frontend/.env to reach a backend on another origin, e.g.
 *   VITE_API_BASE=http://192.168.1.20:8000
 */
export const API_BASE = import.meta.env.VITE_API_BASE ?? ''
