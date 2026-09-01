const express = require('express');
const fetch = require('node-fetch');
const { nanoid } = require('nanoid');
const UAParser = require('ua-parser-js');
const db = require('./database');
const path = require('path');

const app = express();
app.use(express.json());
app.use(express.static('public'));

db.initDB().then(() => {
  const PORT = process.env.PORT || 3000;
  app.listen(PORT, () => {
    console.log(`✅ السيرفر شغّال على المنفذ ${PORT}`);
  });
}).catch(err => {
  console.error('❌ خطأ:', err);
  process.exit(1);
});

function encodeDomain(hostname) {
  return hostname.replace(/\./g, '-').replace(/\//g, '-');
}

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.post('/api/shorten', async (req, res) => {
  const { url, customAlias } = req.body;
  if (!url) return res.status(400).json({ error: 'الرابط مطلوب' });

  let parsedUrl;
  try { parsedUrl = new URL(url); } catch {
    return res.status(400).json({ error: 'رابط غير صالح' });
  }

  const encodedDomain = encodeDomain(parsedUrl.hostname);
  let shortCode = customAlias && customAlias.trim() !== '' 
    ? `${customAlias.trim().toLowerCase().replace(/\s+/g, '-')}-${encodedDomain}`
    : `${['go','link','v','r','to','at'][Math.floor(Math.random()*6)]}-${encodedDomain}`;

  const existing = db.get('SELECT id FROM links WHERE short_code = ?', [shortCode]);
  if (existing) shortCode = `${shortCode}-${Math.floor(Math.random() * 900) + 100}`;

  db.run('INSERT INTO links (short_code, original_url) VALUES (?, ?)', [shortCode, url]);

  res.json({
    shortUrl: `${req.protocol}://${req.get('host')}/${shortCode}`,
    shortCode, originalUrl: url
  });
});

app.get('/api/dashboard', (req, res) => {
  const links = db.all(`
    SELECT l.id, l.short_code, l.original_url, l.created_at, COUNT(c.id) as clicks_count
    FROM links l LEFT JOIN clicks c ON c.link_id = l.id
    GROUP BY l.id ORDER BY l.created_at DESC
  `);
  res.json(links);
});

app.get('/api/clicks/:shortCode', (req, res) => {
  const link = db.get('SELECT * FROM links WHERE short_code = ?', [req.params.shortCode]);
  if (!link) return res.status(404).json({ error: 'غير موجود' });

  const clicks = db.all(`
    SELECT ip_address, country, city, device_type, browser, os, lat, lng, timezone, language, screen_res, clicked_at
    FROM clicks WHERE link_id = ? ORDER BY clicked_at DESC LIMIT 100
  `, [link.id]);

  res.json({ link, clicks });
});

app.get('/api/get-location', async (req, res) => {
  let ip = req.headers['x-forwarded-for']?.split(',')[0].trim() || req.headers['x-real-ip'] || req.ip || '';
  ip = ip.replace('::ffff:', '');

  let location = { country: null, city: null, lat: null, lng: null };
  try {
    const res1 = await fetch(`https://ipapi.co/${ip}/json/`);
    const data1 = await res1.json();
    if (data1 && !data1.error && data1.country_name) {
      location = { country: data1.country_name, city: data1.city, lat: data1.latitude, lng: data1.longitude };
      return res.json(location);
    }
  } catch (e) {}
  
  try {
    const res2 = await fetch(`https://ipinfo.io/${ip}/json`);
    const data2 = await res2.json();
    if (data2 && data2.country) {
      let lat = null, lng = null;
      if (data2.loc) { const [latStr, lngStr] = data2.loc.split(','); lat = parseFloat(latStr); lng = parseFloat(lngStr); }
      location = { country: data2.country, city: data2.city, lat, lng };
      return res.json(location);
    }
  } catch (e) {}

  res.json(location);
});

// 📝 تسجيل النقرة مع البصمة الرقمية
app.post('/api/click', async (req, res) => {
  const { shortCode, deviceType, browser, os, timezone, language, screen_res } = req.body;

  const link = db.get('SELECT id FROM links WHERE short_code = ?', [shortCode]);
  if (!link) return res.status(404).json({ error: 'رابط غير موجود' });

  let ip = req.headers['x-forwarded-for']?.split(',')[0].trim() || req.headers['x-real-ip'] || req.ip || '';
  ip = ip.replace('::ffff:', '');

  let country = null, city = null, lat = null, lng = null;
  try {
    const geoRes = await fetch(`https://ipapi.co/${ip}/json/`);
    const geoData = await geoRes.json();
    if (geoData && !geoData.error) {
      country = geoData.country_name; city = geoData.city; lat = geoData.latitude; lng = geoData.longitude;
    }
  } catch (e) {}

  db.run(`
    INSERT INTO clicks (link_id, ip_address, country, city, device_type, browser, os, lat, lng, timezone, language, screen_res)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `, [link.id, ip, country, city, deviceType, browser, os, lat, lng, timezone, language, screen_res]);

  res.json({ success: true });
});

app.get('/track.html', (req, res) => res.sendFile(path.join(__dirname, 'public', 'track.html')));

app.get('/:shortCode', (req, res) => {
  const link = db.get('SELECT * FROM links WHERE short_code = ?', [req.params.shortCode]);
  if (!link) return res.status(404).send('<h1>الرابط غير موجود</h1><a href="/">رجوع</a>');

  const ua = new UAParser(req.headers['user-agent']).getResult();
  res.redirect(
    `/track.html?code=${encodeURIComponent(link.short_code)}` +
    `&url=${encodeURIComponent(link.original_url)}` +
    `&dt=${ua.device.type || 'desktop'}&br=${encodeURIComponent(ua.browser.name || 'Unknown')}&os=${encodeURIComponent(ua.os.name || 'Unknown')}`
  );
});
