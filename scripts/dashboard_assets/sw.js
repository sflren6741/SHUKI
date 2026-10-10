/* Push-only worker: no dashboard/API caching. */
'use strict';
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));

function safeDestination(path) {
  const url = new URL(path || '/notifications', self.location.origin);
  return url.origin === self.location.origin && ['/', '/notifications', '/settings'].includes(url.pathname)
    ? url.href : self.location.origin + '/notifications';
}

self.addEventListener('push', event => {
  let message = {};
  try { message = event.data ? event.data.json() : {}; } catch (_) { /* Show a usable default. */ }
  if (!message || typeof message !== 'object') message = {};
  const choices = Array.isArray(message.choices) ? message.choices : [];
  const options = {
    body: String(message.body || 'Open SHUKI to see the update.'),
    icon: '/icon-192.png', tag: String(message.tag || 'shuki-notice'),
    data: {url: safeDestination(message.url)},
  };
  // All reply choices remain in the conversation; OS action limits cannot lose a choice.
  if (choices.length) options.actions = [{action: 'reply', title: 'View reply choices'}];
  event.waitUntil(self.registration.showNotification(String(message.title || 'SHUKI'), options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil((async () => {
    const url = safeDestination(event.notification.data && event.notification.data.url);
    const windows = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
    const existing = windows.find(client => client.url === url);
    if (existing) return existing.focus();
    // Do not navigate an unrelated conversation or discard its unsent input.
    return self.clients.openWindow(url);
  })());
});
