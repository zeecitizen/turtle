/* Turtle Trader dashboard service worker — push notifications with action buttons.
   Served from /sw.js (root scope) so it controls / and /grab.
   Push payload (JSON): { title, body, tag, grabUrl, requireInteraction, actions } */

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; }
  catch (_) { data = { body: event.data ? event.data.text() : '' }; }

  const options = {
    body: data.body || '',
    tag: data.tag || 'profit-pulse',
    renotify: true,
    requireInteraction: data.requireInteraction !== false,  // stay until acted on
    icon: '/icon.svg',
    badge: '/icon.svg',
    vibrate: [90, 40, 90, 40, 90],
    data: { grabUrl: data.grabUrl || '', url: data.url || '/' },
    actions: data.actions || [
      { action: 'grab', title: '🫡 Grab it' },
      { action: 'ride', title: 'Let it ride' }
    ]
  };
  event.waitUntil(self.registration.showNotification(data.title || 'Turtle Trader', options));
});

self.addEventListener('notificationclick', (event) => {
  const d = event.notification.data || {};
  event.notification.close();

  if (event.action === 'ride') return;   // just dismiss — let it ride

  if (event.action === 'grab' && d.grabUrl) {
    event.waitUntil(
      fetch(d.grabUrl)
        .then(() => self.registration.showNotification('🫡 Grab sent', {
          body: 'Closing all open positions at market.', tag: 'profit-pulse', icon: '/icon.svg'
        }))
        .catch(() => self.clients.openWindow(d.grabUrl))   // fallback: open the link
    );
    return;
  }

  // default body tap → focus or open the dashboard
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const w of wins) { if ('focus' in w) return w.focus(); }
      return self.clients.openWindow(d.url || '/');
    })
  );
});
