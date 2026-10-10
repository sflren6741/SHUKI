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
    data: {url: safeDestination(message.url), token: message.replyToken || '',
      tag: String(message.tag || 'shuki-notice')},
  };
  const capacity = typeof Notification !== 'undefined' && Number.isInteger(Notification.maxActions)
    ? Notification.maxActions : 2;
  if (choices.length && options.data.token) {
    options.actions = choices.slice(0, capacity).map((label, index) =>
      ({action: 'choice-' + index, title: String(label)}));
    if (choices.length > capacity) options.body += '\nOpen this notification for all reply choices.';
  } else if (message.hasChoices || choices.length) {
    options.actions = [{action: 'reply', title: 'View reply choices'}].slice(0, capacity);
  }
  event.waitUntil(self.registration.showNotification(String(message.title || 'SHUKI'), options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil((async () => {
    const url = safeDestination(event.notification.data && event.notification.data.url);
    const match = /^choice-([0-2])$/.exec(event.action || '');
    const data = event.notification.data || {};
    if (match && data.token) {
      let received = false;
      let duplicate = false;
      try {
        const response = await fetch('/push/reply', {
          method: 'POST', credentials: 'same-origin', redirect: 'error',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({token: data.token, index: Number(match[1])}),
          signal: AbortSignal.timeout(10000),
        });
        const result = await response.json();
        received = response.ok && result.ok === true;
        duplicate = result.duplicate === true;
      } catch (_) { /* Never retry an uncertain submission automatically. */ }
      await self.registration.showNotification(received ? 'Reply received' : 'Check your reply in SHUKI', {
        body: received ? (duplicate ? 'This reply was already received.' : 'Your conversation is continuing.')
          : 'The reply could not be confirmed. Open the conversation before trying again.',
        icon: '/icon-192.png', tag: data.tag, data: {url},
      });
      return;
    }
    const windows = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
    const existing = windows.find(client => client.url === url);
    if (existing) return existing.focus();
    // Do not navigate an unrelated conversation or discard its unsent input.
    return self.clients.openWindow(url);
  })());
});
