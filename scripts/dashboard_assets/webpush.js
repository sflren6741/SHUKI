'use strict';
(() => {
  let cfg, registration, device;
  const byId = id => document.getElementById(id);
  const supported = () => window.isSecureContext && 'serviceWorker' in navigator &&
    'PushManager' in window && 'Notification' in window;
  const status = text => { if (byId('push-status')) byId('push-status').textContent = text; };
  async function api(path, data) {
    const options = data === undefined ? {} : {method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-SHUKI-Push': cfg.csrf}, body: JSON.stringify(data)};
    const response = await fetch('/push/' + path, {...options, cache: 'no-store'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Notification request failed.');
    return result;
  }
  function buttons() {
    if (!byId('push-settings')) return;
    byId('push-enable').disabled = !registration;
    byId('push-test').disabled = !device;
    byId('push-switch').disabled = !device || !device.tested;
    byId('push-disable').disabled = !device;
    byId('push-ntfy').disabled = !cfg;
    byId('push-retry').disabled = !cfg;
  }
  async function syncSubscription() {
    if (!registration || Notification.permission !== 'granted') return;
    const sub = await registration.pushManager.getSubscription();
    if (sub) {
      const key = sub.options.applicationServerKey;
      if (key && btoa(String.fromCharCode(...new Uint8Array(key))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '') !== cfg.public_key)
        throw new Error('Registration key changed. Disable this device, then enable it again.');
      device = await api('subscribe', {subscription: sub.toJSON()});
    }
  }
  async function enable() {
    // Invoke directly in the click handler to retain the user gesture.
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') throw new Error('Notifications are blocked. Allow them in browser or Android settings, then try again.');
    const base64 = cfg.public_key.replace(/-/g, '+').replace(/_/g, '/');
    const key = Uint8Array.from(atob(base64 + '='.repeat((4 - base64.length % 4) % 4)), c => c.charCodeAt(0));
    let sub = await registration.pushManager.getSubscription();
    if (!sub) sub = await registration.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: key});
    device = await api('subscribe', {subscription: sub.toJSON()});
    status('This device is enabled. Send a test; delivery still uses ' + cfg.channel + '.');
  }
  async function disable() {
    const sub = registration && await registration.pushManager.getSubscription();
    // Remove the durable server subscription before clearing the browser's copy.
    if (device) await api('unsubscribe', {id: device.id});
    else if (sub) {
      const registered = await api('subscribe', {subscription: sub.toJSON()});
      await api('unsubscribe', {id: registered.id});
    }
    if (sub && !(await sub.unsubscribe())) throw new Error('Browser could not unsubscribe; try again.');
    device = null;
    status('This device is disabled. Use ntfy if it was your last SHUKI device.');
  }
  async function init() {
    try {
      cfg = await api('config');
      if (!cfg.configured) { status('SHUKI push is not configured on this server.'); return; }
      if (cfg.origin !== location.origin) {
        status('Open Settings at ' + cfg.origin + ' to enable phone notifications.');
        return;
      }
      if (!supported()) { status('Use a supported browser over HTTPS to enable notifications.'); return; }
      registration = await navigator.serviceWorker.register('/sw.js', {scope: '/', updateViaCache: 'none'});
      registration = await navigator.serviceWorker.ready;
      await syncSubscription();
      status('Delivery: ' + (cfg.channel === 'webpush' ? 'SHUKI' : 'ntfy') + '. ' +
        (device ? 'This device is enabled.' : 'Enable this device to begin.'));
    } catch (error) { status(error.message); }
    finally { buttons(); }
  }
  function bind(id, action) {
    const button = byId(id);
    if (!button) return;
    button.addEventListener('click', async () => {
      button.disabled = true;
      try { await action(); } catch (error) { status(error.message); }
      finally { buttons(); }
    });
  }
  async function start() {
    bind('push-enable', enable);
    bind('push-test', async () => {
      await api('test', {id: device.id}); device.tested = true;
      status('Test accepted by the push service. After it arrives on this phone, choose Use SHUKI notifications.');
    });
    bind('push-switch', async () => {
      await api('channel', {channel: 'webpush', id: device.id}); cfg.channel = 'webpush';
      status('SHUKI now delivers notifications. Tap to open the relevant conversation.');
    });
    bind('push-ntfy', async () => {
      await api('channel', {channel: 'ntfy'}); cfg.channel = 'ntfy'; status('Delivery switched to ntfy.');
    });
    bind('push-disable', disable);
    bind('push-retry', async () => {
      await api('retry', {}); status('Pending notices retried. Push acceptance does not confirm receipt.');
    });
    // Avoid registration on plain HTTP/unsupported browsers; Settings still explains how to proceed.
    if (supported() || byId('push-settings')) await init();
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && registration && Notification.permission === 'granted')
        syncSubscription().then(buttons).catch(error => status(error.message));
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
